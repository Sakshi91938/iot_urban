"""Data Preparation and Cleaning Pipeline.

Reads Delhi Traffic Density Dataset directly from a ZIP archive,
converts EpochTime to timezone-aware timestamps (Asia/Kolkata),
reshapes wide zone columns into normalized rows,
filters invalid values (nulls, negatives, duplicates),
and aggregates second-level telemetry into 5-minute interval buckets.
"""

import argparse
import logging
import os
import sys
import zipfile
from pathlib import Path
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("prepare")


def clean_and_aggregate_df(
    raw_df: pd.DataFrame,
    tz: str = "Asia/Kolkata",
) -> tuple[pd.DataFrame, dict]:
    """Cleans a single day's raw traffic DataFrame and aggregates to 5-minute intervals.

    Args:
        raw_df: Raw DataFrame with EpochTime and QueueDensity1..6, StopDensity1..6.
        tz: Timezone string for timestamp localization.

    Returns:
        tuple of (aggregated_df, stats_dict)
    """
    stats = {
        "raw_rows": len(raw_df),
        "null_rows_removed": 0,
        "negative_rows_removed": 0,
        "duplicate_rows_removed": 0,
        "valid_point_rows": 0,
        "bucket_rows": 0,
    }

    if raw_df.empty:
        return pd.DataFrame(), stats

    # 1. Convert EpochTime to timezone-aware timestamps
    timestamps = pd.to_datetime(raw_df["EpochTime"], unit="s", utc=True).dt.tz_convert(tz)

    # 2. Reshape from wide columns (QueueDensity1..6, StopDensity1..6) to long format
    zone_frames = []
    for zone_id in range(1, 7):
        q_col = f"QueueDensity{zone_id}"
        s_col = f"StopDensity{zone_id}"
        if q_col in raw_df.columns and s_col in raw_df.columns:
            sub = pd.DataFrame({
                "ts": timestamps,
                "zone": zone_id,
                "queue_density": pd.to_numeric(raw_df[q_col], errors="coerce"),
                "stop_density": pd.to_numeric(raw_df[s_col], errors="coerce"),
            })
            zone_frames.append(sub)

    if not zone_frames:
        return pd.DataFrame(), stats

    long_df = pd.concat(zone_frames, ignore_index=True)
    total_points = len(long_df)

    # 3. Handle Nulls
    null_mask = long_df[["ts", "zone", "queue_density", "stop_density"]].isna().any(axis=1)
    null_count = int(null_mask.sum())
    stats["null_rows_removed"] = null_count
    if null_count > 0:
        long_df = long_df[~null_mask]

    # 4. Handle Negatives
    neg_mask = (long_df["queue_density"] < 0) | (long_df["stop_density"] < 0)
    neg_count = int(neg_mask.sum())
    stats["negative_rows_removed"] = neg_count
    if neg_count > 0:
        long_df = long_df[~neg_mask]

    # 5. Handle Duplicates on (ts, zone)
    dup_mask = long_df.duplicated(subset=["ts", "zone"], keep="first")
    dup_count = int(dup_mask.sum())
    stats["duplicate_rows_removed"] = dup_count
    if dup_count > 0:
        long_df = long_df[~dup_mask]

    stats["valid_point_rows"] = len(long_df)

    # 6. Aggregate to 5-minute buckets (floor timestamp)
    long_df["ts_bucket"] = long_df["ts"].dt.floor("5min")
    agg_df = (
        long_df.groupby(["ts_bucket", "zone"], as_index=False)[["queue_density", "stop_density"]]
        .mean()
        .rename(columns={"ts_bucket": "ts"})
    )
    agg_df["queue_density"] = agg_df["queue_density"].round(6)
    agg_df["stop_density"] = agg_df["stop_density"].round(6)
    agg_df = agg_df.sort_values(by=["ts", "zone"]).reset_index(drop=True)

    stats["bucket_rows"] = len(agg_df)
    return agg_df, stats


def process_dataset(
    zip_path: str = "data/raw/DelhiTrafficDensityDataset.zip",
    output_path: str = "data/processed/clean_traffic_5min.csv",
    tz: str = "Asia/Kolkata",
) -> pd.DataFrame:
    """Processes all daily CSV files from the dataset ZIP directly.

    Args:
        zip_path: Path to DelhiTrafficDensityDataset.zip.
        output_path: Output CSV destination path.
        tz: Timezone string.

    Returns:
        Consolidated 5-minute aggregated DataFrame.
    """
    zip_file = Path(zip_path)
    if not zip_file.is_file():
        raise FileNotFoundError(f"Dataset zip archive not found at: {zip_path}")

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    logger.info("Opening dataset archive: %s", zip_path)
    daily_results = []
    total_stats = {
        "files_processed": 0,
        "raw_rows_total": 0,
        "null_rows_removed": 0,
        "negative_rows_removed": 0,
        "duplicate_rows_removed": 0,
        "total_5min_rows": 0,
    }

    with zipfile.ZipFile(zip_file, "r") as z:
        csv_names = sorted([n for n in z.namelist() if n.endswith(".csv") and not n.startswith("__MACOSX")])
        logger.info("Found %d daily CSV files in archive.", len(csv_names))

        for idx, filename in enumerate(csv_names, start=1):
            with z.open(filename) as f:
                raw_df = pd.read_csv(f)
                agg_df, stats = clean_and_aggregate_df(raw_df, tz=tz)

                daily_results.append(agg_df)
                total_stats["files_processed"] += 1
                total_stats["raw_rows_total"] += stats["raw_rows"]
                total_stats["null_rows_removed"] += stats["null_rows_removed"]
                total_stats["negative_rows_removed"] += stats["negative_rows_removed"]
                total_stats["duplicate_rows_removed"] += stats["duplicate_rows_removed"]
                total_stats["total_5min_rows"] += stats["bucket_rows"]

                logger.info(
                    "[%02d/%d] %s: %d raw seconds -> %d 5-min rows (nulls=%d, neg=%d, dup=%d)",
                    idx,
                    len(csv_names),
                    os.path.basename(filename),
                    stats["raw_rows"],
                    stats["bucket_rows"],
                    stats["null_rows_removed"],
                    stats["negative_rows_removed"],
                    stats["duplicate_rows_removed"],
                )

    consolidated_df = pd.concat(daily_results, ignore_index=True)
    # Ensure idempotency across the combined dataset on (ts, zone)
    initial_len = len(consolidated_df)
    consolidated_df = consolidated_df.drop_duplicates(subset=["ts", "zone"]).sort_values(by=["ts", "zone"]).reset_index(drop=True)
    if len(consolidated_df) < initial_len:
        logger.warning("Removed %d cross-file duplicate rows on (ts, zone).", initial_len - len(consolidated_df))

    consolidated_df.to_csv(output_file, index=False)
    logger.info("Saved cleaned and aggregated dataset to: %s", output_path)

    # Print Stage 3 verification summary report
    print("\n" + "=" * 60)
    print("STAGE 3 DATA CLEANING & AGGREGATION SUMMARY REPORT")
    print("=" * 60)
    print(f"Total files processed:       {total_stats['files_processed']}")
    print(f"Total raw second rows:       {total_stats['raw_rows_total']:,}")
    print(f"Total raw zone data points:  {total_stats['raw_rows_total'] * 6:,}")
    print(f"Rows removed (Null values):  {total_stats['null_rows_removed']}")
    print(f"Rows removed (Negatives):    {total_stats['negative_rows_removed']}")
    print(f"Rows removed (Duplicates):   {total_stats['duplicate_rows_removed']}")
    print(f"Total 5-minute bucket rows:  {len(consolidated_df):,}")
    print(f"Average rows per zone:       {len(consolidated_df) / 6:,.1f}")
    print(f"Sanity check benchmark:     43,440 rows (Match: {'YES' if len(consolidated_df) == 43440 else 'NO'})")
    print("=" * 60 + "\n")

    return consolidated_df


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare and clean Delhi Traffic Density Dataset")
    parser.add_argument("--zip-path", default="data/raw/DelhiTrafficDensityDataset.zip", help="Path to raw dataset ZIP")
    parser.add_argument("--output-path", default="data/processed/clean_traffic_5min.csv", help="Path to output CSV")
    parser.add_argument("--tz", default="Asia/Kolkata", help="Timezone (default: Asia/Kolkata)")
    args = parser.parse_args()

    process_dataset(zip_path=args.zip_path, output_path=args.output_path, tz=args.tz)
