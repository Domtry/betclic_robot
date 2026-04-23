import asyncio
from services.bot_service import BotService

async def main():
    bot = BotService()
    await bot.run()

asyncio.run(main())