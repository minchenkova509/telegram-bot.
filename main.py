import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.enums import ParseMode
from aiogram.types import Message
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web
from aiogram.client.default import DefaultBotProperties

# === Проверка переменных ===
API_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMINS = [769063484]  # Замени на свой ID

if not API_TOKEN or not WEBHOOK_URL:
    raise ValueError("❌ BOT_TOKEN и WEBHOOK_URL должны быть заданы в переменных окружения")

# === Инициализация бота ===
bot = Bot(
    token=API_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# === FSM ===
class Form(StatesGroup):
    waiting_photo = State()
    choosing_driver_admin = State()
    entering_number = State()
    choosing_driver_driver = State()
    sending_docs = State()

# === Хранилище заявок ===
active_requests = {
    "Ерёмин": [],
    "Уранов": [],
    "Новиков": []
}
photo_storage = {}

# === /start ===
@dp.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext):
    if message.from_user.id in ADMINS:
        await message.answer("👋 Привет, админ! Отправь фото заявки.")
        await state.set_state(Form.waiting_photo)
    else:
        kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
        kb.add("Ерёмин", "Уранов", "Новиков")
        await message.answer("Выбери свою фамилию:", reply_markup=kb)
        await state.set_state(Form.choosing_driver_driver)

# === Админ: фото заявки ===
@dp.message(Form.waiting_photo, F.photo)
async def handle_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(photo_id=file_id)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("Ерёмин", "Уранов", "Новиков")
    await message.answer("Кому отправить заявку?", reply_markup=kb)
    await state.set_state(Form.choosing_driver_admin)

# === Админ: выбор водителя ===
@dp.message(Form.choosing_driver_admin, F.text.in_(["Ерёмин", "Уранов", "Новиков"]))
async def admin_choose_driver(message: Message, state: FSMContext):
    driver = message.text
    data = await state.get_data()
    file_id = data.get("photo_id")

    if not file_id:
        await message.answer("Сначала отправь фото заявки.")
        return

    await state.update_data(driver=driver)
    await message.answer("Введи номер заявки:")
    await state.set_state(Form.entering_number)

# === Админ: ввод номера заявки ===
@dp.message(Form.entering_number)
async def admin_enter_number(message: Message, state: FSMContext):
    data = await state.get_data()
    driver = data["driver"]
    file_id = data["photo_id"]
    req_number = message.text

    active_requests[driver].append(req_number)
    photo_storage[req_number] = file_id

    await message.answer(f"✅ Заявка №{req_number} отправлена водителю {driver}")
    await state.clear()

# === Водитель: выбор фамилии ===
@dp.message(Form.choosing_driver_driver, F.text.in_(["Ерёмин", "Уранов", "Новиков"]))
async def driver_select_name(message: Message, state: FSMContext):
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

# === Водитель: получает номер заявки ===
@dp.message(Form.sending_docs, F.text)
async def handle_request_number(message: Message, state: FSMContext):
    req_number = message.text
    if req_number != "Ввести вручную" and req_number not in photo_storage:
        await message.answer("Такой заявки нет. Введи вручную или выбери из списка.")
        return

    await state.update_data(req_number=req_number)
    await message.answer(f"Отправь фото документов по заявке {req_number}")

# === Водитель: отправил документы ===
@dp.message(F.photo)
async def receive_docs(message: Message, state: FSMContext):
    data = await state.get_data()
    req_number = data.get("req_number", "Без номера")
    caption = f"📄 Документы по заявке {req_number}\nОт: @{message.from_user.username or message.from_user.id}"
    for admin_id in ADMINS:
        await bot.send_photo(admin_id, message.photo[-1].file_id, caption=caption)
    await message.answer("✅ Документы получены. Спасибо!")
    await state.clear()

# === Fallback: неподдерживаемые сообщения ===
@dp.message()
async def fallback(message: Message):
    await message.answer("⚠️ Не понял. Выбери вариант из меню или отправь фото.")

# === Webhook setup ===
async def on_startup(app):
    webhook_info = await bot.get_webhook_info()
    if webhook_info.url != WEBHOOK_URL:
        await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()

# === Запуск ===
app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
