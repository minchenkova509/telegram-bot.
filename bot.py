import os
import asyncio
from datetime import datetime
import gspread
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from oauth2client.service_account import ServiceAccountCredentials

API_TOKEN = os.environ.get("API_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
OWNER_ID = 769063484
SPREADSHEET_ID = "1jDxPfl10qTiKrHW9mdvbY9voinMV872IYrs3iHK56Gg"

# Настройка Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key(SPREADSHEET_ID).sheet1

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class FSMAdmin(StatesGroup):
    waiting_for_photo = State()
    waiting_for_driver = State()
    waiting_for_request_number = State()

class FSMDriver(StatesGroup):
    choosing_request = State()
    sending_docs = State()

driver_list = ["Еремин", "Уранов", "Новиков"]

@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    if message.from_user.id == OWNER_ID:
        await message.answer("Отправьте фото заявки.")
        await state.set_state(FSMAdmin.waiting_for_photo)
    else:
        kb = InlineKeyboardBuilder()
        for name in driver_list:
            kb.button(text=name, callback_data=name)
        await message.answer("Выберите кто вы:", reply_markup=kb.as_markup())
        await state.set_state(FSMDriver.choosing_request)

@dp.message(FSMAdmin.waiting_for_photo, F.photo)
async def get_photo(message: Message, state: FSMContext):
    await state.update_data(photo_id=message.photo[-1].file_id)
    kb = InlineKeyboardBuilder()
    for name in driver_list:
        kb.button(text=name, callback_data=name)
    await message.answer("Кому отправить эту заявку?", reply_markup=kb.as_markup())
    await state.set_state(FSMAdmin.waiting_for_driver)

@dp.callback_query(FSMAdmin.waiting_for_driver)
async def set_driver(callback: CallbackQuery, state: FSMContext):
    await state.update_data(driver=callback.data)
    await callback.message.answer("Введите номер заявки:")
    await state.set_state(FSMAdmin.waiting_for_request_number)
    await callback.answer()

@dp.message(FSMAdmin.waiting_for_request_number)
async def set_request_number(message: Message, state: FSMContext):
    data = await state.get_data()
    photo_id = data["photo_id"]
    driver = data["driver"]
    request_number = message.text.strip()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    sheet.append_row([request_number, driver, date_str, photo_id, "от админа"])
    await message.answer("Заявка сохранена и отправлена водителю.")
    await state.clear()

@dp.callback_query(FSMDriver.choosing_request)
async def driver_chosen(callback: CallbackQuery, state: FSMContext):
    driver = callback.data
    await state.update_data(driver=driver)
    records = sheet.get_all_records()
    buttons = [r["Номер заявки"] for r in records if r["Водитель"] == driver]
    kb = InlineKeyboardBuilder()
    for req in buttons:
        kb.button(text=f"Заявка {req}", callback_data=req)
    kb.button(text="Ввести вручную", callback_data="manual")
    await callback.message.answer("Выберите заявку:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(FSMDriver.choosing_request, F.data == "manual")
async def manual_entry(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите номер заявки:")
    await state.set_state(FSMDriver.sending_docs)
    await callback.answer()

@dp.callback_query(FSMDriver.choosing_request)
async def choose_existing_request(callback: CallbackQuery, state: FSMContext):
    await state.update_data(request_number=callback.data)
    await callback.message.answer("Отправьте фото документов:")
    await state.set_state(FSMDriver.sending_docs)
    await callback.answer()

@dp.message(FSMDriver.sending_docs, F.photo)
async def receive_docs(message: Message, state: FSMContext):
    data = await state.get_data()
    driver = data.get("driver")
    request_number = data.get("request_number", "без номера")
    caption = f"📥 Документы по заявке {request_number} от {driver}"
    await bot.send_photo(chat_id=OWNER_ID, photo=message.photo[-1].file_id, caption=caption)
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    sheet.append_row([request_number, driver, date_str, message.photo[-1].file_id, "от водителя"])
    await message.answer("Спасибо, документы приняты.")
    await state.clear()

@dp.message()
async def fallback(message: Message):
    await message.answer("Пожалуйста, начните с команды /start.")

async def on_startup(app: web.Application):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()

async def main():
    app = web.Application()
    app["bot"] = bot
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    setup_application(app, dp, bot=bot)
    app.on_startup.append(on_startup)
    app.on_shutdown.append(on_shutdown)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.environ.get("PORT", 8000)))
    await site.start()
    print("Бот запущен...")
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(main())
