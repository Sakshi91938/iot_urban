"""DBSCAN Clustering Execution and Database Traceability.

Executes DBSCAN clustering with justified hyperparameters,
records execution metadata into PostgreSQL 'cluster_runs',
and writes cluster labels into 'traffic_clusters'.
"""

import argparse
import logging
import os
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Add project root to sys.path so pipeline modules can be imported directly
project_root = str(Path(__file__).resolve().parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from dotenv import load_dotenv
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score

from pipeline.features import extract_features, load_telemetry_from_db

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("cluster")


def run_clustering(
    eps: float = 0.35,
    min_samples: int = 10,
    notes: str = "Primary DBSCAN clustering run based on k-distance elbow and sensitivity analysis",
    activate: bool = True,
) -> dict:
    """Executes DBSCAN clustering and stores traceable results in PostgreSQL."""
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME", "urban_mobility"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
    )
    cur = conn.cursor()

    # 1. Load telemetry data and extract features
    df_telemetry = load_telemetry_from_db(conn=conn)
    total_points = len(df_telemetry)
    if total_points == 0:
        raise ValueError("No telemetry records found in PostgreSQL. Run Stage 4 replay first.")

    X, feature_names, _ = extract_features(df_telemetry)

    # 2. Run DBSCAN Clustering
    logger.info("Fitting DBSCAN (eps=%.2f, min_samples=%d) on %d points...", eps, min_samples, total_points)
    db = DBSCAN(eps=eps, min_samples=min_samples, n_jobs=-1)
    labels = db.fit_predict(X)

    unique_labels = sorted(list(set(labels)))
    num_clusters = len([lab for lab in unique_labels if lab != -1])
    noise_points = int(np.sum(labels == -1))
    noise_share = round((noise_points / total_points) * 100.0, 3)

    # 3. Calculate Silhouette Score on Clustered Sample
    sil_score = None
    non_noise_mask = labels != -1
    if num_clusters > 1 and np.sum(non_noise_mask) > 100:
        X_clustered = X[non_noise_mask]
        labels_clustered = labels[non_noise_mask]
        sample_size = min(5000, len(X_clustered))
        rng = np.random.default_rng(seed=42)
        sample_indices = rng.choice(len(X_clustered), size=sample_size, replace=False)
        try:
            sil_score = round(float(silhouette_score(X_clustered[sample_indices], labels_clustered[sample_indices])), 4)
        except Exception as e:
            logger.warning("Could not compute silhouette score: %s", e)

    # 4. Generate unique run ID
    timestamp_tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_id = f"run_eps{int(eps*100):02d}_min{min_samples}_{timestamp_tag}"

    logger.info("Clustering completed: run_id=%s, clusters=%d, noise=%d (%.2f%%), silhouette=%s",
                run_id, num_clusters, noise_points, noise_share, sil_score)

    # 5. Insert Run Record into cluster_runs
    if activate:
        cur.execute("UPDATE cluster_runs SET is_active = FALSE WHERE is_active = TRUE;")

    insert_run_sql = """
        INSERT INTO cluster_runs (
            run_id, eps, min_samples, features_used, total_points, 
            num_clusters, noise_points, noise_share, silhouette_score, is_active, notes
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s);
    """
    cur.execute(insert_run_sql, (
        run_id,
        eps,
        min_samples,
        ", ".join(feature_names),
        total_points,
        num_clusters,
        noise_points,
        noise_share,
        sil_score,
        activate,
        notes,
    ))

    # 6. Batch Insert Clustered Results into traffic_clusters
    telemetry_ids = df_telemetry["id"].tolist()
    cluster_records = [(telemetry_ids[i], int(labels[i]), run_id) for i in range(total_points)]

    insert_clusters_sql = """
        INSERT INTO traffic_clusters (telemetry_id, cluster_id, run_id)
        VALUES %s
        ON CONFLICT (telemetry_id, run_id) DO UPDATE SET cluster_id = EXCLUDED.cluster_id;
    """
    logger.info("Writing %d cluster assignments to traffic_clusters...", len(cluster_records))
    execute_values(cur, insert_clusters_sql, cluster_records, page_size=2000)
    conn.commit()

    # 7. Compute Cluster Distribution Breakdown
    df_telemetry["cluster_id"] = labels
    distribution = df_telemetry["cluster_id"].value_counts().sort_index().to_dict()

    print("\n" + "=" * 65)
    print("STAGE 5 DBSCAN CLUSTERING EXECUTION SUMMARY")
    print("=" * 65)
    print(f"Run Identifier:             {run_id}")
    print(f"Algorithm:                  DBSCAN (scikit-learn)")
    print(f"Hyperparameters:            eps = {eps:.2f}, min_samples = {min_samples}")
    print(f"Features:                   {', '.join(feature_names)}")
    print(f"Total Points Clustered:     {total_points:,}")
    print(f"Discovered Clusters:        {num_clusters}")
    print(f"Noise / Anomaly Points:     {noise_points:,} ({noise_share:.2f}%)")
    print(f"Silhouette Score (sample):  {sil_score if sil_score is not None else 'N/A'}")
    print(f"Active in DB Views:         {'YES' if activate else 'NO'}")
    print("-" * 65)
    print("Cluster Distribution Breakdown:")
    for cid, count in distribution.items():
        name = "Anomaly (Noise)" if cid == -1 else f"Cluster {cid}"
        pct = (count / total_points) * 100.0
        print(f"  {name:<22} : {count:>6,d} points ({pct:>5.1f}%)")
    print("=" * 65 + "\n")

    cur.close()
    conn.close()

    return {
        "run_id": run_id,
        "eps": eps,
        "min_samples": min_samples,
        "num_clusters": num_clusters,
        "noise_points": noise_points,
        "noise_share": noise_share,
        "silhouette_score": sil_score,
        "distribution": distribution,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Execute DBSCAN Traffic Clustering")
    parser.add_argument("--eps", type=float, default=0.35, help="DBSCAN eps (default: 0.35)")
    parser.add_argument("--min-samples", type=int, default=10, help="DBSCAN min_samples (default: 10)")
    parser.add_argument("--notes", default="Default verified clustering run", help="Run notes")
    args = parser.parse_args()

    run_clustering(eps=args.eps, min_samples=args.min_samples, notes=args.notes)
