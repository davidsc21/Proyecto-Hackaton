"""CLI: build features and train the seismic-risk model."""

from __future__ import annotations

import argparse

from src.features import build_and_save
from src.model import train
from src.supabase_client import get_client, test_connection
from src.data_fetch import events_to_supabase, load_raw


def main(fetch_remote: bool = False):
    features = build_and_save()
    print(f"Feature rows: {len(features)}")
    print(features["risk_level"].value_counts().to_dict())

    pipeline, metrics = train(features)
    print("Training complete.")
    print("Metrics:", {k: v for k, v in metrics.items() if k != "classification_report"})

    # Optional Supabase sync
    client = get_client()
    ok, msg = test_connection(client)
    print(msg)
    if ok:
        try:
            df = load_raw()
            n = events_to_supabase(df, client)
            print(f"Upserted {n} earthquakes to Supabase.")
            # Upsert risk zones
            records = []
            for row in features.to_dict(orient="records"):
                records.append(
                    {
                        "cell_id": row["cell_id"],
                        "cell_lat": float(row["cell_lat"]),
                        "cell_lon": float(row["cell_lon"]),
                        "n_events": int(row["n_events"]),
                        "max_magnitude": float(row["max_magnitude"]),
                        "mean_magnitude": float(row["mean_magnitude"]),
                        "mean_depth_km": float(row["mean_depth_km"]),
                        "log_energy": float(row["log_energy"]),
                        "events_per_year": float(row["events_per_year"]),
                        "risk_level": row["risk_level"],
                        "dist_to_mesa_km": float(row["dist_to_mesa_km"]),
                        "dist_to_seismic_nest_km": float(row["dist_to_seismic_nest_km"]),
                    }
                )
            for i in range(0, len(records), 500):
                client.table("risk_zones").upsert(records[i : i + 500], on_conflict="cell_id").execute()
            print(f"Upserted {len(records)} risk zones to Supabase.")
        except Exception as exc:  # noqa: BLE001
            print(f"Supabase sync failed: {exc}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fetch", action="store_true", help="Re-fetch data before training")
    args = parser.parse_args()
    if args.fetch:
        from src.data_fetch import fetch_santander_history, save_raw

        df = fetch_santander_history(2005)
        save_raw(df)
    main()
