from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from services.predict import build_prediction
from services.storage import MultiplierStore


def _values(rows: list[dict]) -> list[float]:
    return [float(row["value"]) for row in rows]


def generate_daily_report(
    db_path: str | Path = "data/bot.db",
    output_dir: str | Path = "reports",
    day: str | None = None,
) -> dict:
    day = day or date.today().isoformat()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    store = MultiplierStore(db_path)
    rows = store.fetch_day(day)
    values = _values(rows)
    prediction = build_prediction(values)

    chart_path = output_dir / f"multipliers_{day}.png"
    summary_path = output_dir / f"summary_{day}.txt"

    plt.figure(figsize=(12, 6))
    if values:
        plt.plot(range(1, len(values) + 1), values, marker="o", linewidth=1.2, markersize=3)
        plt.axhline(2.0, color="orange", linestyle="--", label="Seuil 2.0x")
        plt.axhline(prediction["mean"], color="green", linestyle=":", label=f"Moyenne {prediction['mean']}x")
        plt.title(f"Multiplicateurs observés — {day}")
        plt.xlabel("Ordre d'observation")
        plt.ylabel("Multiplicateur")
        plt.legend()
    else:
        plt.text(0.5, 0.5, "Aucune donnée pour cette journée", ha="center", va="center")
        plt.title(f"Multiplicateurs observés — {day}")
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()

    summary = [
        f"Rapport quotidien — {day}",
        f"Nombre de résultats: {len(values)}",
        f"Probabilité historique >= 2.0x: {prediction['probability_next_ge_target']}",
        f"Probabilité récente >= 2.0x: {prediction.get('recent_probability_ge_target', 0)}",
        f"Moyenne: {prediction.get('mean', 0)}",
        f"Médiane: {prediction.get('median', 0)}",
        f"Maximum: {prediction.get('max', 0)}",
        f"Signal: {prediction['recommendation']}",
        f"Raison: {prediction['reason']}",
        f"Avertissement: {prediction['warning']}",
    ]
    summary_path.write_text("\n".join(summary), encoding="utf-8")

    return {
        "day": day,
        "count": len(values),
        "chart_path": str(chart_path),
        "summary_path": str(summary_path),
        "prediction": prediction,
    }


def generate_hourly_report(
    db_path: str | Path = "data/bot.db",
    output_dir: str | Path = "reports",
    hour: str | None = None,
) -> dict:
    """
    Generate a report for a specific hour (in UTC).
    hour format: "YYYY-MM-DD HH" (e.g., "2026-06-04 15")
    If hour is None, uses the current hour in UTC.
    """
    from datetime import datetime as dt

    if hour is None:
        now = datetime.now(timezone.utc)
        hour_str = now.strftime("%Y-%m-%d %H")
    else:
        hour_str = hour

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    store = MultiplierStore(db_path)
    # Fetch for the day then filter by hour
    day = hour_str.split()[0]  # YYYY-MM-DD
    rows = store.fetch_day(day)
    # Parse observed_at strings to datetime objects for filtering
    target_hour_dt = dt.strptime(hour_str, "%Y-%m-%d %H").replace(tzinfo=timezone.utc)
    filtered_rows = []
    for row in rows:
        obs_str = row["observed_at"]
        # obs_str may be like "2026-01-01T13:00:00+00:00" or "2026-01-01 13:00:00"
        # Try to parse
        try:
            # If contains T, split
            if "T" in obs_str:
                dt_obs = dt.fromisoformat(obs_str.replace("Z", "+00:00"))
            else:
                dt_obs = dt.fromisoformat(obs_str)
        except Exception:
            # Fallback: try to parse ignoring timezone
            try:
                dt_obs = dt.strptime(obs_str[:19], "%Y-%m-%d %H:%M:%S")
            except Exception:
                continue
        if dt_obs.hour == target_hour_dt.hour and dt_obs.day == target_hour_dt.day and dt_obs.month == target_hour_dt.month and dt_obs.year == target_hour_dt.year:
            filtered_rows.append(row)
    values = _values(filtered_rows)
    prediction = build_prediction(values)

    # Safe filename: replace space with _
    safe_hour = hour_str.replace(" ", "_")
    chart_path = output_dir / f"multipliers_{safe_hour}.png"
    summary_path = output_dir / f"summary_{safe_hour}.txt"

    plt.figure(figsize=(12, 6))
    if values:
        plt.plot(range(1, len(values) + 1), values, marker="o", linewidth=1.2, markersize=3)
        plt.axhline(2.0, color="orange", linestyle="--", label="Seuil 2.0x")
        plt.axhline(prediction["mean"], color="green", linestyle=":", label=f"Moyenne {prediction['mean']}x")
        plt.title(f"Multiplicateurs observés — {hour_str}")
        plt.xlabel("Ordre d'observation")
        plt.ylabel("Multiplicateur")
        plt.legend()
    else:
        plt.text(0.5, 0.5, f"Aucune donnée pour l'heure {hour_str}", ha="center", va="center")
        plt.title(f"Multiplicateurs observés — {hour_str}")
    plt.tight_layout()
    plt.savefig(chart_path)
    plt.close()

    summary = [
        f"Rapport horaire — {hour_str}",
        f"Nombre de résultats: {len(values)}",
        f"Probabilité historique >= 2.0x: {prediction['probability_next_ge_target']}",
        f"Probabilité récente >= 2.0x: {prediction.get('recent_probability_ge_target', 0)}",
        f"Moyenne: {prediction.get('mean', 0)}",
        f"Médiane: {prediction.get('median', 0)}",
        f"Maximum: {prediction.get('max', 0)}",
        f"Signal: {prediction['recommendation']}",
        f"Raison: {prediction['reason']}",
        f"Avertissement: {prediction['warning']}",
    ]
    summary_path.write_text("\n".join(summary), encoding="utf-8")

    return {
        "hour": hour_str,
        "count": len(values),
        "chart_path": str(chart_path),
        "summary_path": str(summary_path),
        "prediction": prediction,
    }
