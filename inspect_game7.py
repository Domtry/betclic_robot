"""Diagnostic: try to find the correct game URL format on betclic.fr."""
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
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()

        # First, navigate to casino section and find game links
        print("=== Step 1: Navigate to casino ===")
        await page.goto("https://www.betclic.fr/", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(3000)

        # Check if user is logged in
        body = await page.evaluate("() => document.body.innerText.substring(0, 200)")
        print(f"Body: {body[:200]}")
        is_logged = "Déconnexion" in body or "Mon compte" in body
        print(f"Logged in: {is_logged}")

        # Try to find casino/game links
        print("\n=== Step 2: Look for game links ===")
        links = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href]'))
                .map(a => ({href: a.href, text: a.textContent.trim().substring(0, 50)}))
                .filter(a => a.href.includes('game') || a.href.includes('casino') || a.href.includes('crash') || a.href.includes('circuit'));
        }""")
        print(f"Game/casino links found: {len(links)}")
        for link in links[:20]:
            print(f"  {link['href']} | {link['text']}")

        # Try navigating to casino section
        print("\n=== Step 3: Try casino URLs ===")
        casino_urls = [
            "https://www.betclic.fr/casino",
            "https://www.betclic.fr/casino/crash-games",
            "https://www.betclic.fr/casino/crash",
            "https://www.betclic.fr/casino/games/crash",
        ]
        for url in casino_urls:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(2000)
            final = page.url
            redirected = final.rstrip("/") == "https://www.betclic.fr"
            print(f"  {url} -> {final} ({'REDIRECTED' if redirected else 'OK'})")

        # Try the game URL without /casino/ prefix
        print("\n=== Step 4: Try game URL variants ===")
        game_urls = [
            "https://www.betclic.fr/games/b116cce2-f645-47af-a290-f2cf297249dc/play?mode=1",
            "https://www.betclic.fr/games/b116cce2-f645-47af-a290-f2cf297249dc",
            "https://www.betclic.fr/game/b116cce2-f645-47af-a290-f2cf297249dc",
            "https://www.betclic.fr/casino/game/b116cce2-f645-47af-a290-f2cf297249dc",
            "https://www.betclic.fr/casino/crash/b116cce2-f645-47af-a290-f2cf297249dc",
        ]
        for url in game_urls:
            resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
            await page.wait_for_timeout(3000)
            final = page.url
            redirected = final.rstrip("/") == "https://www.betclic.fr"
            print(f"  {url}")
            print(f"    -> {final} ({'REDIRECTED' if redirected else 'OK'})")

            if not redirected:
                # Check for game elements
                for sel in ["#button_go", "#button_sound", "#inGame-history", "canvas"]:
                    try:
                        count = await page.locator(sel).count()
                        if count > 0:
                            print(f"    FOUND '{sel}': {count}")
                    except:
                        pass

        await browser.close()

asyncio.run(main())
