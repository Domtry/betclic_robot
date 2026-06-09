"""Diagnostic: inspect game page after login to find actual game elements."""
import asyncio, json
from playwright.async_api import async_playwright

COOKIES_PATH = "/tmp/betclic_robot/cookies.json"
GAME_URL = "https://www.betclic.fr/casino/games/b116cce2-f645-47af-a290-f2cf297249dc/play?mode=1"

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

        print(f"Navigating to game: {GAME_URL}")
        resp = await page.goto(GAME_URL, wait_until="domcontentloaded", timeout=30000)
        print(f"Status: {resp.status if resp else 'None'}")
        print(f"Final URL: {page.url}")
        print(f"Title: {await page.title()}")

        # Wait for game to load
        print("\nWaiting 10s for game to load...")
        await page.wait_for_timeout(10000)

        # Check frames
        print(f"\nFrames ({len(page.frames)}):")
        for i, f in enumerate(page.frames):
            print(f"  [{i}] URL: {f.url[:150]}")

        # Check for game elements in ALL frames
        game_selectors = [
            "#button_go", "#button_sound", "#inGame-history",
            ".inGame-history-values", ".multiplier-high", ".multiplier-medium",
            "[class*='button_go']", "[class*='button_sound']",
            "[class*='inGame']", "[class*='multiplier']",
            "[class*='game']", "[class*='crash']", "[class*='circuit']",
            "canvas", "iframe", "[id*='game']", "[class*='slot']",
            "[class*='spinner']", "[class*='wheel']",
        ]

        for i, source in enumerate([page] + list(page.frames)):
            found = False
            for sel in game_selectors:
                try:
                    count = await source.locator(sel).count()
                    if count > 0:
                        if not found:
                            print(f"\n  Frame [{i}] ({source.url[:80]}):")
                            found = True
                        visible = False
                        try:
                            visible = await source.locator(sel).first.is_visible()
                        except:
                            pass
                        print(f"    '{sel}': count={count}, visible={visible}")
                except:
                    pass

        # Dump all IDs and classes from the page
        all_ids = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('[id]')).map(el => el.id).filter(id => id.length > 0 && id.length < 60);
        }""")
        print(f"\nAll element IDs on main page ({len(all_ids)}):")
        for eid in sorted(set(all_ids)):
            print(f"  #{eid}")

        # Check for iframes
        iframes = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('iframe')).map(f => ({
                src: f.src.substring(0, 150),
                id: f.id,
                className: f.className.substring(0, 80),
            }));
        }""")
        print(f"\nIframes ({len(iframes)}):")
        for iframe in iframes:
            print(f"  {iframe}")

        # Get a snippet of the page body
        body = await page.evaluate("() => document.body.innerText.substring(0, 500)")
        print(f"\nBody text:\n{body}")

        await browser.close()

asyncio.run(main())
