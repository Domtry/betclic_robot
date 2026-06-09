from __future__ import annotations

import argparse
import json

from services.report import generate_hourly_report


def main():
    parser = argparse.ArgumentParser(description="Génère le rapport horaire des multiplicateurs.")
    parser.add_argument("--db", default="data/bot.db", help="Chemin de la base SQLite")
    parser.add_argument("--output-dir", default="reports", help="Dossier de sortie des rapports")
    parser.add_argument(
        "--hour",
        default=None,
        help="Heure au format YYYY-MM-DD HH (UTC); par défaut l'heure courante UTC",
    )
    args = parser.parse_args()

    result = generate_hourly_report(
        db_path=args.db, output_dir=args.output_dir, hour=args.hour
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
