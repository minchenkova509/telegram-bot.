from textwrap import dedent

# Пример минимального кода с учетом описанных требований
bot_code = dedent("""
    import os
    import json
    import logging
    from aiogram import Bot, Dispatcher, F
    from aiogram.types import Message, CallbackQuery, FSInputFile
    from aiogram.enums import ParseMode
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.state import State, StatesGroup
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    from aiogram.types import InlineKeyboardButton
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
    from aiohttp import web
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    import base64
    import io

    logging.basicConfig(level=logging.INFO)

    # Чтение Google credentials из переменной окружения
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON")
    if credentials_json is None:
        raise RuntimeError("GOOGLE_CREDENTIALS_JSON not set")

    creds_dict = json.loads(credentials_json)
    creds = service_account.Credentials.from_service_account_info(creds_dict)
    sheets_service = build("sheets", "v4", credentials=creds)
    spreadsheet_id = "1jDxPfl10qTiKrHW9mdvbY9voinMV872IYrs3iHK56Gg"

    # Конфигурация
    API_TOKEN = os.getenv("API_TOKEN")
    WEBHOOK_URL = os.getenv("WEBHOOK_URL")
    dispatcher = Dispatcher(storage=MemoryStorage())
    bot = Bot(token=API_TOKEN, parse_mode=ParseMode.HTML)

    # FSM состояния
    class Form(StatesGroup):
        choosing_driver = State()
        entering_request = State()
        uploading_docs = State()

    # Стартовое сообщение
    @dispatcher.message(F.text == "/start")
    async def start(message: Message, state: FSMContext):
        kb = InlineKeyboardBuilder()
        for name in ["Еремин", "Уранов", "Новиков"]:
            kb.add(InlineKeyboardButton(text=name, callback_data=name))
        await state.set_state(Form.choosing_driver)
        await message.answer("Кто вы?", reply_markup=kb.as_markup())

    @dispatcher.callback_query(Form.choosing_driver)
    async def choose_driver(callback: CallbackQuery, state: FSMContext):
        await state.update_data(driver=callback.data)
        await callback.message.answer(f"Вы выбрали: {callback.data}\\nВведите номер заявки.")
        await state.set_state(Form.entering_request)

    @dispatcher.message(Form.entering_request)
    async def enter_request(message: Message, state: FSMContext):
        await state.update_data(request_number=message.text)
        await message.answer("Готов принять документы. Отправьте фото.")
        await state.set_state(Form.uploading_docs)

    @dispatcher.message(Form.uploading_docs, F.photo)
    async def handle_photo(message: Message, state: FSMContext):
        data = await state.get_data()
        driver = data.get("driver")
        request_number = data.get("request_number")
        file_id = message.photo[-1].file_id
        file = await bot.get_file(file_id)
        file_bytes = await bot.download_file(file.file_path)
        content = base64.b64encode(file_bytes.read()).decode("utf-8")

        # Загрузка в таблицу
        row = [driver, request_number, f"Документ", message.date.isoformat()]
        sheets_service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range="A:D",
            valueInputOption="RAW",
            body={"values": [row]}
        ).execute()

        await message.answer("Спасибо, документы приняты. Счастливого пути!")
        await state.clear()

    # Webhook
    async def on_startup(app):
        await bot.set_webhook(WEBHOOK_URL)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dispatcher, bot=bot).register(app, path="/webhook")
    app.on_startup.append(on_startup)
    setup_application(app, dispatcher, bot=bot)

    if __name__ == "__main__":
        web.run_app(app, port=8080)
""")

bot_code_path = "/mnt/data/bot.py"
with open(bot_code_path, "w") as f:
    f.write(bot_code)

bot_code_path
