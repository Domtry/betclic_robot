"""Diagnostic: inspect the game page to find what elements are actually present."""
import asyncio
from playwright.async_api import async_playwright

GAME_URL = "https://www.betclic.ci/casino/games/b116cce2-f645-47af-a290-f2cf297249dc/play?mode=1"

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

        print(f"Navigating to {GAME_URL}...")
        resp = await page.goto(GAME_URL, wait_until="domcontentloaded")
        print(f"Response status: {resp.status if resp else 'None'}")
        print(f"Final URL: {page.url}")

        # Wait a bit for JS to load
        await page.wait_for_timeout(5000)

        # Check for frames
        print(f"\nFrames ({len(page.frames)}):")
        for f in page.frames:
            print(f"  URL: {f.url[:120]}")

        # Check for #button_go and #button_sound in all frames
        for i, source in enumerate([page] + list(page.frames)):
            try:
                btn_go = source.locator("#button_go")
                count = await btn_go.count()
                if count > 0:
                    visible = await btn_go.is_visible()
                    print(f"\n[frame {i}] #button_go: count={count}, visible={visible}")
            except Exception as e:
                pass

            try:
                btn_sound = source.locator("#button_sound")
                count = await btn_sound.count()
                if count > 0:
                    visible = await btn_sound.is_visible()
                    print(f"\n[frame {i}] #button_sound: count={count}, visible={visible}")
            except Exception as e:
                pass

        # Check for common game-related elements
        for source in [page] + list(page.frames):
            for selector in ["#inGame-history", ".inGame-history", "[class*='game']", "[class*='casino']", "canvas", "iframe"]:
                try:
                    count = await source.locator(selector).count()
                    if count > 0:
                        print(f"\n  Found '{selector}': {count} elements")
                except:
                    pass

        # Dump page title and some content
        title = await page.title()
        print(f"\nPage title: {title}")

        # Check for any error messages or redirects
        body_text = await page.evaluate("() => document.body.innerText.substring(0, 500)")
        print(f"\nBody text (first 500 chars):\n{body_text}")

        # Check for iframes
        iframes = await page.evaluate("""() => {
            return Array.from(document.querySelectorAll('iframe')).map(f => ({
                src: f.src,
                id: f.id,
                className: f.className.substring(0, 80),
            }));
        }""")
        print(f"\nIframes ({len(iframes)}):")
        for iframe in iframes:
            print(f"  {iframe}")

        await browser.close()

asyncio.run(main())
