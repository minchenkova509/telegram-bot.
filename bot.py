import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiohttp import web
import requests
import io

API_TOKEN = os.getenv('API_TOKEN')
FOURLOGIST_USER = os.getenv('FOURLOGIST_USER', 'falcon-tr')
FOURLOGIST_PASS = os.getenv('FOURLOGIST_PASS', 'falcon-tr12345')
FOURLOGIST_URL = 'https://api.4logist.com/api/orders/{order}/add-photo'

WEBHOOK_PATH = "/webhook"
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Railway выдаст вам внешний адрес, добавьте /webhook

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
user_state = {}

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="Новиков", callback_data="Novikov"),
            InlineKeyboardButton(text="Уранов", callback_data="Uranov"),
            InlineKeyboardButton(text="Еремин", callback_data="Eremin"),
        ]
    ])
    await message.answer("Выберите свою фамилию:", reply_markup=kb)

@dp.callback_query(F.data.in_(["Novikov", "Uranov", "Eremin"]))
async def surname_handler(callback: types.CallbackQuery):
    user_state[callback.from_user.id] = {"surname": callback.data}
    await bot.send_message(callback.from_user.id, "Введите номер заказа")
    await callback.answer()

@dp.message(lambda message: message.from_user.id in user_state and "order" not in user_state[message.from_user.id])
async def order_handler(message: types.Message):
    user_state[message.from_user.id]["order"] = message.text
    await message.answer("Готовы принимать документы. Отправьте фото.")

@dp.message(F.photo)
async def photo_handler(message: types.Message):
    user = user_state.get(message.from_user.id, {})
    surname = user.get("surname", "Неизвестно")
    order = user.get("order", "Неизвестно")

    # Получаем файл фото
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    file_path = file.file_path
    file_url = f"https://api.telegram.org/file/bot{API_TOKEN}/{file_path}"
    file_data = requests.get(file_url).content

    # Отправляем фото в 4logist с правильной кодировкой
    try:
        files = {"file": ("document.jpg", io.BytesIO(file_data), "image/jpeg")}
        response = requests.post(
            FOURLOGIST_URL.format(order=order),
            auth=(FOURLOGIST_USER, FOURLOGIST_PASS),
            files=files
        )
        logist_status = "Загружено в 4logist" if response.ok else f"Ошибка 4logist: {response.status_code} {response.text}"
    except Exception as e:
        logist_status = f"Ошибка 4logist: {e}"

    await message.answer(f"Спасибо, документы получены. {logist_status}\nФамилия: {surname}\nЗаказ: {order}")

async def on_startup(app):
    webhook_url = os.getenv('WEBHOOK_URL')
    await bot.set_webhook(webhook_url + WEBHOOK_PATH)

async def on_shutdown(app):
    await bot.delete_webhook()

app = web.Application()
app.router.add_post(WEBHOOK_PATH, dp.webhook_handler(bot))
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, port=int(os.getenv("PORT", 8080)))
