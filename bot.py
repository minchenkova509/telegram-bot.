import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.enums import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.webhook.aiohttp_server import SimpleRequestHandler
from aiohttp import web

# --- Настройки ---
ADMINS = [769063484]
DRIVERS = ["Еремин", "Уранов", "Новиков"]
API_TOKEN = "BOT_TOKEN_HERE"

# --- Переменные ---
driver_states = {}
driver_zayavki = {}
zayavki = {}

# --- Логика ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, default=bot.DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- Обработка /start ---
@dp.message(F.text == "/start")
async def start(message: Message):
    builder = InlineKeyboardBuilder()
    for driver in DRIVERS:
        builder.button(text=driver, callback_data=f"select_driver:{driver}")
    await message.answer("Выберите себя:", reply_markup=builder.as_markup())

# --- Выбор водителя ---
@dp.callback_query(F.data.startswith("select_driver:"))
async def choose_driver(callback: CallbackQuery):
    driver = callback.data.split(":")[1]
    driver_states[callback.from_user.id] = {"name": driver, "stage": "menu"}
    builder = InlineKeyboardBuilder()
    builder.button(text="Мои заявки", callback_data="my_zayavki")
    await callback.message.answer(f"Привет, {driver}!", reply_markup=builder.as_markup())
    await callback.answer()

# --- Просмотр заявок ---
@dp.callback_query(F.data == "my_zayavki")
async def show_zayavki(callback: CallbackQuery):
    user_id = callback.from_user.id
    name = driver_states.get(user_id, {}).get("name")
    relevant = driver_zayavki.get(name, [])

    if not relevant:
        await callback.message.answer("Нет заявок. Введите вручную: /manual")
        return

    builder = InlineKeyboardBuilder()
    for z in relevant:
        builder.button(text=z, callback_data=f"select_z:{z}")
    await callback.message.answer("Выбери заявку:", reply_markup=builder.as_markup())
    await callback.answer()

# --- Водитель выбирает заявку ---
@dp.callback_query(F.data.startswith("select_z:"))
async def pick_z(callback: CallbackQuery):
    z_number = callback.data.split(":")[1]
    driver_states[callback.from_user.id]["selected"] = z_number
    driver_states[callback.from_user.id]["stage"] = "waiting_doc"
    await callback.message.answer("Отправьте документы по заявке в виде фото")
    await callback.answer()

# --- Принимаем документы ---
@dp.message(F.photo)
async def handle_photo(message: Message):
    state = driver_states.get(message.from_user.id, {})
    if state.get("stage") != "waiting_doc":
        return

    z_number = state.get("selected")
    name = state.get("name")

    if z_number and name:
        for admin_id in ADMINS:
            await bot.send_photo(admin_id, message.photo[-1].file_id,
                                 caption=f"Документы от {name} по заявке {z_number}")
        await message.answer("✅ Спасибо, документы отправлены!")
        driver_states[message.from_user.id]["stage"] = "menu"

# --- Команда /manual ---
@dp.message(F.text == "/manual")
async def manual_entry(message: Message):
    driver_states[message.from_user.id]["stage"] = "manual_wait"
    await message.answer("Введите номер заявки:")

# --- Получаем номер от водителя ---
@dp.message(F.text.regexp(r"^\d+$"))
async def save_manual(message: Message):
    state = driver_states.get(message.from_user.id, {})
    if state.get("stage") == "manual_wait":
        driver_states[message.from_user.id]["selected"] = message.text
        driver_states[message.from_user.id]["stage"] = "waiting_doc"
        await message.answer("Теперь отправьте фото документов")

# --- Админ: загрузка заявки ---
@dp.message(F.photo & F.from_user.id.in_(ADMINS))
async def admin_zayavka(message: Message):
    driver_states[message.from_user.id] = {"stage": "await_z_number", "photo": message.photo[-1].file_id}
    builder = InlineKeyboardBuilder()
    for d in DRIVERS:
        builder.button(text=d, callback_data=f"admin_driver:{d}")
    await message.answer("Кому эта заявка?", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("admin_driver:"))
async def assign_driver(callback: CallbackQuery):
    driver = callback.data.split(":")[1]
    state = driver_states.get(callback.from_user.id)
    if not state or "photo" not in state:
        await callback.answer("Ошибка. Нет сохранённого фото.", show_alert=True)
        return

    driver_states[callback.from_user.id]["assign_to"] = driver
    driver_states[callback.from_user.id]["stage"] = "await_number"
    await callback.message.answer("Введите номер заявки:")
    await callback.answer()

@dp.message(F.text & F.from_user.id.in_(ADMINS))
async def save_zayavka(message: Message):
    state = driver_states.get(message.from_user.id)
    if not state or state.get("stage") != "await_number":
        return

    number = message.text
    driver = state.get("assign_to")
    photo = state.get("photo")

    zayavki[number] = {"photo": photo, "driver": driver}
    driver_zayavki.setdefault(driver, []).append(number)

    await message.answer(f"✅ Заявка {number} отправлена {driver}")
    driver_states[message.from_user.id] = {}

# --- Webhook ---
async def on_startup(_: web.Application):
    await bot.set_webhook("https://your-webhook-url/webhook")

async def on_shutdown(_: web.Application):
    await bot.delete_webhook()

app = web.Application()
SimpleRequestHandler(dispatcher=dp, bot=bot).register(app, path="/webhook")
app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == '__main__':
    web.run_app(app, host="0.0.0.0", port=8080)
