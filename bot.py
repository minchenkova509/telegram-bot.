import logging
import os
import json
import gspread
from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from oauth2client.service_account import ServiceAccountCredentials

# ================== НАСТРОЙКИ ===================
ADMINS = [769063484]  # ID администратора
DRIVERS = ["Ерёмин", "Уранов", "Новиков"]
bot_token = os.getenv("BOT_TOKEN")
if not bot_token:
    raise ValueError("BOT_TOKEN environment variable is missing!")

# =============== GOOGLE SHEETS ===================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
client = gspread.authorize(credentials)
sheet = client.open("Falcontrans Docs").sheet1

# =============== СОСТОЯНИЯ FSM ====================
class AdminStates(StatesGroup):
    waiting_for_photo = State()
    waiting_for_request_number = State()
    waiting_for_driver = State()

class DriverStates(StatesGroup):
    choosing_request = State()
    waiting_for_docs = State()

# =============== НАСТРОЙКА БОТА ===================
logging.basicConfig(level=logging.INFO)
bot = Bot(token=bot_token, default=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# =============== СЛОВАРИ ==========================
zayavki = {}  # ключ: id водителя, значение: список (номер заявки, file_id)
current_driver_request = {}  # водитель_id: номер заявки

# =============== ХЭНДЛЕРЫ =========================
@router.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    if message.from_user.id in ADMINS:
        await state.set_state(AdminStates.waiting_for_photo)
        await message.answer("👋 Привет, админ! Отправь фото заявки.")
    else:
        kb = InlineKeyboardBuilder()
        for name in DRIVERS:
            kb.button(text=name, callback_data=f"driver:{name}")
        await message.answer("Пожалуйста, выберите свою фамилию:", reply_markup=kb.as_markup())

@router.message(AdminStates.waiting_for_photo, F.photo)
async def admin_get_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(photo=file_id)
    await state.set_state(AdminStates.waiting_for_request_number)
    await message.answer("Введи номер заявки:")

@router.message(AdminStates.waiting_for_request_number)
async def admin_get_request_number(message: Message, state: FSMContext):
    await state.update_data(request_number=message.text)
    await state.set_state(AdminStates.waiting_for_driver)
    kb = InlineKeyboardBuilder()
    for name in DRIVERS:
        kb.button(text=name, callback_data=f"assign:{name}")
    await message.answer("Кому н0430значить?", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("assign:"))
async def assign_request(callback: CallbackQuery, state: FSMContext):
    driver = callback.data.split(":")[1]
    data = await state.get_data()
    request_number = data["request_number"]
    file_id = data["photo"]
    zayavki.setdefault(driver, []).append((request_number, file_id))
    sheet.append_row([request_number, driver])
    await callback.message.answer(f"Заявка {request_number} добавлена для {driver}.")
    await state.clear()

@router.callback_query(F.data.startswith("driver:"))
async def driver_menu(callback: CallbackQuery, state: FSMContext):
    driver = callback.data.split(":")[1]
    await state.set_state(DriverStates.choosing_request)
    await state.update_data(driver=driver)
    kb = InlineKeyboardBuilder()
    for req_num, _ in zayavki.get(driver, []):
        kb.button(text=req_num, callback_data=f"req:{req_num}")
    kb.button(text="Другой номер", callback_data="req:manual")
    await callback.message.answer("Выбери номер заявки:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("req:"))
async def handle_request(callback: CallbackQuery, state: FSMContext):
    req = callback.data.split(":")[1]
    if req == "manual":
        await callback.message.answer("Введи номер ручной:")
        await state.set_state(DriverStates.waiting_for_docs)
        return
    await state.update_data(request=req)
    await callback.message.answer(f"Отправь документы для заявки {req}:")
    await state.set_state(DriverStates.waiting_for_docs)

@router.message(DriverStates.waiting_for_docs, F.photo)
async def get_docs(message: Message, state: FSMContext):
    data = await state.get_data()
    request = data.get("request") or message.text
    for admin in ADMINS:
        await bot.send_photo(admin, message.photo[-1].file_id, caption=f"Заявка {request} от {data['driver']}")
    await message.answer("Спасибо!")
    await state.clear()

# =============== WEBHOOK =========================
async def on_startup(app):
    webhook_url = os.getenv("WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("WEBHOOK_URL is not set!")
    await bot.set_webhook(webhook_url + "/webhook")

async def on_shutdown(app):
    await bot.delete_webhook()

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == '__main__':
    web.run_app(app, port=8080)
