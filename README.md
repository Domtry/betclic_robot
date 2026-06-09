# Betclic Robot

Bot d'observation Betclic/Circuit Masters avec :

- scraping Playwright des multiplicateurs ;
- stockage SQLite des résultats observés ;
- analyse statistique prudente ;
- génération de rapport quotidien avec graphique PNG ;
- notification Telegram.

> ⚠️ Important : ce projet ne garantit aucun gain. Les jeux RNG/casino restent imprévisibles. Les prédictions fournies sont uniquement des signaux statistiques descriptifs.

## Installation

```bash
uv sync --frozen
uv run playwright install chromium
```

## Variables d'environnement

Créer un fichier `.env` :

```env
USERNAME=ton_identifiant
PASSWORD=ton_mot_de_passe
DATE_OF_BIRTH=JJ/MM/AAAA
GAME_URL=https://...
DATABASE_PATH=data/bot.db
TELEGRAM_API_URL=https://api.telegram.org/bot
TELEGRAM_API_KEY=xxx
TELEGRAM_CHAT_ID=xxx
```

## Lancer le bot

```bash
uv run python main.py
```

Le bot enregistre les multiplicateurs dans `data/bot.db`.

## Générer le rapport quotidien

```bash
uv run python daily_report.py
```

Pour une date précise :

```bash
uv run python daily_report.py --day 2026-01-01
```

Sorties :

- `reports/multipliers_YYYY-MM-DD.png`
- `reports/summary_YYYY-MM-DD.txt`

## Automatiser chaque jour avec cron

Exemple : générer le rapport chaque soir à 23h55.

```bash
55 23 * * * cd /chemin/vers/betclic_robot && uv run python daily_report.py >> reports/cron.log 2>&1
```

## Générer un rapport horaire

Vous pouvez également générer un rapport pour l'heure courante :

```bash
uv run python hourly_report.py
```

Pour une heure précise :

```bash
uv run python hourly_report.py --hour 2026-06-04 15
```

## Automatiser un rapport toutes les heures avec cron

Exemple : exécuter le script à chaque début d'heure.

```bash
0 * * * * cd /chemin/vers/betclic_robot && uv run python hourly_report.py >> reports/hourly_cron.log 2>&1
```

## Tests

```bash
uv run pytest -q
```

## Règles de prudence

- Ne pas activer d'auto-bet sans backtest solide.
- Ne jamais miser une somme nécessaire à la vie quotidienne.
- Toujours utiliser une limite de perte.
- Considérer les prédictions comme des observations, pas comme des certitudes.
