import os
import json
from collections import defaultdict, Counter

import telebot
from telebot import types
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN_2")
GROUP_CHAT_ID_ENV = os.getenv("CHAT_ID_FOR_REPORT")
THREAD_ID_ENV = os.getenv("THREAD_ID_FOR_REPORT2")  # Обрати внимание на переменную

if BOT_TOKEN is None:
    raise RuntimeError("Переменная окружения BOT_TOKEN_2 не установлена!")

if GROUP_CHAT_ID_ENV is None:
    raise RuntimeError("Переменная окружения CHAT_ID_FOR_REPORT не установлена!")

if THREAD_ID_ENV is None:
    raise RuntimeError("Переменная окружения THREAD_ID_FOR_REPORT2 не установлена!")

GROUP_CHAT_ID = int(GROUP_CHAT_ID_ENV)
THREAD_ID = int(THREAD_ID_ENV)

bot = telebot.TeleBot(BOT_TOKEN)

SHOP_NAMES = ["янтарь", "хайп", "полка"]
TOP_COUNTER_FILE = "top_counter.json"

orders = defaultdict(list)
position_counter = Counter()
user_states = {}  # user_id -> состояние пользователя


# Загрузка счётчика позиций из файла
if os.path.exists(TOP_COUNTER_FILE):
    with open(TOP_COUNTER_FILE, "r", encoding="utf-8") as f:
        position_counter.update(json.load(f))


def save_counter():
    with open(TOP_COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump(position_counter, f, ensure_ascii=False)


def shop_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    for shop in SHOP_NAMES:
        keyboard.add(types.InlineKeyboardButton(text=shop.capitalize(), callback_data=f"shop_{shop}"))
    return keyboard


@bot.message_handler(commands=["заказ"])
def start_order(message):
    user_states[message.from_user.id] = {"state": "choosing_shop"}
    bot.send_message(message.chat.id, "Выберите магазин:", reply_markup=shop_keyboard())


@bot.callback_query_handler(func=lambda call: call.data.startswith("shop_"))
def shop_chosen(call):
    user_id = call.from_user.id
    shop = call.data.split("_")[1]
    user_states[user_id] = {"state": "writing_order", "shop": shop}

    bot.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=f"Вы выбрали магазин: <b>{shop.capitalize()}</b>\nТеперь введите список заказа:",
        parse_mode="HTML",
    )
    bot.answer_callback_query(call.id)


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "writing_order")
def receive_order(message):
    user_id = message.from_user.id
    data = user_states.get(user_id)
    if not data:
        bot.send_message(message.chat.id, "Пожалуйста, начните заказ с команды /заказ")
        return

    shop = data["shop"]
    text = message.text.replace(",", "\n")
    positions = [line.strip() for line in text.split("\n") if line.strip()]
    orders[shop].extend(positions)

    position_counter.update(positions)
    save_counter()

    formatted = "\n".join(f"▪️ {p}" for p in positions)
    bot.send_message(message.chat.id, f"✅ Заказ принят для <b>{shop.capitalize()}</b>:\n{formatted}", parse_mode="HTML")

    # Отправляем в группу в тему с ID THREAD_ID
    bot.send_message(
        GROUP_CHAT_ID,
        f"🛒 <b>Новый заказ для {shop.capitalize()}</b>:\n{formatted}",
        parse_mode="HTML",
        message_thread_id=THREAD_ID,
    )

    # Сброс состояния
    user_states.pop(user_id, None)


@bot.message_handler(commands=["все_заказы"])
def all_orders(message):
    if not orders:
        bot.send_message(message.chat.id, "Нет заказов.")
        return
    msg = ["📦 <b>Текущие заказы:</b>"]
    for shop, items in orders.items():
        msg.append(f"\n<b>{shop.capitalize()}:</b>")
        for item in items:
            msg.append(f"▪️ {item}")
    bot.send_message(message.chat.id, "\n".join(msg), parse_mode="HTML")


@bot.message_handler(commands=["топ_позиции"])
def top_positions(message):
    if not position_counter:
        bot.send_message(message.chat.id, "Пока нет заказов.")
        return
    top = position_counter.most_common(10)
    result = ["📈 <b>Топ популярных позиций:</b>"]
    for i, (item, count) in enumerate(top, 1):
        result.append(f"{i}. {item} — <b>{count}</b> раз(а)")
    bot.send_message(message.chat.id, "\n".join(result), parse_mode="HTML")


def run_bot2():
    print("✅ Бот 2 запущен...")
    bot.infinity_polling()


if __name__ == "__main__":
    run_bot2()
