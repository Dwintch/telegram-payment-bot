import asyncio
import os
import re
import json
from collections import defaultdict, Counter
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums.parse_mode import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties

from apscheduler.schedulers.asyncio import AsyncIOScheduler

# Настройки
BOT_TOKEN = os.getenv("BOT_TOKEN_2")
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID_2"))
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()
router = Router()

# Список магазинов
SHOP_NAMES = ["янтарь", "хайп", "полка"]

# FSM состояния
class OrderStates(StatesGroup):
    choosing_shop = State()
    writing_order = State()

# Хранилище заказов
orders = defaultdict(list)  # {shop: ["позиция 1", "позиция 2"]}
position_counter = Counter()  # Счётчик всех позиций
TOP_COUNTER_FILE = "top_counter.json"

# Загрузка счётчика из файла
if os.path.exists(TOP_COUNTER_FILE):
    with open(TOP_COUNTER_FILE, "r", encoding="utf-8") as f:
        position_counter.update(json.load(f))

# Сохранение счётчика в файл
def save_counter():
    with open(TOP_COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump(position_counter, f, ensure_ascii=False)

# Инлайн клавиатура выбора магазина
def shop_keyboard():
    buttons = [[InlineKeyboardButton(text=shop.capitalize(), callback_data=f"shop_{shop}")] for shop in SHOP_NAMES]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# Команда начала заказа
@router.message(F.text == "/заказ")
async def start_order(message: Message, state: FSMContext):
    await state.set_state(OrderStates.choosing_shop)
    await message.reply("Выберите магазин:", reply_markup=shop_keyboard())

# Обработка выбора магазина
@router.callback_query(F.data.startswith("shop_"))
async def shop_chosen(callback: CallbackQuery, state: FSMContext):
    shop = callback.data.split("_")[1]
    await state.update_data(shop=shop)
    await state.set_state(OrderStates.writing_order)
    await callback.message.edit_text(f"Вы выбрали магазин: <b>{shop}</b>\nТеперь введите список заказа:")
    await callback.answer()

# Обработка текста заказа
@router.message(OrderStates.writing_order)
async def receive_order(message: Message, state: FSMContext):
    data = await state.get_data()
    shop = data.get("shop")
    text = message.text.replace(",", "\n")
    positions = [line.strip() for line in text.split("\n") if line.strip()]
    orders[shop].extend(positions)

    # Обновляем счётчик
    position_counter.update(positions)
    save_counter()

    formatted = "\n".join(f"▪️ {p}" for p in positions)
    await message.answer(f"✅ Заказ принят для <b>{shop}</b>:\n{formatted}")

    # Отправляем в группу
    await bot.send_message(chat_id=GROUP_CHAT_ID, text=f"🛒 <b>Новый заказ для {shop}</b>:\n{formatted}")
    await state.clear()

# Просмотр всех заказов
@router.message(F.text == "/все_заказы")
async def all_orders(message: Message):
    if not orders:
        await message.reply("Нет заказов.")
        return
    msg = ["📦 <b>Текущие заказы:</b>"]
    for shop, items in orders.items():
        msg.append(f"\n<b>{shop.capitalize()}:</b>")
        for item in items:
            msg.append(f"▪️ {item}")
    await message.reply("\n".join(msg))

# Топ позиций
@router.message(F.text == "/топ_позиции")
async def top_positions(message: Message):
    if not position_counter:
        await message.reply("Пока нет заказов.")
        return
    top = position_counter.most_common(10)
    result = ["📈 <b>Топ популярных позиций:</b>"]
    for i, (item, count) in enumerate(top, 1):
        result.append(f"{i}. {item} — <b>{count}</b> раз(а)")
    await message.reply("\n".join(result))

# Запуск бота через polling
async def main():
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    print("🤖 Бот запущен через polling...")
    asyncio.run(main())
