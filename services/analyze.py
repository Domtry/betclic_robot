# ============================================================
#  CONFIGURATION
# ============================================================
THRESHOLD       = 2.0
MAX_MISE        = 200   # mise max slot 1 (normale)
MIN_MISE        = 100   # mise min slot 1 (plancher)
MISE_STEP       = 10    # arrondi à la dizaine
MIN_COTE        = 1.10  # cote la plus basse — assure ~90% de victoires
MAX_COTE        = 1.80  # cote la plus haute en mode normal
SPIKE_THRESHOLD = 5.0   # valeur absolue minimale pour être considéré un pic
SPIKE_RATIO     = 2.5   # N × médiane des valeurs voisines → pic relatif

# Slot 2 — super multiplicateur (mise max 50F, cote haute)
SLOT2_MISE      = 50
SLOT2_COTE_HIGH = 10.0  # cote ambitieuse quand série basse ≥ 6
SLOT2_COTE_MED  = 8.0   # cote modérée quand série basse ≥ 4
SLOT2_MIN_STREAK = 4    # streak_low minimum pour activer le slot 2

# Récupération post-pic : progression sur 4 tours
_RECOVERY_COTES = {1: 1.10, 2: 1.15, 3: 1.20, 4: 1.30}
_RECOVERY_MISES = {1: 100,  2: 100,  3: 120,  4: 150}


# ============================================================
#  HELPERS — séries et statistiques
# ============================================================

def _streak_low(values: list[float]) -> int:
    """Nombre de valeurs consécutives < THRESHOLD depuis la plus récente."""
    count = 0
    for v in values:
        if v < THRESHOLD:
            count += 1
        else:
            break
    return count


def _streak_high(values: list[float]) -> int:
    """Nombre de valeurs consécutives >= THRESHOLD depuis la plus récente."""
    count = 0
    for v in values:
        if v >= THRESHOLD:
            count += 1
        else:
            break
    return count


def _rolling_mean(values: list[float], n: int) -> float:
    window = values[:n] if len(values) >= n else values
    return round(sum(window) / len(window), 3) if window else 0.0


def _p90_cote(values: list[float]) -> float:
    """
    Calcule la cote garantissant ~90% de victoires.
    = 10e percentile de l'historique récent (valeur dépassée 90% du temps).
    Arrondie à 0.05 près, bornée entre MIN_COTE (1.10) et MAX_COTE (1.80).
    """
    if len(values) < 10:
        return MIN_COTE
    sorted_vals = sorted(values)
    idx = max(0, int(len(sorted_vals) * 0.10) - 1)
    p10 = sorted_vals[idx]
    # Arrondir à 0.05 près, borner entre MIN_COTE et MAX_COTE
    cote = max(MIN_COTE, min(MAX_COTE, p10))
    return round(round(cote / 0.05) * 0.05, 2)


def _is_spike(value: float, context: list[float]) -> bool:
    """
    Détecte si une valeur est un pic isolé à ignorer.

    Conditions (les deux doivent être vraies) :
    1. Valeur >= SPIKE_THRESHOLD (seuil absolu, ex : 5.0x)
    2. Valeur >= SPIKE_RATIO × médiane des valeurs voisines (pic relatif)
    """
    if value < SPIKE_THRESHOLD:
        return False
    if not context:
        return True
    ctx_sorted = sorted(context)
    median_ctx = ctx_sorted[len(ctx_sorted) // 2]
    return value >= SPIKE_RATIO * max(median_ctx, 1.0)


def _rounds_since_last_spike(values: list[float]) -> int | None:
    """
    Cherche le pic le plus récent dans les 6 dernières valeurs.
    Retourne le nombre de tours depuis ce pic (0 = pic sur la valeur actuelle).
    Retourne None si aucun pic trouvé récemment.
    """
    for i, v in enumerate(values[:6]):
        if _is_spike(v, values[i + 1: i + 11]):
            return i
    return None


# ============================================================
#  ALGORITHME ADAPTATIF : COTE
# ============================================================

def _adaptive_cote(values: list[float]) -> float:
    """
    Cote cible pour ~90% de victoires.
    Base : 10e percentile des valeurs récentes (p90_cote).
    Ajustements selon les séries pour affiner.
    """
    if not values:
        return MIN_COTE

    base = _p90_cote(values)   # cote garantissant ~90% de victoires

    sl = _streak_low(values)
    sh = _streak_high(values)

    def _r(v): return round(round(v / 0.05) * 0.05, 2)

    # Ajustements autour de la base p90
    if sl >= 4: return _r(max(MIN_COTE, base - 0.05))
    if sl >= 2: return _r(base)
    if sl == 1: return _r(min(MAX_COTE, base + 0.05))

    if sh >= 3: return _r(min(MAX_COTE, base + 0.15))
    if sh == 2: return _r(min(MAX_COTE, base + 0.10))
    if sh == 1: return _r(min(MAX_COTE, base + 0.05))

    return _r(base)


# ============================================================
#  ALGORITHME ADAPTATIF : MISE
# ============================================================

def _adaptive_mise(cote: float, boost: bool = False) -> int:
    """
    Mise inversement proportionnelle à la cote.
    boost=True → montant doublé (principe martingale sur série basse ≥ 4).
    """
    t = (cote - MIN_COTE) / (MAX_COTE - MIN_COTE)
    t = max(0.0, min(1.0, t))
    mise_raw = MAX_MISE - (MAX_MISE - MIN_MISE) * t
    mise = max(MIN_MISE, min(MAX_MISE, round(mise_raw / MISE_STEP) * MISE_STEP))
    if boost:
        mise = round((mise * 2) / MISE_STEP) * MISE_STEP
    return mise


# ============================================================
#  ANALYSE — retourne un seul dictionnaire
# ============================================================

def analyze(data) -> dict:
    values = [float(d['value']) for d in data if d.get('value') is not None]
    n = len(values)

    if n == 0:
        return {
            'is_valid': False,
            'nombre_total': 0,
            'dernier_multiplicateur': None,
            'taux_gains_faibles':  "0%",
            'taux_gains_moyens':   "0%",
            'taux_gains_elevés':   "0%",
            'tendance_recente':    "INCONNUE",
            'historique_recent':   [],
            'historique_etendu':   [],
        }

    pct_high = round(sum(1 for v in values if v >= 2.0)       / n * 100, 1)
    pct_mid  = round(sum(1 for v in values if 1.5 <= v < 2.0) / n * 100, 1)
    pct_low  = round(sum(1 for v in values if v < 1.5)        / n * 100, 1)

    last5  = values[:5]
    last20 = values[:20]

    bonus_5 = sum(1 for v in last5 if v >= 2.0)
    if   bonus_5 >= 4: tendance = "HAUSSE"
    elif bonus_5 <= 1: tendance = "BAISSE"
    else:              tendance = "STABLE"

    return {
        'is_valid':            True,
        'nombre_total':        n,
        'dernier_multiplicateur': values[0],
        'taux_gains_faibles':  f"{pct_low}%",
        'taux_gains_moyens':   f"{pct_mid}%",
        'taux_gains_elevés':   f"{pct_high}%",
        'tendance_recente':    tendance,
        'historique_recent':   last5,
        'historique_etendu':   last20,
    }


# ============================================================
#  GÉNÉRATION DE LA MISE — algorithme adaptatif
# ============================================================

def generate_mise(analysis: dict) -> dict:
    """
    Algorithme adaptatif basé sur les 20 dernières valeurs.

    Règles :
    - Série de valeurs basses (< 2.0) → cote basse, mise élevée
    - Série de valeurs hautes (≥ 2.0) → cote haute, mise faible
    - Pas de série nette → basé sur la moyenne glissante des 10 derniers

    Mise : inversement proportionnelle à la cote cible.
    """
    etendu = analysis.get('historique_etendu', [])
    recent = analysis.get('historique_recent', [])
    values = etendu if etendu else recent

    if not analysis.get('is_valid') or len(recent) < 5:
        return {
            'cote':         0,
            'mise':         0,
            'is_ready':     False,
            'raison':       'Données insuffisantes (< 5 valeurs)',
            'streak_low':   0,
            'streak_high':  0,
            'moyenne_10':   0.0,
            'spike':        False,
        }

    # ── Détection du pic sur la valeur la plus récente ──────────────────
    last_val      = values[0] if values else 0.0
    context_vals  = values[1:11]                          # les 10 suivantes comme référence
    spike_detected = _is_spike(last_val, context_vals)

    if spike_detected:
        m10_clean = _rolling_mean(values[1:], 10)
        return {
            'cote':        0,
            'mise':        0,
            'is_ready':    False,
            'raison':      f"Pic détecté ({last_val}x) — ce tour ignoré, récupération au prochain",
            'streak_low':  0,
            'streak_high': 0,
            'moyenne_10':  m10_clean,
            'spike':       True,
        }

    # ── Récupération post-pic : montée progressive ───────────────────────
    rss = _rounds_since_last_spike(values)
    if rss is not None and 1 <= rss <= 4:
        rec_cote = _RECOVERY_COTES[rss]
        rec_mise = _RECOVERY_MISES[rss]
        m10_clean = _rolling_mean([v for v in values if not _is_spike(v, values)], 10)
        return {
            'cote':        rec_cote,
            'mise':        rec_mise,
            'is_ready':    True,
            'raison':      f"Récupération post-pic tour {rss}/4 → cote {rec_cote}x, mise {rec_mise}F",
            'streak_low':  0,
            'streak_high': 0,
            'moyenne_10':  m10_clean,
            'spike':       False,
            'recovery':    True,
        }

    # ── Analyse normale : filtrer tous les pics de l'historique ─────────
    values_clean = [v for v in values if not _is_spike(v, values)]
    if len(values_clean) < 5:
        values_clean = values                             # fallback si trop filtrés

    sl    = _streak_low(values_clean)
    sh    = _streak_high(values_clean)
    m10   = _rolling_mean(values_clean, 10)
    cote  = _adaptive_cote(values_clean)

    # ── Règle d'attente : 3 valeurs basses → passer son tour ────────────
    if sl == 3:
        return {
            'cote':        0,
            'mise':        0,
            'is_ready':    False,
            'raison':      f"3 valeurs basses de suite — attente du 4e ou 5e tour avant de miser",
            'streak_low':  sl,
            'streak_high': sh,
            'moyenne_10':  m10,
            'spike':       False,
        }

    boost = sl >= 4           # boost uniquement à partir du 4e tour bas
    mise  = _adaptive_mise(cote, boost=boost)

    if sl >= 4:
        raison = f"{sl} résultat(s) sous {THRESHOLD}x de suite → BOOST x2 ({mise}F)"
    elif sl > 0:
        raison = f"{sl} résultat(s) sous {THRESHOLD}x de suite → cote conservatrice, mise ↑"
    elif sh > 0:
        raison = f"{sh} résultat(s) à {THRESHOLD}x+ de suite → cote prudente, mise ↓"
    else:
        raison = f"Moy(10)={m10}x → cote et mise calculées"

    # ── Slot 2 : super multiplicateur ───────────────────────────────────
    # Activé quand série basse ≥ SLOT2_MIN_STREAK (signal de grand retournement)
    slot2_ready = sl >= SLOT2_MIN_STREAK
    slot2_cote  = SLOT2_COTE_HIGH if sl >= 6 else SLOT2_COTE_MED
    slot2_mise  = SLOT2_MISE if slot2_ready else 0

    return {
        'cote':         cote,
        'mise':         mise,
        'is_ready':     True,
        'raison':       raison,
        'streak_low':   sl,
        'streak_high':  sh,
        'moyenne_10':   m10,
        'spike':        False,
        'slot2_ready':  slot2_ready,
        'slot2_cote':   slot2_cote,
        'slot2_mise':   slot2_mise,
    }
