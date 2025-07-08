import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiohttp import web
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

API_TOKEN = os.environ.get("API_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")
OWNER_ID = 769063484  # Твой Telegram ID

bot = Bot(token=API_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

class DocFSM(StatesGroup):
    waiting_for_driver = State()
    waiting_for_request_number = State()
    waiting_for_photos = State()

@dp.message(F.text == "/start")
async def start(message: Message, state: FSMContext):
    kb = InlineKeyboardBuilder()
    for name in ["Еремин", "Уранов", "Новиков"]:
        kb.button(text=name, callback_data=name)
    await message.answer("Кто вы?", reply_markup=kb.as_markup())
    await state.set_state(DocFSM.waiting_for_driver)

@dp.callback_query(DocFSM.waiting_for_driver)
async def driver_chosen(callback: CallbackQuery, state: FSMContext):
    await state.update_data(driver=callback.data)
    await callback.message.answer(f"Принято. Введите номер заявки:")
    await state.set_state(DocFSM.waiting_for_request_number)
    await callback.answer()

@dp.message(DocFSM.waiting_for_request_number)
async def get_request_number(message: Message, state: FSMContext):
    await state.update_data(request_number=message.text)
    await message.answer("Готов принять документы. Отправьте фото:")
    await state.set_state(DocFSM.waiting_for_photos)

@dp.message(DocFSM.waiting_for_photos, F.photo)
async def get_photos(message: Message, state: FSMContext):
    data = await state.get_data()
    driver = data["driver"]
    request_number = data["request_number"]
    caption = f"📄 Документы от {driver}\nЗаявка: {request_number}"

    for photo in message.photo:
        await bot.send_photo(chat_id=OWNER_ID, photo=photo.file_id, caption=caption)
        break  # берём только последнее фото

    await message.answer("Спасибо, документы приняты. Счастливого пути!")
    await state.clear()

@dp.message()
async def fallback(message: Message):
    await message.answer("Пожалуйста, начните с команды /start.")

# Webhook запуск
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
