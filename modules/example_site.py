import asyncio
import json
import os
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from core.logger import get_logger

log = get_logger("bot.site")


class SessionExpiredError(Exception):
    """Levée quand le site redirige vers la page de login pendant le scraping."""


class ExampleSiteBot:
    COOKIES_PATH = "cookies.json"
    BASE_URL = "https://www.betclic.ci/"
    LOGIN_URL = f"{BASE_URL}connexion"

    _JS_GET_MULTIPLIERS = """
        () => {
            const container = document.querySelector('#inGame-history');
            if (!container) return null;
            const elements = container.querySelectorAll('.inGame-history-values');
            if (!elements.length) return null;
            return Array.from(elements)
                .filter(el => el.textContent && el.textContent.includes('x'))
                .map((el, i) => ({
                    index: i,
                    raw: el.textContent.trim(),
                    value: parseFloat(
                        el.textContent.trim().replace(',', '.').replace('x', '')
                    ),
                    level: el.classList.contains('multiplier-high') ? 'high'
                         : el.classList.contains('multiplier-medium') ? 'medium'
                         : 'low'
                }));
        }
    """

    _JS_WAIT_NEW_RESULT = """
        (lastRaw) => {
            const first = document.querySelector(
                '#inGame-history .inGame-history-values'
            );
            return !!first && first.textContent.trim() !== lastRaw;
        }
    """

    _USERNAME_SELECTORS = [
        'input[autocomplete="username"]',
        'input[data-qa="username"]',
        'input[name="username"]',
        'input[type="email"]',
        'input[name="email"]',
        'input[autocomplete="email"]',
    ]
    _PASSWORD_SELECTORS = [
        'input[data-qa="password"]',
        'input[type="password"]',
        'input[autocomplete="current-password"]',
        'input[name="password"]',
    ]

    def __init__(self, page):
        self.page = page
        self.context = page.context
        self._active_source = None
        self._session_expired = asyncio.Event()
        self._logging_in = False

        page.on("framenavigated", self._on_frame_navigated)

    def _on_frame_navigated(self, frame):
        """Signale l'expiration seulement hors phase de login intentionnel."""
        if self._logging_in:
            return
        if frame == self.page.main_frame and "/connexion" in frame.url:
            log.warning("Redirection vers /connexion détectée — session expirée")
            self._session_expired.set()

    # ------------------------------------------------------------------
    # Session — détection et récupération
    # ------------------------------------------------------------------

    async def is_session_expired(self) -> bool:
        if self._session_expired.is_set():
            return True
        if "/connexion" in self.page.url:
            log.warning("URL contient /connexion — session marquée expirée")
            self._session_expired.set()
            return True
        try:
            await self.page.locator("text=Connexion").wait_for(state="visible", timeout=1500)
            log.warning("Bouton 'Connexion' visible — session expirée")
            self._session_expired.set()
            return True
        except PlaywrightTimeoutError:
            return False

    async def refresh_session(self, username: str, password: str, date_of_birth: str, game_url: str):
        log.info("Session expirée — nettoyage et reconnexion...")
        self._active_source = None

        await self._clear_session_files()
        await self._login(username, password, date_of_birth)
        await self._save_cookies()
        await self.open_game(game_url)
        log.info("Session restaurée, reprise du scraping")

    async def _clear_session_files(self):
        if os.path.exists(self.COOKIES_PATH):
            os.remove(self.COOKIES_PATH)
            log.info("Fichier cookies.json supprimé")
        await self.context.clear_cookies()
        log.info("Cookies du contexte navigateur purgés")

    # ------------------------------------------------------------------
    # Cookies
    # ------------------------------------------------------------------

    async def _save_cookies(self):
        cookies = await self.context.cookies()
        with open(self.COOKIES_PATH, "w") as f:
            json.dump(cookies, f, indent=2)
        log.info("Cookies sauvegardés (%d entrées)", len(cookies))

    async def _load_cookies(self) -> bool:
        if not os.path.exists(self.COOKIES_PATH):
            log.info("Aucun fichier cookies.json trouvé")
            return False
        try:
            with open(self.COOKIES_PATH, "r") as f:
                cookies = json.load(f)
            if not cookies:
                log.info("Fichier cookies.json vide")
                return False
            await self.context.add_cookies(cookies)
            log.info("Cookies chargés depuis le disque (%d entrées)", len(cookies))
            return True
        except (json.JSONDecodeError, OSError) as e:
            log.error("Impossible de charger les cookies : %s", e)
            return False

    async def _is_logged_in(self) -> bool:
        log.info("Vérification de la session sur %s", self.BASE_URL)
        await self.page.goto(self.BASE_URL, wait_until="domcontentloaded")
        await self.page.wait_for_timeout(2000)

        # Check multiple indicators: absence of login button AND presence of logout/account
        is_logged_in = await self.page.evaluate("""() => {
            const body = document.body.innerText;
            const hasConnexion = body.includes('Connexion');
            const hasDeconnexion = body.includes('Déconnexion') || body.includes('deconnexion');
            const hasMonCompte = body.includes('Mon compte') || body.includes('Mon profil');
            // Return true only if we see logged-in indicators OR definitively no login button
            return {
                hasConnexion,
                hasDeconnexion,
                hasMonCompte,
            };
        }""")

        logged_in = (
            is_logged_in.get("hasDeconnexion") or
            is_logged_in.get("hasMonCompte") or
            not is_logged_in.get("hasConnexion")
        )

        if logged_in:
            log.info("Session active confirmée (déconnexion=%s, monCompte=%s, connexion=%s)",
                     is_logged_in.get("hasDeconnexion"),
                     is_logged_in.get("hasMonCompte"),
                     is_logged_in.get("hasConnexion"))
        else:
            log.info("Non connecté (bouton Connexion visible, aucun indicateur de session active)")

        return logged_in

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------

    async def _find_and_fill(self, selectors: list[str], value: str, per_selector_timeout: int = 8000):
        """Essaye chaque sélecteur avec retries pour absorber les re-renders Angular."""
        for selector in selectors:
            try:
                el = self.page.locator(selector).first
                await el.wait_for(state="visible", timeout=per_selector_timeout)
                await el.click()  # focus avant fill (Angular aime le focus)
                await el.fill(value)
                # Vérifier que la valeur a bien été saisie (Angular two-way binding)
                actual = await el.input_value()
                if actual:
                    log.debug("Champ rempli via sélecteur : %s", selector)
                    return
                log.debug("Fill sur %s n'a pas pris, réessai...", selector)
            except PlaywrightTimeoutError:
                continue
            except Exception as e:
                log.debug("Erreur sur sélecteur %s : %s", selector, e)
                continue
        raise RuntimeError(f"Aucun champ de saisie trouvé parmi : {', '.join(selectors)}")

    async def ensure_logged_in(self, username: str, password: str, date_of_birth: str):
        if await self._load_cookies() and await self._is_logged_in():
            log.info("Session restaurée depuis les cookies")
            return
        log.info("Cookies absents ou expirés — connexion complète requise")
        await self._login(username, password, date_of_birth)
        await self._save_cookies()

    async def _login(self, username: str, password: str, date_of_birth: str):
        self._logging_in = True
        try:
            log.info("Navigation vers la page de connexion")
            await self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")

            # Vérifier qu'on n'a pas été redirigés vers le .fr (ancien bug .ci)
            if "betclic.fr" in self.page.url and "betclic.ci" not in self.LOGIN_URL:
                log.info("Redirection .ci -> .fr détectée, poursuite sur .fr")
            elif "betclic.ci" in self.page.url:
                log.warning("Toujours sur .ci — tentative de navigation directe vers .ci")
                self.LOGIN_URL = "https://www.betclic.ci/casino/connexion"
                await self.page.goto(self.LOGIN_URL, wait_until="domcontentloaded")

            # --- Bannière cookies (tc-privacy-banner Angular) ---
            # Sélecteurs multiples car le texte exact varie
            cookie_selectors = [
                "button:has-text(\"Tout accepter\")",
                "button:has-text(\"Accepter\")",
                "button:has-text(\"Accepter tout\")",
                "button:has-text(\"J'accepte\")",
                "#privacy-cookie-banner button.accept",
                "[class*=privacy] button[class*=accept]",
                "[class*=consent] button[class*=accept]",
            ]
            cookie_closed = False
            for cs in cookie_selectors:
                try:
                    await self.page.locator(cs).first.click(timeout=3000)
                    await self.page.wait_for_timeout(500)
                    log.info("Bannière cookies fermée via : %s", cs)
                    cookie_closed = True
                    break
                except Exception:
                    continue
            if not cookie_closed:
                log.debug("Pas de bannière cookies détectée ou déjà acceptée")

            # --- Attendre qu'Angular ait fini de rendre le formulaire ---
            log.info("Attente du formulaire de connexion...")
            # Fixe un délai minimum pour laisser Angular bootstraper
            await self.page.wait_for_timeout(2000)
            # Attendre que le champ username soit visible (plus fiable que networkidle)
            username_field = self.page.locator('input[autocomplete="username"]').first
            await username_field.wait_for(state="visible", timeout=15000)

            log.info("Remplissage de l'identifiant")
            await self._find_and_fill(self._USERNAME_SELECTORS, username)

            log.info("Remplissage du mot de passe")
            await self._find_and_fill(self._PASSWORD_SELECTORS, password)

            log.info("Soumission du formulaire")
            await self.page.get_by_role("button", name="Connexion", exact=True).click()

            try:
                await self.page.wait_for_selector("text=Saisis ta date de naissance", timeout=5000)
                log.info("Saisie de la date de naissance")
                await self.page.get_by_label("Date de naissance").fill(date_of_birth)
                await self.page.get_by_role("button", name="Valider", exact=True).click()
                await self.page.wait_for_load_state("networkidle")
            except PlaywrightTimeoutError:
                log.debug("Pas de demande de date de naissance")

            log.info("Connexion réussie")
        finally:
            self._logging_in = False
            self._session_expired.clear()

    # ------------------------------------------------------------------
    # Navigation vers le jeu
    # ------------------------------------------------------------------

    async def open_game(self, game_url: str):
        log.info("Navigation vers le jeu : %s", game_url)
        await self.page.goto(game_url, wait_until="domcontentloaded")

        # If redirected to homepage, the session is probably expired or game is unavailable
        current = self.page.url.rstrip("/")
        if current in ("https://www.betclic.ci", "https://www.betclic.fr"):
            log.warning("Redirection vers la page d'accueil — session expirée ou jeu indisponible")
            raise SessionExpiredError(
                f"Redirigé vers l'accueil depuis {game_url} — reconnexion nécessaire"
            )

        await self._handle_game_launch_sequence()
        await self._wait_for_game_ready()
        log.info("Jeu chargé et prêt")
        return self.page

    async def _handle_game_launch_sequence(self, timeout: int = 60_000):
        log.info("Détection de l'état du jeu (bouton_go / button_sound)...")
        interval = 500
        elapsed = 0

        while elapsed < timeout:
            for source in [self.page] + list(self.page.frames):
                # Priorité 1 : écran de bienvenue → cliquer "Aller!" en premier
                try:
                    btn_go = source.locator("#button_go")
                    if await btn_go.count() > 0 and await btn_go.is_visible():
                        log.info("Écran de bienvenue détecté — clic sur 'Aller!'")
                        await btn_go.click()
                        self._active_source = source
                        await source.wait_for_timeout(1000)
                        return
                except Exception:
                    pass

                # Priorité 2 : jeu déjà actif ET pas de #button_go visible
                try:
                    btn_go_count = await source.locator("#button_go").count()
                    btn_go_visible = btn_go_count > 0 and await source.locator("#button_go").is_visible()
                    if not btn_go_visible and await source.locator("#button_sound").count() > 0:
                        if await source.locator("#button_sound").is_visible():
                            log.info("Jeu déjà actif (#button_sound visible, pas d'écran d'accueil)")
                            self._active_source = source
                            return
                except Exception:
                    pass

            await self.page.wait_for_timeout(interval)
            elapsed += interval

        raise RuntimeError("Impossible de lancer le jeu dans le délai imparti (60s)")

    async def _wait_for_game_ready(self):
        log.info("Attente du chargement complet du jeu (#button_sound)...")
        await self.page.wait_for_load_state("domcontentloaded")

        timeout = 30000
        interval = 500
        elapsed = 0

        while elapsed < timeout:
            for source in [self.page] + list(self.page.frames):
                try:
                    btn = source.locator("#button_sound")
                    if await btn.count() > 0:
                        await btn.wait_for(state="visible", timeout=5000)
                        self._active_source = source
                        log.info("Jeu prêt (frame actif mis en cache)")
                        return source
                except Exception:
                    continue

            await self.page.wait_for_timeout(interval)
            elapsed += interval

        raise RuntimeError("Jeu pas encore chargé (#button_sound introuvable après 30s)")

    # ------------------------------------------------------------------
    # Scraping
    # ------------------------------------------------------------------

    async def _get_sources(self):
        if self._active_source is not None:
            return [self._active_source]
        return [self.page] + list(self.page.frames)

    async def get_multipliers(self) -> list[dict]:
        log.debug("Scraping des multiplicateurs...")
        for source in await self._get_sources():
            try:
                result = await source.evaluate(self._JS_GET_MULTIPLIERS)
                if result:
                    if self._active_source is None:
                        self._active_source = source
                    log.info("%d multiplicateurs récupérés", len(result))
                    return result
            except Exception:
                continue

        log.warning("Cache frame périmé — réessai sur toutes les sources")
        self._active_source = None
        for source in [self.page] + list(self.page.frames):
            try:
                result = await source.evaluate(self._JS_GET_MULTIPLIERS)
                if result:
                    self._active_source = source
                    log.info("%d multiplicateurs récupérés (fallback)", len(result))
                    return result
            except Exception:
                continue

        if await self.is_session_expired():
            raise SessionExpiredError("Session expirée lors du scraping des multiplicateurs")

        raise RuntimeError("Multiplicateurs introuvables dans la page et les iframes")

    # ------------------------------------------------------------------
    # Placement automatique de la mise
    # ------------------------------------------------------------------

    async def place_bet(self, mise: int, cote: float, slot: int = 1) -> bool:
        """
        Place un pari pendant la phase de mise.
        mise   : montant en FCFA (ex: 100)
        cote   : multiplicateur d'auto cash-out (ex: 2.0)
        slot   : emplacement de pari (1 ou 2)
        Retourne True si le pari a bien été confirmé.
        """
        source = self._active_source
        if source is None:
            log.warning("place_bet: aucune source active, pari ignoré")
            return False

        btn_id     = f"#button_bet_{slot}"
        input_id   = f"#bet_value_{slot}"
        cb_id      = f"#cash_out_checkbox_{slot}"
        cashout_id = f"#cash_out_input_{slot}"
        cancel_id  = f"#button_cancel_{slot}"

        try:
            # --- 1. Attendre la phase de mise (bouton actif) ---
            log.info("Attente de la phase de mise (%s)...", btn_id)
            await source.wait_for_function(
                f"() => {{ const b = document.querySelector('{btn_id}'); return b && !b.disabled; }}",
                timeout=20_000,
                polling=200,
            )
            log.info("Phase de mise ouverte")

            # --- 2. Montant : via JS pour bypasser les event listeners Django/jQuery ---
            set_ok = await source.evaluate(f"""(val) => {{
                const inp = document.querySelector('{input_id}');
                if (!inp) return false;
                const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                setter.call(inp, val);
                inp.dispatchEvent(new Event('input',  {{ bubbles: true }}));
                inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return inp.value === val;
            }}""", str(mise))
            log.info("Montant fixé via JS : %s (%s)", mise, "OK" if set_ok else "KO")

            # Fallback : fill Playwright si JS n'a pas pris
            if not set_ok:
                bet_input = source.locator(input_id)
                await bet_input.click()
                await self.page.keyboard.press("Control+a")
                await self.page.keyboard.type(str(mise))

            # --- 3. Auto cash-out : activer la checkbox via JS (elle est hidden) ---
            cb_enabled = await source.evaluate(f"""() => {{
                const cb = document.querySelector('{cb_id}');
                if (!cb) return false;
                if (!cb.checked) {{
                    // Clic sur le label associé s'il existe, sinon force le clic
                    const lbl = document.querySelector('label[for="{cb_id}"]')
                           || cb.closest('label')
                           || cb.parentElement;
                    if (lbl) lbl.click();
                    else cb.click();
                    cb.dispatchEvent(new Event('change', {{ bubbles: true }}));
                }}
                return cb.checked;
            }}""")
            log.info("Auto cash-out checkbox : %s", "activée" if cb_enabled else "non trouvée/déjà active")

            # Attendre que l'input cashout devienne visible après la checkbox
            await source.wait_for_timeout(400)

            # --- 4. Cote auto cash-out via JS ---
            cote_str = f"{cote:.2f}"
            cote_ok = await source.evaluate(f"""(val) => {{
                const inp = document.querySelector('{cashout_id}');
                if (!inp) return false;
                const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
                setter.call(inp, val);
                inp.dispatchEvent(new Event('input',  {{ bubbles: true }}));
                inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                return inp.value === val;
            }}""", cote_str)
            log.info("Cote cash-out fixée : %s (%s)", cote_str, "OK" if cote_ok else "KO")

            # Fallback fill
            if not cote_ok:
                cashout_input = source.locator(cashout_id)
                try:
                    await cashout_input.wait_for(state="visible", timeout=2_000)
                    await cashout_input.click()
                    await self.page.keyboard.press("Control+a")
                    await self.page.keyboard.type(cote_str)
                except PlaywrightTimeoutError:
                    log.warning("place_bet: #%s non visible — pari sans auto cash-out", cashout_id)

            # --- 5. Clic sur le bouton MISE ---
            await source.locator(btn_id).click()
            await source.wait_for_timeout(700)

            # --- 6. Vérification : le bouton ANNULER doit apparaître ---
            cancel_visible = await source.locator(cancel_id).is_visible()
            if cancel_visible:
                log.info("Pari confirmé : %d FCFA @ %.2fx (slot %d)", mise, cote, slot)
                return True

            log.warning("place_bet: bouton ANNULER absent après clic — pari non confirmé")
            return False

        except PlaywrightTimeoutError:
            log.warning("place_bet: timeout — phase de mise non atteinte dans les délais")
            return False
        except Exception as e:
            log.error("place_bet: erreur inattendue — %s", e, exc_info=True)
            return False

    # ------------------------------------------------------------------
    # Event-driven — attend le prochain résultat de round
    # ------------------------------------------------------------------

    async def wait_for_new_result(self, last_raw: str, timeout: int = 120_000) -> None:
        log.info("En attente du prochain round (dernier résultat : %s)...", last_raw)
        for source in await self._get_sources():
            try:
                await self._race_wait(source, last_raw, timeout)
                log.info("Nouveau round détecté")
                return
            except SessionExpiredError:
                raise
            except Exception:
                continue

        self._active_source = None
        for source in [self.page] + list(self.page.frames):
            try:
                await self._race_wait(source, last_raw, timeout)
                self._active_source = source
                log.info("Nouveau round détecté (fallback)")
                return
            except SessionExpiredError:
                raise
            except Exception:
                continue

        raise RuntimeError("Impossible d'attendre un nouveau résultat de round")

    async def _race_wait(self, source, last_raw: str, timeout: int) -> None:
        async def _do_wait():
            await source.wait_for_function(
                self._JS_WAIT_NEW_RESULT,
                arg=last_raw,
                timeout=timeout,
                polling=200,
            )

        async def _watch_session():
            await self._session_expired.wait()
            raise SessionExpiredError("Session expirée pendant l'attente du round")

        wait_task = asyncio.create_task(_do_wait())
        session_task = asyncio.create_task(_watch_session())

        done, pending = await asyncio.wait(
            [wait_task, session_task],
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass

        for task in done:
            exc = task.exception()
            if exc is not None:
                raise exc
