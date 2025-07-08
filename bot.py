import logging
import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.state import StatesGroup, State
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Настройки
ADMINS = [769063484]
DRIVERS = ["Ерёмин", "Уранов", "Новиков"]
bot_token = os.getenv("BOT_TOKEN")
webhook_url = os.getenv("WEBHOOK_URL")

# FSM состояния
class Form(StatesGroup):
    waiting_for_claim_number = State()
    waiting_for_driver = State()
    waiting_for_documents = State()

# Запуск
bot = Bot(token=bot_token, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# Таблица
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
creds_dict = json.loads(creds_json)
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Falcontrans Docs").sheet1

claims = {}

@router.message(CommandStart())
async def cmd_start(msg: Message, state: FSMContext):
    if msg.from_user.id in ADMINS:
        await msg.answer("Отправь фото заявки.")
        await state.set_state(Form.waiting_for_claim_number)
    else:
        kb = InlineKeyboardBuilder()
        for driver in DRIVERS:
            kb.button(text=driver, callback_data=f"driver:{driver}")
        await msg.answer("Выбери свою фамилию:", reply_markup=kb.as_markup())

@router.message(Form.waiting_for_claim_number, F.photo)
async def handle_photo(msg: Message, state: FSMContext):
    await state.update_data(photo=msg.photo[-1].file_id)
    await msg.answer("Введи номер заявки!:")
    await state.set_state(Form.waiting_for_driver)

@router.message(Form.waiting_for_driver)
async def handle_claim_number(msg: Message, state: FSMContext):
    data = await state.get_data()
    claim_number = msg.text
    await state.update_data(claim_number=claim_number)

    kb = InlineKeyboardBuilder()
    for driver in DRIVERS:
        kb.button(text=driver, callback_data=f"assign:{driver}")
    await msg.answer("Кому отправить эту заявку?", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("assign:"))
async def assign_driver(callback: CallbackQuery, state: FSMContext):
    driver = callback.data.split(":")[1]
    data = await state.get_data()
    claims.setdefault(driver, []).append({
        "claim_number": data["claim_number"],
        "photo": data["photo"]
    })
    sheet.append_row([driver, data["claim_number"], ""])
    await callback.message.answer(f"✅ Заявка {data['claim_number']} отправлена {driver}")
    await state.clear()

@router.callback_query(F.data.startswith("driver:"))
async def show_driver_claims(callback: CallbackQuery):
    driver = callback.data.split(":")[1]
    user_claims = claims.get(driver, [])
    if not user_claims:
        await callback.message.answer("Нет активных заявок.")
        return

    kb = InlineKeyboardBuilder()
    for claim in user_claims:
        kb.button(text=claim["claim_number"], callback_data=f"submit:{driver}:{claim['claim_number']}")
    kb.button(text="Ввести вручную", callback_data=f"manual:{driver}")
    await callback.message.answer("Выбери заявку:", reply_markup=kb.as_markup())

@router.callback_query(F.data.startswith("submit:"))
async def request_document(callback: CallbackQuery, state: FSMContext):
    _, driver, claim_number = callback.data.split(":")
    await state.set_state(Form.waiting_for_documents)
    await state.update_data(driver=driver, claim_number=claim_number)
    await callback.message.answer(f"Отправь документы по заявке {claim_number}:")

@router.callback_query(F.data.startswith("manual:"))
async def manual_entry(callback: CallbackQuery, state: FSMContext):
    _, driver = callback.data.split(":")
    await state.update_data(driver=driver)
    await state.set_state(Form.waiting_for_driver)
    await callback.message.answer("Введи номер заявки вручную:")

@router.message(Form.waiting_for_documents, F.photo)
async def handle_documents(msg: Message, state: FSMContext):
    data = await state.get_data()
    admin_id = ADMINS[0]
    await bot.send_photo(admin_id, msg.photo[-1].file_id, caption=f"📄 Документы по заявке {data['claim_number']} от {data['driver']}")
    await msg.answer("Спасибо! Документы получены.")
    await state.clear()

# Webhook setup
async def on_startup(app: web.Application):
    await bot.set_webhook(webhook_url)

async def on_shutdown(app: web.Application):
    await bot.delete_webhook()

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
