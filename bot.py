import json
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.types import Message, BufferedInputFile
from aiogram.utils.markdown import hbold
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram import Router

import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Загрузка переменных из окружения
API_TOKEN = os.getenv("API_TOKEN")

# Подключение к Google Sheets
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
GOOGLE_CREDENTIALS_JSON = json.loads(os.getenv("GOOGLE_CREDENTIALS_JSON"))

CREDS = ServiceAccountCredentials.from_json_keyfile_dict(GOOGLE_CREDENTIALS_JSON, SCOPE)
client = gspread.authorize(CREDS)
sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1jDxPfl10qTiKrHW9mdvbY9voinMV872IYrs3iHK56Gg/edit").sheet1

# FSM для обработки состояний
class UploadStates(StatesGroup):
    waiting_for_request_number = State()
    waiting_for_document = State()

# Инициализация
bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# Словарь для хранения активных заявок по пользователям
active_requests = {}

@router.message(F.text == "/start")
async def start_handler(message: Message):
    await message.answer("Привет! Напиши номер заявки, чтобы отправить документы.")
    await UploadStates.waiting_for_request_number.set()

@router.message(UploadStates.waiting_for_request_number)
async def handle_request_number(message: Message, state: FSMContext):
    request_number = message.text.strip()
    active_requests[message.from_user.id] = request_number
    await message.answer(f"Номер заявки: {hbold(request_number)}.\nТеперь пришли документ.")
    await state.set_state(UploadStates.waiting_for_document)

@router.message(UploadStates.waiting_for_document)
async def handle_document(message: Message, state: FSMContext):
    request_number = active_requests.get(message.from_user.id)
    if not message.document:
        await message.answer("Пожалуйста, отправь документ.")
        return

    # Скачиваем документ
    file = await bot.download(message.document)
    filename = f"{request_number}_{message.document.file_name}"

    # Загружаем в Google таблицу
    sheet.append_row([str(message.from_user.full_name), request_number, filename])

    await message.answer("Документ получен и сохранён.")
    await state.clear()

# Запуск
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    import asyncio
    asyncio.run(dp.start_polling(bot))
