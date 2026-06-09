from datetime import datetime
from modules.example_site import ExampleSiteBot, SessionExpiredError
from core.browser import BrowserManager
from core.logger import get_logger
import asyncio
import os
from dotenv import load_dotenv

from services.analyze import analyze, generate_mise
from services.notify_bot import TelegramNotifier
from services.storage import MultiplierStore
from services.report import generate_session_chart

load_dotenv(".env")

log = get_logger("bot.service")

USERNAME = os.getenv("USERNAME")
PASSWORD = os.getenv("PASSWORD")
GAME_URL = os.getenv("GAME_URL")
DATE_OF_BIRTH = os.getenv("DATE_OF_BIRTH")
DATABASE_PATH = os.getenv("DATABASE_PATH", "data/bot.db")
TELEGRAM_API_URL = os.getenv("TELEGRAM_API_URL")
TELEGRAM_API_KEY = os.getenv("TELEGRAM_API_KEY")
TELEGRAM_BOT_NAME = os.getenv("TELEGRAM_BOT_NAME")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

MAX_REAUTH_ATTEMPTS = 3
REPORT_EVERY_N_BETS = 5


class BotService:
    def __init__(self):
        self.browser = BrowserManager()
        self.store = MultiplierStore(DATABASE_PATH)

    async def run(self):
        log.info("=== Démarrage du bot ===")
        await self.browser.start()
        log.info("Navigateur démarré")

        page = await self.browser.new_page()
        bot = ExampleSiteBot(page)
        log.info("Instance bot créée")

        async with TelegramNotifier(
            chat_id=TELEGRAM_CHAT_ID,
            url=f"{TELEGRAM_API_URL}{TELEGRAM_API_KEY}/sendMessage",
        ) as notifier:
            await bot.ensure_logged_in(USERNAME, PASSWORD, DATE_OF_BIRTH)
            await bot.open_game(GAME_URL)

            log.info("Premier scrape des multiplicateurs")
            multipliers = await bot.get_multipliers()
            saved = self.store.save_multipliers(multipliers)
            log.info("%d nouveaux multiplicateurs sauvegardés en base", saved)
            reauth_attempts = 0
            bet_count = 0

            log.info("=== Boucle principale démarrée ===")
            while True:
                try:
                    analysis = analyze(multipliers)
                    mise = generate_mise(analysis)

                    log.info(
                        "Analyse — tendance=%s | dernier=%.2f | cote=%.2f | mise=%d FCFA | prêt=%s",
                        analysis["tendance_recente"],
                        analysis["dernier_multiplicateur"],
                        mise["cote"],
                        mise["mise"],
                        mise["is_ready"],
                    )

                    ancienne_cote = (
                        analysis["historique_recent"][1]
                        if len(analysis.get("historique_recent", [])) > 1
                        else "N/A"
                    )

                    await notifier.envoyer(
                        f"🎯 <b>Nouveau Paris - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n"
                        f"├ Jeu           : Circuit Masters\n"
                        f"├ Tendance      : {analysis['tendance_recente']}\n"
                        f"├ Historique    : {analysis['historique_recent']}\n"
                        f"├ Nouvelle côte : <code>{mise['cote']}</code>\n"
                        f"├ Ancienne côte : <code>{ancienne_cote}</code>\n"
                        f"├ Mise suggérée : <code>{mise['mise']} FCFA</code>\n"
                        f"├ Décision      : {'✅ OPPORT. À SAISIR' if mise['is_ready'] else '⛔ RISQUE ÉLEVÉ'}\n"
                        f"│\n"
                        f"├ ⚠️ Remarque :\n"
                        f"├ Analyse basée sur des probabilités \n"
                        f"├ statistiques. Les résultats restent \n"
                        f"├ imprévisibles (RNG) les résultats \n"
                        f"└ Gérer votre mise avec prudence\n"
                    )

                    cote_jouee = mise["cote"]
                    voulait_miser = mise["is_ready"]
                    montant_mise = mise["mise"]
                    pari_place = False

                    if voulait_miser:
                        pari_place = await bot.place_bet(montant_mise, cote_jouee)
                        if not pari_place:
                            log.warning("Pari non placé — on continue sans mise cette partie")

                    last_raw = multipliers[0]["raw"] if multipliers else ""
                    await bot.wait_for_new_result(last_raw)

                    multipliers = await bot.get_multipliers()
                    saved = self.store.save_multipliers(multipliers)
                    log.info("%d nouveaux multiplicateurs sauvegardés en base", saved)
                    bet_count += 1
                    reauth_attempts = 0

                    result_value = float(multipliers[0]["value"]) if multipliers else None
                    if result_value is not None and voulait_miser:
                        log.info(
                            "Résultat — valeur=%.2f | cote=%.2f | placé=%s",
                            result_value, cote_jouee, pari_place,
                        )
                        if not pari_place:
                            await notifier.envoyer(
                                f"⚠️ <b>Pari non placé</b>\n"
                                f"├ Résultat sorti : <code>{result_value}x</code>\n"
                                f"├ Cote visée     : <code>{cote_jouee}x</code>\n"
                                f"└ Le bot n'a pas pu miser à temps"
                            )
                        else:
                            won = result_value >= cote_jouee
                            gain_brut = round(montant_mise * cote_jouee)
                            benefice  = gain_brut - montant_mise
                            if won:
                                await notifier.envoyer(
                                    f"✅ <b>GAGNÉ !</b>\n"
                                    f"├ Résultat sorti : <code>{result_value}x</code>\n"
                                    f"├ Cote jouée     : <code>{cote_jouee}x</code>\n"
                                    f"├ Mise           : <code>{montant_mise} FCFA</code>\n"
                                    f"├ Gain brut      : <code>+{gain_brut} FCFA</code>\n"
                                    f"└ Bénéfice net   : <code>+{benefice} FCFA</code>"
                                )
                            else:
                                await notifier.envoyer(
                                    f"❌ <b>PERDU</b>\n"
                                    f"├ Résultat sorti : <code>{result_value}x</code>\n"
                                    f"├ Cote jouée     : <code>{cote_jouee}x</code>\n"
                                    f"├ Mise           : <code>{montant_mise} FCFA</code>\n"
                                    f"└ Perte          : <code>-{montant_mise} FCFA</code>"
                                )

                    if bet_count % REPORT_EVERY_N_BETS == 0:
                        log.info("Génération du graphe toutes les %d parties (n°%d)", REPORT_EVERY_N_BETS, bet_count)
                        image_bytes, caption = generate_session_chart(multipliers, bet_count, history=30)
                        await notifier.envoyer_photo(image_bytes, caption)

                except SessionExpiredError as e:
                    reauth_attempts += 1
                    log.warning(
                        "Session expirée (tentative %d/%d) : %s",
                        reauth_attempts, MAX_REAUTH_ATTEMPTS, e,
                    )

                    if reauth_attempts > MAX_REAUTH_ATTEMPTS:
                        log.error(
                            "Impossible de restaurer la session après %d tentatives — arrêt",
                            MAX_REAUTH_ATTEMPTS,
                        )
                        raise RuntimeError(
                            f"Impossible de restaurer la session après {MAX_REAUTH_ATTEMPTS} tentatives."
                        ) from e

                    await bot.refresh_session(USERNAME, PASSWORD, DATE_OF_BIRTH, GAME_URL)
                    multipliers = await bot.get_multipliers()
                    saved = self.store.save_multipliers(multipliers)
                    log.info("%d nouveaux multiplicateurs sauvegardés en base après reconnexion", saved)
