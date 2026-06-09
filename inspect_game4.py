"""Diagnostic: check if user is actually logged in and if casino is accessible."""
import asyncio, json
from playwright.async_api import async_playwright

COOKIES_PATH = "/tmp/betclic_robot/cookies.json"

async def main():
    with open(COOKIES_PATH) as f:
        cookies = json.load(f)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--headless=new", "--no-sandbox", "--disable-gpu"],
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        await ctx.add_cookies(cookies)
        page = await ctx.new_page()

        # Check login status
        print("--- Checking login status ---")
        await page.goto("https://www.betclic.fr/", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(3000)

        body_text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
        print(f"Body preview:\n{body_text}")

        # Check for logged-in indicators
        has_deconnexion = "Déconnexion" in body_text or "deconnexion" in body_text
        has_mon_compte = "Mon compte" in body_text or "mon compte" in body_text
        has_solde = "solde" in body_text.lower() or "balance" in body_text.lower()
        print(f"\nLogged-in indicators:")
        print(f"  Déconnexion: {has_deconnexion}")
        print(f"  Mon compte: {has_mon_compte}")
        print(f"  Solde: {has_solde}")

        # Check cookies that were actually set
        current_cookies = await ctx.cookies()
        print(f"\nActive cookies ({len(current_cookies)}):")
        for c in current_cookies:
            if 'betclic' in c.get('domain', ''):
                print(f"  {c['domain']} | {c['name']} = {c['value'][:40]}...")

        # Try various casino URLs
        casino_urls = [
            "https://www.betclic.fr/casino",
            "https://www.betclic.fr/casino/games",
            "https://casino.betclic.fr/",
        ]

        for url in casino_urls:
            print(f"\n--- Trying: {url} ---")
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)
            print(f"  Final URL: {page.url}")
            print(f"  Title: {await page.title()}")
            body = await page.evaluate("() => document.body.innerText.substring(0, 200)")
            print(f"  Body: {body[:200]}")

        await browser.close()

asyncio.run(main())
