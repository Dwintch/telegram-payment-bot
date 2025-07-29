import os
import json
import logging
from datetime import datetime
from collections import defaultdict, Counter

import telebot
from telebot import types
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# =======================
# Logging Configuration
# =======================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# =======================
# Load Environment
# =======================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID_REPORT = int(os.getenv("CHAT_ID_FOR_REPORT"))
THREAD_ID_REPORT = int(os.getenv("THREAD_ID_FOR_REPORT"))
THREAD_ID_ORDERS = int(os.getenv("THREAD_ID_FOR_REPORT2"))
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE")

assert BOT_TOKEN, "BOT_TOKEN is required"
assert CHAT_ID_REPORT, "CHAT_ID_FOR_REPORT is required"
assert THREAD_ID_REPORT, "THREAD_ID_FOR_REPORT is required"
assert THREAD_ID_ORDERS, "THREAD_ID_FOR_REPORT2 is required"
assert GOOGLE_SHEET_NAME, "GOOGLE_SHEET_NAME is required"
assert CREDENTIALS_FILE, "CREDENTIALS_FILE is required"

# =======================
# Bot Initialization
# =======================
bot = telebot.TeleBot(BOT_TOKEN)

# =======================
# Google Sheets Setup
# =======================
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).sheet1

# =======================
# Global States
# =======================
user_data = {}
user_states = {}  # for order system
orders = defaultdict(list)
position_counter = Counter()

TOP_COUNTER_FILE = "top_counter.json"
SHOP_NAMES = ["янтарь", "хайп", "полка"]

if os.path.exists(TOP_COUNTER_FILE):
    with open(TOP_COUNTER_FILE, "r", encoding="utf-8") as f:
        position_counter.update(json.load(f))

# =======================
# Helper Functions
# =======================
def save_counter():
    with open(TOP_COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump(position_counter, f, ensure_ascii=False)

def round_to_50(value):
    remainder = value % 50
    return int(value - remainder) if remainder < 25 else int(value + (50 - remainder))

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💰 Перевод", "💸 Возврат")
    markup.add("📄 Составить отчёт", "👀 Посмотреть сумму")
    markup.add("📦 Заказы", "🍎 Приём поставки")
    markup.add("✅ Отправить заказ")
    markup.add("❌ Отменить")
    return markup

def get_shop_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Янтарь", "Хайп", "Полка")
    return markup

def get_confirm_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ Отправить", "✏️ Изменить данные", "🗓 Изменить дату", "❌ Отмена")
    return markup

def shop_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    for shop in SHOP_NAMES:
        keyboard.add(types.InlineKeyboardButton(text=shop.capitalize(), callback_data=f"shop_{shop}"))
    return keyboard

# =======================
# Start Without /start
# =======================
@bot.message_handler(func=lambda m: m.text and m.chat.id not in user_data)
def auto_start(message):
    start(message)

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_data[chat_id] = {
        "shop": None, "transfers": [], "mode": "add",
        "cash": 0, "terminal": 0, "stage": "choose_shop",
        "date": datetime.now().strftime("%d.%m.%Y")
    }
    bot.send_message(chat_id, "Привет! Выбери режим: учёт или заказы.", reply_markup=shop_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("shop_"))
def handle_shop_selection(call):
    chat_id = call.message.chat.id
    selected_shop = call.data.split("_")[1]
    user_data[chat_id]["shop"] = selected_shop
    user_states[chat_id] = None
    bot.answer_callback_query(call.id, f"Выбран магазин: {selected_shop.capitalize()}")
    bot.send_message(chat_id, f"Магазин *{selected_shop.capitalize()}* выбран.\nВыберите действие:", 
                     parse_mode="Markdown", reply_markup=get_main_menu())

# =======================
# Заказы
# =======================
@bot.message_handler(func=lambda msg: msg.text == "📦 Заказы")
def handle_orders(msg):
    user_states[msg.chat.id] = "ordering"
    orders[msg.chat.id] = []
    bot.send_message(msg.chat.id, "Отправь позиции (через запятую или с новой строки):", reply_markup=get_main_menu())

@bot.message_handler(func=lambda msg: user_states.get(msg.chat.id) == "ordering")
def accumulate_order(msg):
    items = [i.strip() for part in msg.text.split("\n") for i in part.split(",") if i.strip()]
    orders[msg.chat.id].extend(items)
    bot.send_message(msg.chat.id, f"Текущий заказ:\n- " + "\n- ".join(orders[msg.chat.id]))

@bot.message_handler(func=lambda msg: msg.text == "✅ Отправить заказ")
def send_order(msg):
    if not orders.get(msg.chat.id):
        bot.send_message(msg.chat.id, "Заказ пуст. Добавьте позиции перед отправкой.")
        return
    order_text = f"🛒 Новый заказ от @{msg.from_user.username or msg.from_user.first_name}:\n" + "\n".join(f"- {item}" for item in orders[msg.chat.id])
    bot.send_message(chat_id=CHAT_ID_REPORT, text=order_text, message_thread_id=THREAD_ID_ORDERS)
    bot.send_message(msg.chat.id, "Заказ отправлен!", reply_markup=get_main_menu())
    orders[msg.chat.id] = []
    user_states[msg.chat.id] = None

# =======================
# Приём поставки
# =======================
@bot.message_handler(func=lambda msg: msg.text == "🍎 Приём поставки")
def receive_delivery(msg):
    chat_id = msg.chat.id
    if not orders.get(chat_id):
        bot.send_message(chat_id, "Нет активных заказов.")
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for idx, item in enumerate(orders[chat_id]):
        markup.add(types.InlineKeyboardButton(text=f"✅ {item}", callback_data=f"recv_{idx}"))
    markup.add(types.InlineKeyboardButton(text="🚚 Завершить приём", callback_data="recv_done"))

    bot.send_message(chat_id, "Выберите, что пришло:", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("recv_"))
def handle_receive_callback(call):
    chat_id = call.message.chat.id
    if call.data == "recv_done":
        if orders.get(chat_id):
            bot.send_message(chat_id, "Следующие позиции не были доставлены и перенесены:")
            bot.send_message(chat_id, "\n".join(f"- {item}" for item in orders[chat_id]))
        else:
            bot.send_message(chat_id, "Все позиции были доставлены!")
        return

    idx = int(call.data.split("_")[1])
    if chat_id in orders and 0 <= idx < len(orders[chat_id]):
        item = orders[chat_id].pop(idx)
        bot.answer_callback_query(call.id, f"{item} — принято")
        bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=None)
        receive_delivery(call.message)

# =======================
# Универсальный обработчик для цифр и текста
# =======================
@bot.message_handler(func=lambda msg: True)
def universal_handler(msg):
    chat_id = msg.chat.id
    text = msg.text.strip()

    if chat_id not in user_data:
        start(msg)
        return

    if text.replace(".", "", 1).isdigit():
        amount = float(text)
        user_data[chat_id]["transfers"].append(amount)
        bot.send_message(chat_id, f"✅ Учтён перевод: {amount:.2f}")
    elif user_states.get(chat_id) == "ordering":
        accumulate_order(msg)
    else:
        user_states[chat_id] = "ordering"
        orders[chat_id].extend([text])
        bot.send_message(chat_id, f"Добавлено в заказ:\n- {text}")

# =======================
# Start Bot
# =======================
if __name__ == "__main__":
    logger.info("Bot started.")
    bot.remove_webhook()
    bot.infinity_polling()
