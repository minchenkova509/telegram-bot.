import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.state import StatesGroup, State

# ENV VARIABLES
API_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

ADMINS = ["769063484"]
DRIVERS = ["Ерёмин", "Уранов", "Новиков"]

# Logging
logging.basicConfig(level=logging.INFO)

# FSM States
class AdminState(StatesGroup):
    waiting_photo = State()
    waiting_number = State()
    waiting_driver = State()

class DriverState(StatesGroup):
    waiting_documents = State()

# Memory storage
storage = MemoryStorage()
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=storage)

# In-memory заявки
driver_tasks = {}

# Handlers
@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    user_id = str(message.from_user.id)
    if user_id in ADMINS:
        await message.answer("👋 Привет, админ! Отправь фото заявки.")
        await state.set_state(AdminState.waiting_photo)
    else:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=driver, callback_data=f"driver:{driver}")]
            for driver in DRIVERS
        ])
        await message.answer("👋 Выбери свою фамилию:", reply_markup=keyboard)

@dp.message(AdminState.waiting_photo, F.photo)
async def admin_get_photo(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    await state.update_data(photo_id=file_id)
    await message.answer("📄 Введи номер заявки:")
    await state.set_state(AdminState.waiting_number)

@dp.message(AdminState.waiting_number)
async def admin_get_number(message: Message, state: FSMContext):
    await state.update_data(task_number=message.text)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=driver, callback_data=f"assign:{driver}")]
        for driver in DRIVERS
    ])
    await message.answer("👤 Кому отправить заявку?", reply_markup=keyboard)
    await state.set_state(AdminState.waiting_driver)

@dp.callback_query(F.data.startswith("assign:"))
async def admin_assign_driver(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    photo_id = data["photo_id"]
    task_number = data["task_number"]
    driver = callback.data.split(":")[1]

    # Сохраняем заявку
    driver_tasks.setdefault(driver, []).append({
        "task_number": task_number,
        "photo_id": photo_id
    })

    await callback.message.answer(f"✅ Заявка №{task_number} отправлена {driver}!")
    await state.clear()

@dp.callback_query(F.data.startswith("driver:"))
async def driver_selected(callback: CallbackQuery, state: FSMContext):
    driver = callback.data.split(":")[1]
    await state.update_data(driver_name=driver)

    tasks = driver_tasks.get(driver, [])
    if not tasks:
        await callback.message.answer("📭 Заявок пока нет.")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=task["task_number"], callback_data=f"task:{task['task_number']}")]
        for task in tasks
    ])
    await callback.message.answer("📌 Мои заявки:", reply_markup=keyboard)

@dp.callback_query(F.data.startswith("task:"))
async def driver_selected_task(callback: CallbackQuery, state: FSMContext):
    task_number = callback.data.split(":")[1]
    data = await state.get_data()
    driver = data.get("driver_name")

    task_list = driver_tasks.get(driver, [])
    task = next((t for t in task_list if t["task_number"] == task_number), None)

    if not task:
        await callback.message.answer("❌ Заявка не найдена.")
        return

    await callback.message.answer_photo(task["photo_id"], caption=f"📄 Заявка №{task_number}")
    await state.update_data(current_task=task_number)
    await callback.message.answer("📤 Отправь документы на эту заявку:")
    await state.set_state(DriverState.waiting_documents)

@dp.message(DriverState.waiting_documents, F.photo)
async def driver_send_docs(message: Message, state: FSMContext):
    data = await state.get_data()
    task_number = data.get("current_task")
    driver = data.get("driver_name")

    # Пересылаем админу
    for admin_id in ADMINS:
        await bot.send_message(admin_id, f"📥 Документы от {driver} по заявке №{task_number}")
        await bot.send_photo(admin_id, message.photo[-1].file_id)

    await message.answer("✅ Спасибо! Документы отправлены.")
    await state.clear()

# Webhook setup
async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()

# AIOHTTP
app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)
setup_application(app, dp)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=8080)
