"""Diagnostic: check if game loads with longer wait and WebGL support."""
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
            args=[
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--enable-webgl",
                "--ignore-gpu-blocklist",
                "--use-gl=swiftshader",
            ],
        )
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
        )
        await ctx.add_cookies(cookies)
        page = await ctx.new_page()

        # Listen for console errors
        page.on("console", lambda msg: print(f"  [CONSOLE {msg.type}] {msg.text[:200]}"))
        page.on("pageerror", lambda err: print(f"  [PAGE ERROR] {err}"))

        print(f"Navigating to: {GAME_URL}")
        resp = await page.goto(GAME_URL, wait_until="networkidle", timeout=30000)
        print(f"Status: {resp.status if resp else 'None'}")
        print(f"Final URL: {page.url}")

        # Wait longer
        print("\nWaiting 20s for Angular to render...")
        await page.wait_for_timeout(20000)

        # Check URL again
        print(f"URL after wait: {page.url}")

        # Check frames
        print(f"\nFrames ({len(page.frames)}):")
        for i, f in enumerate(page.frames):
            print(f"  [{i}] {f.url[:150]}")

        # Check for game elements
        for source in [page] + list(page.frames):
            for sel in ["#button_go", "#button_sound", "#inGame-history", "canvas", "[class*='game']", "[class*='crash']", "[class*='multiplier']"]:
                try:
                    count = await source.locator(sel).count()
                    if count > 0:
                        print(f"  FOUND '{sel}': {count}")
                except:
                    pass

        # Check body text
        body = await page.evaluate("() => document.body.innerText.substring(0, 300)")
        print(f"\nBody:\n{body}")

        # Check for specific Angular routing
        route_info = await page.evaluate("""() => {
            return {
                url: window.location.href,
                title: document.title,
                hasAngular: !!window.angular || !!window.getAllAngularRootElements,
                bodyChildCount: document.body.children.length,
                mainContent: document.querySelector('[ng-view]') ? 'found ng-view' : 
                             document.querySelector('router-outlet') ? 'found router-outlet' :
                             document.querySelector('#app') ? 'found #app' :
                             document.querySelector('[data-ng-app]') ? 'found data-ng-app' : 'no main content found',
            };
        }""")
        print(f"\nRoute info: {json.dumps(route_info, indent=2)}")

        await browser.close()

asyncio.run(main())
