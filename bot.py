import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import Message, FSInputFile, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

# === CONFIG ===
API_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMINS = [769063484]  # твой Telegram ID

# === Инициализация ===
bot = Bot(token=API_TOKEN, default=Bot.DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

# === FSM ===
class Form(StatesGroup):
    choosing_driver = State()
    waiting_photo = State()
    entering_number = State()
    sending_docs = State()

# === Память заявок ===
active_requests = {
    "Ерёмин": [],
    "Уранов": [],
    "Новиков": []
}

photo_storage = {}

# === Команда старт ===
@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    if message.from_user.id in ADMINS:
        await message.answer("👋 Привет, админ! Отправь фото заявки.")
        await state.set_state(Form.waiting_photo)
    else:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("Ерёмин", "Уранов", "Новиков")
        await message.answer("Выбери свою фамилию:", reply_markup=kb)
        await state.set_state(Form.choosing_driver)

# === Админ отправляет фото ===
@dp.message(Form.waiting_photo, F.photo)
async def admin_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(photo_id=file_id)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Ерёмин", "Уранов", "Новиков")
    await message.answer("Кому отправить заявку?", reply_markup=kb)
    await state.set_state(Form.choosing_driver)

# === Админ выбирает водителя ===
@dp.message(Form.choosing_driver, F.text.in_(["Ерёмин", "Уранов", "Новиков"]))
async def assign_driver(message: Message, state: FSMContext):
    driver = message.text
    data = await state.get_data()
    file_id = data.get("photo_id")

    if not file_id:
        await message.answer("Сначала отправь фото заявки.")
        return

    await message.answer("Введи номер заявки:")
    await state.update_data(driver=driver)
    await state.set_state(Form.entering_number)

# === Админ вводит номер заявки ===
@dp.message(Form.entering_number)
async def enter_number(message: Message, state: FSMContext):
    data = await state.get_data()
    driver = data["driver"]
    file_id = data["photo_id"]
    req_number = message.text

    active_requests[driver].append(req_number)
    photo_storage[req_number] = file_id

    await message.answer(f"✅ Заявка №{req_number} отправлена водителю {driver}")
    await state.clear()

# === Водитель выбирает фамилию ===
@dp.message(Form.choosing_driver, F.text.in_(["Ерёмин", "Уранов", "Новиков"]))
async def driver_selected(message: Message, state: FSMContext):
    driver = message.text
    requests = active_requests.get(driver, [])

    if not requests:
        await message.answer("У тебя пока нет активных заявок.")
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for req in requests:
        kb.add(req)
    kb.add("Ввести вручную")

    await state.update_data(driver=driver)
    await message.answer("Выбери номер заявки:", reply_markup=kb)
    await state.set_state(Form.sending_docs)

# === Водитель отправляет документы по номеру заявки ===
@dp.message(Form.sending_docs, F.text)
async def receive_docs(message: Message, state: FSMContext):
    req_number = message.text
    data = await state.get_data()

    if req_number not in photo_storage and req_number != "Ввести вручную":
        await message.answer("Такой заявки нет. Введи вручную или выбери из списка.")
        return

    await message.answer(f"Отправь фото документов по заявке {req_number}")
    await state.update_data(req_number=req_number)

# === Водитель отправил фото документов ===
@dp.message(F.photo)
async def docs_received(message: Message, state: FSMContext):
    data = await state.get_data()
    req_number = data.get("req_number", "Без номера")

    caption = f"📄 Документы по заявке {req_number}\nОт: @{message.from_user.username or message.from_user.id}"
    for admin_id in ADMINS:
        await bot.send_photo(admin_id, message.photo[-1].file_id, caption=caption)

    await message.answer("✅ Документы получены. Спасибо!")
    await state.clear()

# === Webhook setup ===
async def on_startup(app):
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()

# === Запуск сервера ===
app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
