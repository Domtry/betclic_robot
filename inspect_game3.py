"""Diagnostic: navigate to game page with existing cookies loaded."""
import asyncio, json
from playwright.async_api import async_playwright

COOKIES_PATH = "/tmp/betclic_robot/cookies.json"
GAME_URL = "https://www.betclic.ci/casino/games/b116cce2-f645-47af-a290-f2cf297249dc/play?mode=1"
GAME_URL_FR = "https://www.betclic.fr/casino/games/b116cce2-f645-47af-a290-f2cf297249dc/play?mode=1"

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

        # Load cookies
        await ctx.add_cookies(cookies)
        print(f"Loaded {len(cookies)} cookies")

        page = await ctx.new_page()

        # First verify login
        print("\n--- Step 1: Verify login ---")
        await page.goto("https://www.betclic.fr/", wait_until="domcontentloaded", timeout=15000)
        await page.wait_for_timeout(2000)
        print(f"After login check - URL: {page.url}")

        # Now try the game URL
        print(f"\n--- Step 2: Navigate to game (.ci URL) ---")
        resp = await page.goto(GAME_URL, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_timeout(5000)
        print(f"Status: {resp.status if resp else 'None'}")
        print(f"Final URL: {page.url}")
        print(f"Title: {await page.title()}")

        if page.url != "https://www.betclic.fr/":
            print("SUCCESS - Not redirected to homepage!")
            # Check for game elements
            for source in [page] + list(page.frames):
                print(f"\n  Frame URL: {source.url[:100]}")
                for sel in ["#button_go", "#button_sound", "#inGame-history", ".inGame-history-values", "canvas", "[class*='game']", "[class*='casino']", "[class*='slot']"]:
                    try:
                        count = await source.locator(sel).count()
                        if count > 0:
                            visible = await source.locator(sel).first.is_visible()
                            print(f"    '{sel}': count={count}, first visible={visible}")
                    except:
                        pass
        else:
            print("FAILED - Redirected back to homepage")
            print("\n--- Step 3: Try .fr URL directly ---")
            resp2 = await page.goto(GAME_URL_FR, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(5000)
            print(f"Status: {resp2.status if resp2 else 'None'}")
            print(f"Final URL: {page.url}")
            print(f"Title: {await page.title()}")

            if page.url != "https://www.betclic.fr/":
                print("SUCCESS!")
                for source in [page] + list(page.frames):
                    print(f"\n  Frame URL: {source.url[:100]}")
                    for sel in ["#button_go", "#button_sound", "#inGame-history", ".inGame-history-values", "canvas"]:
                        try:
                            count = await source.locator(sel).count()
                            if count > 0:
                                visible = await source.locator(sel).first.is_visible()
                                print(f"    '{sel}': count={count}, first visible={visible}")
                        except:
                            pass
            else:
                print("ALSO FAILED - Redirected to homepage")

                # Maybe the game URL format changed - try searching on the site
                print("\n--- Step 4: Search for Circuit Masters ---")
                await page.goto("https://www.betclic.fr/casino", wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(3000)
                print(f"Casino page URL: {page.url}")
                print(f"Casino page title: {await page.title()}")

        await browser.close()

asyncio.run(main())
