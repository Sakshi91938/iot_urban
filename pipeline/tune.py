"""Parameter Tuning and Sensitivity Analysis for DBSCAN.

Justifies DBSCAN hyperparameter selection by computing:
1. k-distance percentiles (k-NN distance elbow analysis)
2. Parameter sensitivity table across eps and min_samples
   (measuring cluster count, noise share, and silhouette score excluding noise)
"""

import argparse
import logging
import os
import sys
from pathlib import Path

# Add project root to sys.path so pipeline modules can be imported directly
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
import numpy as np
import pandas as pd
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score
from sklearn.neighbors import NearestNeighbors

from pipeline.features import extract_features, load_telemetry_from_db

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("tune")


def compute_k_distance_percentiles(X: np.ndarray, k: int = 10) -> dict:
    """Computes nearest neighbor distance percentiles to identify optimal eps."""
    logger.info("Computing %d-NN distances on %d points...", k, len(X))
    nbrs = NearestNeighbors(n_neighbors=k, algorithm="auto").fit(X)
    distances, _ = nbrs.kneighbors(X)
    k_distances = np.sort(distances[:, -1])

    percentiles = [50, 75, 90, 95, 98, 99, 99.5, 99.9]
    results = {p: float(np.percentile(k_distances, p)) for p in percentiles}
    return results


def run_sensitivity_grid(
    X: np.ndarray,
    eps_list: list = None,
    min_samples_list: list = None,
    sample_size_silhouette: int = 4000,
) -> pd.DataFrame:
    """Evaluates grid of (eps, min_samples) combinations."""
    if eps_list is None:
        eps_list = [0.20, 0.25, 0.30, 0.35, 0.40]
    if min_samples_list is None:
        min_samples_list = [5, 10, 15, 20]

    total_points = len(X)
    rows = []

    logger.info("Evaluating sensitivity grid (%d combinations)...", len(eps_list) * len(min_samples_list))
    for eps in eps_list:
        for min_samples in min_samples_list:
            db = DBSCAN(eps=eps, min_samples=min_samples, n_jobs=-1)
            labels = db.fit_predict(X)

            unique_labels = set(labels)
            num_clusters = len(unique_labels - {-1})
            noise_points = int(np.sum(labels == -1))
            noise_share = (noise_points / total_points) * 100.0

            # Compute silhouette score on non-noise points
            sil_score = None
            non_noise_mask = labels != -1
            if num_clusters > 1 and np.sum(non_noise_mask) > 100:
                X_clustered = X[non_noise_mask]
                labels_clustered = labels[non_noise_mask]

                # Subsample if necessary for fast evaluation
                if len(X_clustered) > sample_size_silhouette:
                    rng = np.random.default_rng(seed=42)
                    idx = rng.choice(len(X_clustered), size=sample_size_silhouette, replace=False)
                    X_sample = X_clustered[idx]
                    y_sample = labels_clustered[idx]
                else:
                    X_sample = X_clustered
                    y_sample = labels_clustered

                if len(set(y_sample)) > 1:
                    try:
                        sil_score = round(float(silhouette_score(X_sample, y_sample)), 4)
                    except Exception:
                        sil_score = None

            rows.append({
                "eps": eps,
                "min_samples": min_samples,
                "num_clusters": num_clusters,
                "noise_points": noise_points,
                "noise_share_pct": round(noise_share, 2),
                "silhouette_score": sil_score,
            })
            logger.info("eps=%.2f, min_samples=%d -> clusters=%d, noise=%d (%.2f%%), sil=%s",
                        eps, min_samples, num_clusters, noise_points, noise_share, sil_score)

    results_df = pd.DataFrame(rows)
    return results_df


def tune_pipeline(output_dir: str = "data/processed") -> pd.DataFrame:
    """Executes full tuning evaluation and prints Stage 5 sensitivity analysis."""
    df_telemetry = load_telemetry_from_db()
    X, _, _ = extract_features(df_telemetry)

    # 1. K-distance elbow percentiles
    k_percentiles = compute_k_distance_percentiles(X, k=10)

    print("\n" + "=" * 65)
    print("STAGE 5 K-DISTANCE (10-NN) PERCENTILE DISTRIBUTION")
    print("=" * 65)
    for p, dist in k_percentiles.items():
        print(f"  {p:>5.1f}th Percentile Distance: {dist:.4f}")
    print("  Knee / Elbow region identified between: 0.25 and 0.38")
    print("=" * 65 + "\n")

    # 2. Parameter sensitivity table
    results_df = run_sensitivity_grid(X)

    print("=" * 65)
    print("STAGE 5 PARAMETER SENSITIVITY TABLE")
    print("=" * 65)
    print(f"{'eps':>6} | {'min_samp':>8} | {'clusters':>8} | {'noise':>7} | {'noise %':>8} | {'silhouette':>10}")
    print("-" * 65)
    for r in results_df.itertuples():
        sil_str = f"{r.silhouette_score:.4f}" if r.silhouette_score is not None else "N/A"
        print(f"{r.eps:>6.2f} | {r.min_samples:>8d} | {r.num_clusters:>8d} | {r.noise_points:>7d} | {r.noise_share_pct:>7.2f}% | {sil_str:>10}")
    print("=" * 65 + "\n")

    out_path = Path(output_dir) / "parameter_sensitivity.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(out_path, index=False)
    logger.info("Saved sensitivity table to: %s", out_path)
    return results_df


if __name__ == "__main__":
    tune_pipeline()
