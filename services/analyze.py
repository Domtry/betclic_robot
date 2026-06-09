import numpy as np

# ============================================================
#  CONFIGURATION
# ============================================================
THRESHOLD = 2.0
WIN_SHORT = 5
WIN_LONG  = 15
WIN_RATE  = 10
 
 
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
            'taux_gains_faibles': "0%",
            'taux_gains_moyens': "0%",
            'taux_gains_elevés': "0%",
            'tendance_recente': "INCONNUE",
            'historique_recent': [],
        }
 
    pct_high = round(sum(1 for v in values if v >= 2.0)       / n * 100, 1)
    pct_mid  = round(sum(1 for v in values if 1.5 <= v < 2.0) / n * 100, 1)
    pct_low  = round(sum(1 for v in values if v < 1.5)        / n * 100, 1)
 
    last5   = values[:5]
    bonus_5 = sum(1 for v in last5 if v >= 2.0)
 
    if   bonus_5 >= 4: tendance = "HAUSSE"
    elif bonus_5 <= 1: tendance = "BAISSE"
    else:              tendance = "STABLE"
 
    return {
        'is_valid': True,
        'nombre_total': n,
        'dernier_multiplicateur': values[0],

        'taux_gains_faibles': f"{pct_low}%",        # < 1.5x
        'taux_gains_moyens': f"{pct_mid}%",         # 1.5x - 2x
        'taux_gains_elevés': f"{pct_high}%",        # > 2x

        'tendance_recente': tendance,
        'historique_recent': last5
    }
    

# ============================================================
#  GENERATION DE LA MISE — retourne un seul dictionnaire
# ============================================================
def generate_mise(analysis: dict) -> dict:
    cote = 0
    mise = 0
    
    historic = analysis.get('historique_recent', [])
    if not analysis.get('is_valid', True) or len(historic) < WIN_SHORT:
        return {
            "cote": 0,
            "mise": 0,
            "is_ready": False,
        }

    if analysis['tendance_recente'] == 'BAISSE' :
        variance = min(historic)
        if variance > 1.3:
            cote = 2
            
    if analysis['tendance_recente'] == 'HAUSSE':
        variance = max(historic)
        if variance > 2:
            cote = 1.2
            
    if analysis['tendance_recente'] == 'STABLE':
        variance = max(historic) - min(historic)
        if variance > 0.5:
            cote = 1.1
            
    # Virifier que les quatre dernières valeurs sont toutes inferieure a 2.0
    if all(v < THRESHOLD for v in historic):
        return {
            "cote": 2.5,
            "mise": 100,
            "is_ready": True
        }

    if all(v >= THRESHOLD for v in historic):
        return {
            "cote": 0,
            "mise": 0,
            "is_ready": False
        }

    if cote >= 1.1:
        mise = 100
    else:
        mise = 0

    return {
        "cote": cote,
        "mise": mise,
        "is_ready": mise > 0
    }