import os
import json
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import ParseMode
from aiogram.utils import executor
from googleapiclient.discovery import build
from oauth2client.service_account import ServiceAccountCredentials

# Логирование
logging.basicConfig(level=logging.INFO)

# Переменные среды
TOKEN = os.getenv("API_TOKEN")
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")
GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON")

# Инициализация бота
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot)

# Настройка Google Sheets API
SCOPE = ['https://www.googleapis.com/auth/spreadsheets']
CREDS = ServiceAccountCredentials.from_json_keyfile_dict(
    json.loads(GOOGLE_CREDENTIALS_JSON),
    SCOPE
)
sheet_service = build('sheets', 'v4', credentials=CREDS)
sheet = sheet_service.spreadsheets()

# Хэндлер стартовой команды
@dp.message_handler(commands=["start"])
async def start_command(message: types.Message):
    await message.answer("Привет! 👋 Отправь номер заявки, а затем прикрепи документ или фото.")

# Словарь для хранения временных заявок (по user_id)
user_requests = {}

@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle_text(message: types.Message):
    if message.text.isdigit():
        user_requests[message.from_user.id] = message.text
        await message.reply(f"📄 Заявка №{message.text} сохранена. Теперь отправь документ или фото.")
    else:
        await message.reply("Пожалуйста, сначала отправьте номер заявки (только цифры).")

@dp.message_handler(content_types=[types.ContentType.DOCUMENT, types.ContentType.PHOTO])
async def handle_file(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_requests:
        await message.reply("Сначала отправь номер заявки (цифрами).")
        return

    request_number = user_requests[user_id]
    file_id = None
    file_type = None

    if message.document:
        file_id = message.document.file_id
        file_type = "document"
    elif message.photo:
        file_id = message.photo[-1].file_id  # последняя — лучшее качество
        file_type = "photo"

    file = await bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{TOKEN}/{file.file_path}"

    # Добавляем запись в Google Таблицу
    values = [[
        str(message.from_user.id),
        message.from_user.full_name,
        request_number,
        file_type,
        file_url
    ]]
    sheet.values().append(
        spreadsheetId=SPREADSHEET_ID,
        range="A1",
        valueInputOption="RAW",
        body={"values": values}
    ).execute()

    await message.reply("✅ Документ получен и добавлен в таблицу!")

# Запуск
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
