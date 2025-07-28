import os
import json
from collections import defaultdict, Counter

import telebot
from telebot import types
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN_2")
group_chat_id_env = os.getenv("GROUP_CHAT_ID_2")

if group_chat_id_env is None:
    raise RuntimeError("Переменная окружения GROUP_CHAT_ID_2 не установлена!")

GROUP_CHAT_ID = int(group_chat_id_env)

bot = telebot.TeleBot(BOT_TOKEN)

SHOP_NAMES = ["янтарь", "хайп", "полка"]

TOP_COUNTER_FILE = "top_counter.json"

orders = defaultdict(list)
position_counter = Counter()

# Загрузка счётчика
if os.path.exists(TOP_COUNTER_FILE):
    with open(TOP_COUNTER_FILE, "r", encoding="utf-8") as f:
        position_counter.update(json.load(f))

user_states = {}  # user_id -> state info


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
        text=f"Вы выбрали магазин: <b>{shop}</b>\nТеперь введите список заказа:",
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
    bot.send_message(message.chat.id, f"✅ Заказ принят для <b>{shop}</b>:\n{formatted}", parse_mode="HTML")

    # Отправляем в группу
    bot.send_message(GROUP_CHAT_ID, f"🛒 <b>Новый заказ для {shop}</b>:\n{formatted}", parse_mode="HTML")

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


if __name__ == "__main__":
    print("✅ Бот 2 запущен...")
    bot.infinity_polling()
