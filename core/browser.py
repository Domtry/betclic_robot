from playwright.async_api import async_playwright

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.context = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir="user_data",
            headless=True
        )

    async def new_page(self):
        return await self.context.new_page()

    async def close(self):
        await self.context.close()
        await self.playwright.stop()