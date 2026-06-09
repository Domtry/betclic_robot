from services.analyze import analyze, generate_mise


def test_analyze_empty_data_returns_invalid_analysis():
    result = analyze([])

    assert result["nombre_total"] == 0
    assert result["is_valid"] is False
    assert result["historique_recent"] == []


def test_generate_mise_refuses_invalid_or_short_analysis():
    assert generate_mise({"is_valid": False, "historique_recent": []}) == {
        "cote": 0,
        "mise": 0,
        "is_ready": False,
    }
    assert generate_mise(analyze([{"value": 1.2}]))["is_ready"] is False
