import logging
from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message, CallbackQuery, InputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import CommandStart, Command
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.client.default import DefaultBotProperties
from aiohttp import web
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Constants
ADMINS = [769063484]  # Твой Telegram ID
DRIVERS = ["Ерёмин", "Уранов", "Новиков"]

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials = ServiceAccountCredentials.from_json_keyfile_name("creds.json", scope)
gs_client = gspread.authorize(credentials)
spreadsheet = gs_client.open("Falcontrans Docs")
sheet = spreadsheet.sheet1

# Logging
logging.basicConfig(level=logging.INFO)

# Bot setup
bot = Bot(token="YOUR_BOT_TOKEN_HERE", default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# States
class DriverStates(StatesGroup):
    choosing_driver = State()
    choosing_request = State()
    sending_documents = State()

class AdminStates(StatesGroup):
    waiting_photo = State()
    waiting_request_number = State()
    waiting_driver_choice = State()

# Storage for in-memory requests
active_requests = {}

# Start command
@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    if message.from_user.id in ADMINS:
        await state.set_state(AdminStates.waiting_photo)
        await message.answer("Отправь фото заявки!")
    else:
        buttons = [KeyboardButton(text=name) for name in DRIVERS]
        keyboard = ReplyKeyboardMarkup(keyboard=[[btn] for btn in buttons], resize_keyboard=True)
        await state.set_state(DriverStates.choosing_driver)
        await message.answer("Выбери свою фамилию:", reply_markup=keyboard)

# Админ отправил фото
@dp.message(AdminStates.waiting_photo, F.photo)
async def handle_admin_photo(message: Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await state.set_state(AdminStates.waiting_request_number)
    await message.answer("Введите номер заявки:")

# Админ ввёл номер заявки
@dp.message(AdminStates.waiting_request_number)
async def handle_request_number(message: Message, state: FSMContext):
    await state.update_data(request_number=message.text)
    builder = InlineKeyboardBuilder()
    for driver in DRIVERS:
        builder.add(InlineKeyboardButton(text=driver, callback_data=f"assign:{driver}"))
    await state.set_state(AdminStates.waiting_driver_choice)
    await message.answer("Кому отправить заявку?", reply_markup=builder.as_markup())

# Админ выбирает водителя
@dp.callback_query(AdminStates.waiting_driver_choice, F.data.startswith("assign:"))
async def assign_to_driver(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    driver = callback.data.split(":")[1]
    request_number = data["request_number"]
    photo_id = data["photo"]

    if driver not in active_requests:
        active_requests[driver] = []
    active_requests[driver].append({"number": request_number, "photo": photo_id})

    # В таблицу записать
    sheet.append_row([driver, request_number])

    await callback.message.answer(f"Заявка {request_number} отправлена {driver}!")
    await state.clear()

# Водитель выбрал себя
@dp.message(DriverStates.choosing_driver, F.text.in_(DRIVERS))
async def driver_chosen(message: Message, state: FSMContext):
    driver = message.text
    await state.update_data(driver=driver)
    await state.set_state(DriverStates.choosing_request)
    requests = active_requests.get(driver, [])
    if requests:
        buttons = [InlineKeyboardButton(text=req["number"], callback_data=f"req:{req['number']}") for req in requests]
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[b] for b in buttons])
        await message.answer("Выбери заявку:", reply_markup=keyboard)
    else:
        await message.answer("Нет активных заявок. Введите номер вручную:")

# Водитель нажал на заявку
@dp.callback_query(DriverStates.choosing_request, F.data.startswith("req:"))
async def driver_selected_request(callback: CallbackQuery, state: FSMContext):
    request_number = callback.data.split(":")[1]
    await state.update_data(request_number=request_number)
    await state.set_state(DriverStates.sending_documents)
    await callback.message.answer(f"Отправь документы по заявке {request_number}:")

# Водитель отправил фото-документы
@dp.message(DriverStates.sending_documents, F.photo)
async def handle_documents(message: Message, state: FSMContext):
    data = await state.get_data()
    driver = data["driver"]
    request_number = data["request_number"]

    caption = f"📄 Документы от {driver}\nЗаявка №{request_number}"
    await bot.send_photo(chat_id=ADMINS[0], photo=message.photo[-1].file_id, caption=caption)

    await message.answer("✅ Спасибо! Документы отправлены.")
    await state.clear()

# Webhook (если нужен)
async def main():
    app = web.Application()
    dp.startup.register(lambda _: print("Bot started!"))
    setup_application(app, dp, bot=bot)
    SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
    return app

if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
