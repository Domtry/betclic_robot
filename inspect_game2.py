"""Diagnostic: try to navigate to the game via betclic.fr domain."""
import asyncio
from playwright.async_api import async_playwright

# Try different URL formats
URLS = [
    "https://www.betclic.fr/casino/games/b116cce2-f645-47af-a290-f2cf297249dc/play?mode=1",
    "https://www.betclic.fr/casino/games/b116cce2-f645-47af-a290-f2cf297249dc",
    "https://www.betclic.fr/casino/game/b116cce2-f645-47af-a290-f2cf297249dc",
]

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--headless=new", "--no-sandbox", "--disable-gpu"],
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await ctx.new_page()

        for url in URLS:
            print(f"\n{'='*60}")
            print(f"Trying: {url}")
            try:
                resp = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                await page.wait_for_timeout(3000)
                print(f"  Status: {resp.status if resp else 'None'}")
                print(f"  Final URL: {page.url}")
                print(f"  Title: {await page.title()}")

                # Check if we're on a game page or redirected to home
                if page.url == "https://www.betclic.fr/" or page.url == "https://www.betclic.fr":
                    print("  -> Redirected to homepage (not a valid game URL)")
                else:
                    # Check for game elements
                    for source in [page] + list(page.frames):
                        for sel in ["#button_go", "#button_sound", "#inGame-history", "canvas", "[class*='game']"]:
                            try:
                                count = await source.locator(sel).count()
                                if count > 0:
                                    print(f"  -> Found '{sel}': {count} elements")
                            except:
                                pass
            except Exception as e:
                print(f"  Error: {e}")

        await browser.close()

asyncio.run(main())
