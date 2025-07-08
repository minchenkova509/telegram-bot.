import os
from aiogram import Bot, Dispatcher, types
from aiogram.utils.executor import start_webhook

API_TOKEN = os.environ.get("API_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await message.reply("Привет! Я работаю через Railway!")

async def on_startup(dp):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(dp):
    await bot.delete_webhook()

if __name__ == '__main__':
    start_webhook(
        dispatcher=dp,
        webhook_path='',
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 8000))
    )
# minor update to trigger redeploy

