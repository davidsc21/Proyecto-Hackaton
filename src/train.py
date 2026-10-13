"""CLI: build features and train the seismic-risk model."""

from __future__ import annotations

import argparse

from src.features import build_and_save
from src.model import train
from src.supabase_client import get_client, test_connection
from src.data_fetch import load_sismo
from src.database import seed_risk_zones, record_model_run


def main(fetch_remote: bool = False):
    features = build_and_save()
    print(f"Feature rows: {len(features)}")
    print(features["risk_level"].value_counts().to_dict())

    pipeline, metrics = train(features)
    print("Training complete.")
    print("Metrics:", {k: v for k, v in metrics.items() if k != "classification_report"})

    # Direct PostgreSQL sync (does not require REST API keys).
    # Events stay in Supabase (public.sismo); only derived risk zones are stored.
    try:
        n_rz = seed_risk_zones(features)
        print(f"Synced {n_rz} risk zones to PostgreSQL.")
    except Exception as exc:  # noqa: BLE001
        print(f"PostgreSQL risk-zone sync failed: {exc}")
    try:
        record_model_run("RandomForest", metrics)
        print("Recorded model run to PostgreSQL.")
    except Exception as exc:  # noqa: BLE001
        print(f"PostgreSQL model-run sync failed: {exc}")

    # Optional: report Supabase REST status (no duplicate event sync; events live in public.sismo).
    client = get_client()
    ok, msg = test_connection(client)
    print(msg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="Re-fetch data before training")
    args = parser.parse_args()
    if args.fetch:
        from src.data_fetch import fetch_santander_history, save_raw

        df = fetch_santander_history(2005)
        save_raw(df)
    main()
