import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.storage import MultiplierStore
from services.report import generate_daily_report, generate_hourly_report
from services.predict import build_prediction
from datetime import datetime, timedelta, timezone


def test_store_saves_unique_rounds_and_reads_latest(tmp_path):
    db_path = tmp_path / "bot.db"
    store = MultiplierStore(db_path)
    now = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)

    inserted = store.save_multipliers([{"raw": "1.2x", "value": 1.2}, {"raw": "2.5x", "value": 2.5}], observed_at=now)
    duplicate_inserted = store.save_multipliers([{"raw": "1.2x", "value": 1.2}], observed_at=now)

    assert inserted == 2
    assert duplicate_inserted == 0
    latest = store.fetch_latest(limit=10)
    assert [row["value"] for row in latest] == [2.5, 1.2]


def test_prediction_returns_probabilities_and_recommendation():
    values = [1.1, 1.2, 2.3, 1.8, 3.0, 1.4, 2.1, 1.0, 1.9, 2.6]

    prediction = build_prediction(values, target=2.0)

    assert prediction["sample_size"] == 10
    assert prediction["target"] == 2.0
    assert 0 <= prediction["probability_next_ge_target"] <= 1
    assert prediction["recommendation"] in {"OBSERVATION", "PRUDENCE", "SIGNAL_MODERE"}
    assert "Ce n'est pas une garantie" in prediction["warning"]


def test_generate_daily_report_creates_png_and_summary(tmp_path):
    db_path = tmp_path / "bot.db"
    output_dir = tmp_path / "reports"
    store = MultiplierStore(db_path)
    start = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    for i, value in enumerate([1.1, 1.4, 2.2, 1.8, 3.5, 1.2, 2.1]):
        store.save_multipliers([{"raw": f"{value}x", "value": value, "level": "high" if value >= 2 else "low"}], observed_at=start + timedelta(minutes=i))

    result = generate_daily_report(db_path=db_path, output_dir=output_dir, day="2026-01-01")

    assert result["count"] == 7
    assert Path(result["chart_path"]).exists()
    assert Path(result["summary_path"]).exists()
    assert result["prediction"]["sample_size"] == 7


def test_generate_hourly_report_creates_png_and_summary(tmp_path):
    db_path = tmp_path / "bot.db"
    output_dir = tmp_path / "reports"
    store = MultiplierStore(db_path)
    # Use a fixed hour: 2026-01-01 13
    base = datetime(2026, 1, 1, 13, 0, 0, tzinfo=timezone.utc)
    for i, value in enumerate([1.1, 1.4, 2.2, 1.8, 3.5]):
        store.save_multipliers([{"raw": f"{value}x", "value": value, "level": "high" if value >= 2 else "low"}], observed_at=base + timedelta(minutes=i))

    result = generate_hourly_report(db_path=db_path, output_dir=output_dir, hour="2026-01-01 13")

    assert result["count"] == 5
    assert Path(result["chart_path"]).exists()
    assert Path(result["summary_path"]).exists()
    assert result["prediction"]["sample_size"] == 5
    assert result["hour"] == "2026-01-01 13"