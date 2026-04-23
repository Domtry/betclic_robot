from playwright.async_api import async_playwright

# Flags requis pour Chromium dans un conteneur Docker (pas de sandbox kernel)
_DOCKER_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",   # /dev/shm souvent trop petit dans Docker
    "--disable-gpu",
    "--single-process",
]

class BrowserManager:
    def __init__(self):
        self.playwright = None
        self.context = None

    async def start(self):
        self.playwright = await async_playwright().start()
        self.context = await self.playwright.chromium.launch_persistent_context(
            user_data_dir="user_data",
            headless=True,
            args=_DOCKER_ARGS,
            viewport={"width": 1280, "height": 800},
        )

    async def new_page(self):
        return await self.context.new_page()

    async def close(self):
        await self.context.close()
        await self.playwright.stop()