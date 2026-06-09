from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from services.predict import build_prediction
from services.storage import MultiplierStore


def _values(rows: list[dict]) -> list[float]:
    return [float(row["value"]) for row in rows]


def generate_session_chart(
    multipliers: list[dict],
    bet_count: int,
    history: int = 30,
) -> tuple[bytes, str]:
    """
    Génère un graphe PNG (en mémoire) des `history` derniers multiplicateurs.
    `multipliers` est dans l'ordre décroissant (le plus récent en premier).
    Retourne (image_bytes, caption_html).
    """
    import io
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    last_n = multipliers[:history]
    # Remettre dans l'ordre chronologique (ancien → récent)
    last_n = list(reversed(last_n))
    values = [float(m["value"]) for m in last_n]

    if not values:
        return b"", "📊 Aucune donnée disponible."

    n = len(values)
    x = list(range(1, n + 1))
    v_min = round(min(values), 2)
    v_max = round(max(values), 2)
    v_mean = round(sum(values) / len(values), 2)
    count_ge2 = sum(1 for v in values if v >= 2.0)
    pct_ge2 = round(count_ge2 / n * 100)

    last5 = [float(m["value"]) for m in multipliers[:5]]
    bonus_5 = sum(1 for v in last5 if v >= 2.0)
    if bonus_5 >= 4:
        tendance = "HAUSSE ↑"
    elif bonus_5 <= 1:
        tendance = "BAISSE ↓"
    else:
        tendance = "STABLE →"

    # --- Graphe ---
    fig, ax = plt.subplots(figsize=(12, 5))
    fig.patch.set_facecolor("#1a1a2e")
    ax.set_facecolor("#16213e")

    colors = ["#00d4aa" if v >= 2.0 else "#ff4757" for v in values]
    ax.bar(x, values, color=colors, width=0.7, alpha=0.85, zorder=2)

    # Ligne seuil 2.0x
    ax.axhline(2.0, color="#ffa502", linestyle="--", linewidth=1.5, label="Seuil 2.0x", zorder=3)
    # Ligne moyenne
    ax.axhline(v_mean, color="#ecf0f1", linestyle=":", linewidth=1.2, label=f"Moy. {v_mean}x", zorder=3)

    # Marquer le dernier point (le plus récent)
    ax.bar(x[-1], values[-1], color="#f9ca24", width=0.7, alpha=1.0, zorder=4, label=f"Dernier: {values[-1]}x")

    # Étiquette valeur sur chaque barre
    for xi, v in zip(x, values):
        ax.text(xi, v + 0.05, f"{v:.1f}", ha="center", va="bottom", fontsize=6.5,
                color="#ecf0f1", fontweight="bold")

    ax.set_xlim(0.3, n + 0.7)
    ax.set_ylim(0, max(values) * 1.25 + 0.5)
    ax.set_xlabel("Ordre de partie (ancien → récent)", color="#ecf0f1", fontsize=9)
    ax.set_ylabel("Multiplicateur", color="#ecf0f1", fontsize=9)
    ax.set_title(
        f"Circuit Masters — 30 derniers multiplicateurs  |  Partie n°{bet_count}",
        color="#ecf0f1", fontsize=11, fontweight="bold", pad=10,
    )
    ax.tick_params(colors="#ecf0f1")
    for spine in ax.spines.values():
        spine.set_edgecolor("#2f3640")
    ax.legend(facecolor="#2f3640", labelcolor="#ecf0f1", fontsize=8)
    ax.grid(axis="y", color="#2f3640", linewidth=0.6, zorder=1)

    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    image_bytes = buf.read()

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    caption = (
        f"📊 <b>Rapport {n} parties — {timestamp}</b>\n"
        f"├ Min    : <code>{v_min}x</code>\n"
        f"├ Max    : <code>{v_max}x</code>\n"
        f"├ Moy.   : <code>{v_mean}x</code>\n"
        f"├ ≥ 2.0x : {count_ge2}/{n} ({pct_ge2}%)\n"
        f"├ Tendance : {tendance}\n"
        f"└ Partie n°{bet_count}"
    )
    return image_bytes, caption


def generate_daily_report(
    db_path: str | Path = "data/bot.db",
    output_dir: str | Path = "reports",
    day: str | None = None,
) -> dict:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

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
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
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
