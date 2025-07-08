import os
import asyncio
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import Message

API_TOKEN = os.environ.get("API_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

if not API_TOKEN:
    raise Exception("API_TOKEN is missing!")
if not WEBHOOK_URL:
    raise Exception("WEBHOOK_URL is missing!")

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

@dp.message()
async def handle_message(message: Message):
    await message.answer("Привет! Я бот на aiogram 3 🚀")

async def on_startup(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()

async def main():
    app = web.Application()
    app["bot"] = bot

    # Обработчик запросов Telegram
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")

    # Подключение aiogram к aiohttp
    setup_application(app, dp, bot=bot)

    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    port = int(os.environ.get("PORT", 8000))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

    print(f"Бот запущен на http://0.0.0.0:{port}")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
