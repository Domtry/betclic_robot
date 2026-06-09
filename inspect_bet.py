"""Inspection des éléments de mise dans Circuit Masters."""
import asyncio, json
from playwright.async_api import async_playwright

COOKIES_PATH = "cookies.json"
GAME_URL = "https://www.betclic.ci/casino/games/b116cce2-f645-47af-a290-f2cf297249dc/play?mode=1"

async def dump_source(label, source):
    print(f"\n{'='*60}")
    print(f"SOURCE: {label}")
    result = await source.evaluate("""() => {
        const info = el => ({
            tag: el.tagName,
            id: el.id,
            cls: el.className?.toString().substring(0, 80),
            type: el.type || '',
            placeholder: el.placeholder || '',
            value: el.value || '',
            text: el.textContent?.trim().substring(0, 40) || '',
            ariaLabel: el.getAttribute('aria-label') || '',
            dataQa: el.getAttribute('data-qa') || '',
            name: el.name || '',
            disabled: el.disabled,
            visible: el.offsetParent !== null,
        });
        const inputs = Array.from(document.querySelectorAll('input')).map(info);
        const buttons = Array.from(document.querySelectorAll('button')).map(info);
        const allIds = Array.from(document.querySelectorAll('[id]'))
                           .map(el => el.id).filter(id => id.length > 0 && id.length < 80);
        return { inputs, buttons, allIds };
    }""")
    print(f"  IDs on page: {result['allIds'][:40]}")
    print(f"\n  Inputs ({len(result['inputs'])}):")
    for inp in result['inputs']:
        print(f"    id={inp['id']!r:30} type={inp['type']!r:10} cls={inp['cls']!r:50} placeholder={inp['placeholder']!r} name={inp['name']!r} visible={inp['visible']}")
    print(f"\n  Buttons ({len(result['buttons'])}):")
    for btn in result['buttons']:
        if btn['text'] or btn['id'] or btn['dataQa']:
            print(f"    id={btn['id']!r:30} text={btn['text']!r:30} cls={btn['cls']!r:50} disabled={btn['disabled']}")

async def main():
    import os
    from core.browser import BrowserManager
    from modules.example_site import ExampleSiteBot
    from dotenv import load_dotenv
    load_dotenv(".env")

    browser = BrowserManager()
    await browser.start()
    page = await browser.new_page()
    bot = ExampleSiteBot(page)

    await bot.ensure_logged_in(os.getenv("USERNAME"), os.getenv("PASSWORD"), os.getenv("DATE_OF_BIRTH"))
    await bot.open_game(GAME_URL)

    # Attendre que le jeu soit bien chargé
    await page.wait_for_timeout(3000)

    print("\n=== PAGE PRINCIPALE ===")
    await dump_source("page", page)

    print("\n=== FRAMES ===")
    for i, frame in enumerate(page.frames):
        if frame.url and frame.url != "about:blank":
            print(f"\n--- Frame {i}: {frame.url[:100]} ---")
            try:
                await dump_source(f"frame_{i}", frame)
            except Exception as e:
                print(f"  Erreur: {e}")

    await browser.close()

asyncio.run(main())
