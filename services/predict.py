from __future__ import annotations

import statistics
from collections import Counter
from typing import Iterable


def build_prediction(values: Iterable[float], target: float = 2.0) -> dict:
    """
    Build a conservative statistical signal from historical multipliers.

    Important: this is descriptive/probabilistic, not a guarantee. Casino RNG outcomes
    are not reliably predictable from previous rounds.
    """
    values = [float(v) for v in values if v is not None]
    if not values:
        return {
            "sample_size": 0,
            "target": target,
            "probability_next_ge_target": 0.0,
            "recommendation": "OBSERVATION",
            "reason": "Pas assez de données",
            "warning": "Ce n'est pas une garantie : les jeux RNG restent imprévisibles.",
        }

    hits = sum(1 for value in values if value >= target)
    probability = hits / len(values)
    recent = values[-10:]
    recent_hits = sum(1 for value in recent if value >= target) / len(recent)
    mean = statistics.fmean(values)
    median = statistics.median(values)

    # Conservative signal: require enough samples and do not overstate the result.
    if len(values) < 50:
        recommendation = "OBSERVATION"
        reason = "Échantillon encore trop faible pour décider"
    elif probability >= 0.48 and recent_hits >= 0.45:
        recommendation = "SIGNAL_MODERE"
        reason = "Fréquence récente et globale au-dessus du seuil interne"
    else:
        recommendation = "PRUDENCE"
        reason = "Signal insuffisant ou instable"

    bands = Counter(
        "<1.5" if v < 1.5 else "1.5-2" if v < 2 else "2-5" if v < 5 else ">=5"
        for v in values
    )

    return {
        "sample_size": len(values),
        "target": target,
        "probability_next_ge_target": round(probability, 4),
        "recent_probability_ge_target": round(recent_hits, 4),
        "mean": round(mean, 4),
        "median": round(median, 4),
        "max": round(max(values), 4),
        "bands": dict(bands),
        "recommendation": recommendation,
        "reason": reason,
        "warning": "Ce n'est pas une garantie : les jeux RNG restent imprévisibles.",
    }
