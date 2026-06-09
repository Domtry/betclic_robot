from playwright.async_api import async_playwright
import os

# Force headless=new to avoid "Multiple targets are not supported in headless mode" error
# in Chromium >= 109 with remote-debugging-pipe (used by Playwright persistent contexts).
os.environ.setdefault("PLAYWRIGHT_CHROMIUM_USE_HEADLESS_NEW", "1")


class BrowserManager:
    def __init__(self):
        self.chromium_flags = os.getenv("CHROMIUM_FLAGS", "")
        self.playwright = None
        self.context = None

    async def start(self):
        self.playwright = await async_playwright().start()
        headless = os.getenv("HEADLESS", "true").lower() != "false"
        args = self.chromium_flags.split(" ") if self.chromium_flags else []
        if headless:
            args.append("--headless=new")
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir="user_data",
            headless=headless,
            args=args,
        )

    async def new_page(self):
        return await self.context.new_page()

    async def close(self):
        await self.context.close()
        await self.playwright.stop()
