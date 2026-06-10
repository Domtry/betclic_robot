from datetime import datetime, timedelta
from modules.example_site import ExampleSiteBot, SessionExpiredError
from core.browser import BrowserManager
from core.logger import get_logger
import asyncio
import html
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

MAX_REAUTH_ATTEMPTS  = 3
REPORT_EVERY_N_BETS  = 5


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
            multipliers = None
            for attempt in range(1, 6):
                try:
                    multipliers = await bot.get_multipliers()
                    break
                except RuntimeError as e:
                    log.warning("get_multipliers échoué (tentative %d/5) : %s", attempt, e)
                    if attempt < 5:
                        await asyncio.sleep(3)
                    else:
                        raise
            saved = self.store.save_multipliers(multipliers)
            log.info("%d nouveaux multiplicateurs sauvegardés en base", saved)
            reauth_attempts = 0
            bet_count       = 0

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

                    solde = await bot.get_balance()

                    slot2_info = (
                        f"├ Slot 2        : <code>{mise['slot2_cote']}x</code> — {mise['slot2_mise']} FCFA\n"
                        if mise.get("slot2_ready") else ""
                    )

                    await notifier.envoyer(
                        f"🎯 <b>Nouveau Paris — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</b>\n"
                        f"├ Jeu           : Circuit Masters\n"
                        f"├ 💰 Solde       : <b>{html.escape(solde, quote=False)}</b>\n"
                        f"├ Tendance      : {html.escape(analysis['tendance_recente'], quote=False)}\n"
                        f"├ Historique(5) : {html.escape(str(analysis['historique_recent']), quote=False)}\n"
                        f"├─────────────────────────\n"
                        f"├ Cote cible    : <code>{mise['cote']}x</code>\n"
                        f"├ Mise          : <code>{mise['mise']} FCFA</code>\n"
                        f"{slot2_info}"
                        f"├ Série basse   : {mise['streak_low']} consécutif(s)\n"
                        f"├ Série haute   : {mise['streak_high']} consécutif(s)\n"
                        f"├ Moy(10)       : <code>{mise['moyenne_10']}x</code>\n"
                        f"├ Raison        : {html.escape(mise['raison'], quote=False)}\n"
                        f"├─────────────────────────\n"
                        + (f"├ ⚠️ PIC IGNORÉ — mise réduite au minimum\n" if mise.get('spike') else "")
                        + f"└ Décision : {'✅ PARI PLACÉ' if mise['is_ready'] else '⛔ AUCUN PARI'}\n"
                    )

                    cote_jouee    = mise["cote"]
                    voulait_miser = mise["is_ready"]
                    montant_mise  = mise["mise"]
                    pari_place    = False
                    pari_place_s2 = False

                    if voulait_miser:
                        try:
                            pari_place = await asyncio.wait_for(
                                bot.place_bet(montant_mise, cote_jouee, slot=1),
                                timeout=100,
                            )
                        except asyncio.TimeoutError:
                            log.warning("place_bet slot1 timeout (100s) — pari ignoré")
                            pari_place = False
                        if not pari_place:
                            log.warning("Slot 1 : pari non placé")

                    # Slot 2 — super multiplicateur (skip_phase_wait : déjà dans la phase)
                    if mise.get("slot2_ready"):
                        s2_cote = mise["slot2_cote"]
                        s2_mise = mise["slot2_mise"]
                        log.info("Slot 2 : super-mult @%.1fx mise=%dF", s2_cote, s2_mise)
                        try:
                            pari_place_s2 = await asyncio.wait_for(
                                bot.place_bet(s2_mise, s2_cote, slot=2, skip_phase_wait=True),
                                timeout=20,
                            )
                        except asyncio.TimeoutError:
                            log.warning("place_bet slot2 timeout (20s) — ignoré")
                        if pari_place_s2:
                            log.info("Slot 2 confirmé : %dF @ %.1fx", s2_mise, s2_cote)

                    last_raw = multipliers[0]["raw"] if multipliers else ""
                    try:
                        await asyncio.wait_for(
                            bot.wait_for_new_result(last_raw),
                            timeout=180,
                        )
                    except asyncio.TimeoutError:
                        raise RuntimeError("wait_for_new_result timeout (180s) — frame probablement invalide")

                    multipliers = await bot.get_multipliers()
                    saved = self.store.save_multipliers(multipliers)
                    log.info("%d nouveaux multiplicateurs sauvegardés en base", saved)
                    bet_count += 1
                    reauth_attempts = 0

                    result_value = float(multipliers[0]["value"]) if multipliers else None
                    if result_value is not None and voulait_miser:
                        solde_apres = await bot.get_balance()
                        log.info(
                            "Résultat — valeur=%.2f | cote=%.2f | placé=%s | solde=%s",
                            result_value, cote_jouee, pari_place, solde_apres,
                        )
                        if not pari_place:
                            await notifier.envoyer(
                                f"⚠️ <b>Pari non placé</b>\n"
                                f"├ Résultat sorti : <code>{result_value}x</code>\n"
                                f"├ Cote visée     : <code>{cote_jouee}x</code>\n"
                                f"├ 💰 Solde        : <b>{html.escape(solde_apres, quote=False)}</b>\n"
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
                                    f"├ Bénéfice net   : <code>+{benefice} FCFA</code>\n"
                                    f"└ 💰 Solde        : <b>{html.escape(solde_apres, quote=False)}</b>"
                                )
                            else:
                                await notifier.envoyer(
                                    f"❌ <b>PERDU</b>\n"
                                    f"├ Résultat sorti : <code>{result_value}x</code>\n"
                                    f"├ Cote jouée     : <code>{cote_jouee}x</code>\n"
                                    f"├ Mise           : <code>{montant_mise} FCFA</code>\n"
                                    f"├ Perte          : <code>-{montant_mise} FCFA</code>\n"
                                    f"└ 💰 Solde        : <b>{html.escape(solde_apres, quote=False)}</b>"
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

                except RuntimeError as e:
                    # Frame Darwin invalide ou jeu déconnecté — réouverture sans reconnexion
                    log.warning("Erreur jeu : %s — tentative de réouverture...", e)
                    try:
                        await bot.open_game(GAME_URL)
                        multipliers = await bot.get_multipliers()
                        saved = self.store.save_multipliers(multipliers)
                        log.info("Jeu réouvert — %d multiplicateurs récupérés, reprise de la boucle", saved)
                    except SessionExpiredError:
                        log.warning("Session expirée lors de la réouverture — reconnexion complète")
                        await bot.refresh_session(USERNAME, PASSWORD, DATE_OF_BIRTH, GAME_URL)
                        multipliers = await bot.get_multipliers()
                        saved = self.store.save_multipliers(multipliers)
                        log.info("%d multiplicateurs récupérés après reconnexion", saved)
                    except Exception as reopen_err:
                        log.error("Impossible de rouvrir le jeu : %s — arrêt", reopen_err)
                        raise
