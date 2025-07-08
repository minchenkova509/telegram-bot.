import json
import logging
import os
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.enums import ParseMode
from aiogram.types import Message, FSInputFile, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import setup_application
from aiohttp import web
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Telegram Bot Token
TOKEN = os.getenv("API_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# Google Sheets Setup
GOOGLE_CREDENTIALS_JSON = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS_JSON, SCOPE)
GSPREAD_CLIENT = gspread.authorize(CREDS)
SHEET = GSPREAD_CLIENT.open_by_url("https://docs.google.com/spreadsheets/d/1jDxPfl10qTiKrHW9mdvbY9voinMV872IYrs3iHK56Gg/edit#gid=0").sheet1

# FSM States
class Form(StatesGroup):
    driver = State()
    request_id = State()
    awaiting_photos = State()

ADMINS = [769063484]
DRIVERS = ["Еремин", "Уранов", "Новиков"]

router = Router()

@router.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    keyboard = [[InlineKeyboardButton(text=name, callback_data=name)] for name in DRIVERS]
    await message.answer("Кто вы?", reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))
    await state.set_state(Form.driver)

@router.callback_query(Form.driver)
async def select_driver(callback: types.CallbackQuery, state: FSMContext):
    driver_name = callback.data
    await state.update_data(driver=driver_name)
    await callback.message.answer(f"Вы выбрали: {driver_name}. Введите номер заявки:")
    await state.set_state(Form.request_id)
    await callback.answer()

@router.message(Form.request_id)
async def input_request_id(message: Message, state: FSMContext):
    await state.update_data(request_id=message.text)
    await message.answer("Готов принять твои документы. Пришли фото одним сообщением.")
    await state.set_state(Form.awaiting_photos)

@router.message(Form.awaiting_photos, F.photo)
async def handle_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    driver_name = data.get("driver")
    request_id = data.get("request_id")

    media = message.photo[-1]
    file_id = media.file_id
    caption = f"\uD83D\uDCC4 Документы от {driver_name}\nЗаявка: {request_id}"

    for admin_id in ADMINS:
        await message.bot.send_photo(admin_id, file_id, caption=caption)

    SHEET.append_row([driver_name, request_id, message.from_user.full_name])

    await message.answer("Спасибо, документы приняты. Счастливого пути!")
    await state.clear()

# Start bot
async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)

async def main():
    bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    app = web.Application()
    setup_application(app, dp, bot=bot)

    app.on_startup.append(lambda _: on_startup(bot))

    return app

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    web.run_app(main())
