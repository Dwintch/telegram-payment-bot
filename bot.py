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
    markup.add("📦 Заказы")
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
# Money Report Handlers
# =======================
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_data[chat_id] = {
        "shop": None, "transfers": [], "mode": "add",
        "cash": 0, "terminal": 0, "stage": "choose_shop",
        "date": datetime.now().strftime("%d.%m.%Y")
    }
    bot.send_message(chat_id, "Привет! Выбери режим: учёт или заказы.", reply_markup=get_shop_menu())

@bot.message_handler(func=lambda m: m.text in ["Янтарь", "Хайп", "Полка"])
def choose_shop(message):
    chat_id = message.chat.id
    user_data[chat_id].update({
        "shop": message.text, "transfers": [], "mode": "add",
        "cash": 0, "terminal": 0, "stage": "main",
        "date": datetime.now().strftime("%d.%m.%Y")
    })
    bot.send_message(chat_id, f"Выбран магазин: {message.text}", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: m.text == "💰 Перевод")
def handle_transfer(message):
    chat_id = message.chat.id
    user_data[chat_id]["mode"] = "add"
    user_data[chat_id]["stage"] = "amount_input"
    bot.send_message(chat_id, "Введите сумму перевода:")

@bot.message_handler(func=lambda m: m.text == "💸 Возврат")
def handle_return(message):
    chat_id = message.chat.id
    user_data[chat_id]["mode"] = "subtract"
    user_data[chat_id]["stage"] = "amount_input"
    bot.send_message(chat_id, "Введите сумму возврата:")

@bot.message_handler(func=lambda m: m.text == "👀 Посмотреть сумму")
def show_total(message):
    chat_id = message.chat.id
    total = sum(user_data.get(chat_id, {}).get("transfers", []))
    count = len(user_data.get(chat_id, {}).get("transfers", []))
    bot.send_message(chat_id, f"Сумма: {total}₽, Транзакций: {count}")

@bot.message_handler(func=lambda m: m.text == "📄 Составить отчёт")
def start_report(message):
    chat_id = message.chat.id
    user_data[chat_id]["stage"] = "cash_input"
    total = sum(user_data[chat_id]["transfers"])
    bot.send_message(chat_id, f"Переводов на: {total}₽. Введите сумму наличных:")

@bot.message_handler(func=lambda m: m.text.isdigit())
def handle_amount(message):
    chat_id = message.chat.id
    stage = user_data[chat_id]["stage"]
    amount = int(message.text)

    if stage in ["main", "amount_input"]:
        delta = amount if user_data[chat_id]["mode"] == "add" else -amount
        user_data[chat_id]["transfers"].append(delta)
        bot.send_message(chat_id, f"Текущая сумма: {sum(user_data[chat_id]['transfers'])}₽", reply_markup=get_main_menu())
        user_data[chat_id]["stage"] = "main"

    elif stage == "cash_input":
        user_data[chat_id]["cash"] = amount
        user_data[chat_id]["stage"] = "terminal_input"
        bot.send_message(chat_id, "Введите сумму по терминалу:")

    elif stage == "terminal_input":
        user_data[chat_id]["terminal"] = amount
        user_data[chat_id]["stage"] = "confirm_report"
        preview_report(chat_id)

def preview_report(chat_id):
    data = user_data[chat_id]
    shop = data["shop"]
    transfers = sum(data["transfers"])
    cash = data["cash"]
    terminal = data["terminal"]
    total = transfers + cash + terminal

    salary = round_to_50(total * 0.10)
    if shop == "Янтарь" and total < 40000:
        salary = 4000

    text = (
        f"📦 Магазин: {shop}\n📅 Дата: {data['date']}\n"
        f"💳 Переводы: {transfers}₽\n💵 Наличные: {cash}₽\n🏧 Терминал: {terminal}₽\n📊 Итого: {total}₽\n👔 ЗП: {salary}₽"
    )
    bot.send_message(chat_id, text, reply_markup=get_confirm_menu())

@bot.message_handler(func=lambda m: m.text == "✅ Отправить")
def confirm_and_send(message):
    chat_id = message.chat.id
    send_report(chat_id)
    bot.send_message(chat_id, "✅ Отчёт отправлен.", reply_markup=get_main_menu())

    user_data[chat_id].update({"transfers": [], "cash": 0, "terminal": 0, "stage": "main"})

def send_report(chat_id):
    data = user_data[chat_id]
    row = [data["date"], data["shop"], sum(data["transfers"]), data["cash"], data["terminal"], sum(data["transfers"])+data["cash"]+data["terminal"]]
    sheet.append_row(row)
    bot.send_message(CHAT_ID_REPORT, f"Отчёт по магазину {data['shop']} отправлен.", message_thread_id=THREAD_ID_REPORT)

# =======================
# Order System Handlers
# =======================
@bot.message_handler(func=lambda m: m.text == "📦 Заказы")
def orders_menu(message):
    user_states[message.from_user.id] = {"state": "choosing_shop"}
    bot.send_message(message.chat.id, "Выберите магазин:", reply_markup=shop_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("shop_"))
def shop_chosen(call):
    user_id = call.from_user.id
    shop = call.data.split("_")[1]
    user_states[user_id] = {"state": "writing_order", "shop": shop}
    bot.edit_message_text(chat_id=call.message.chat.id, message_id=call.message.message_id, text=f"Вы выбрали: {shop}\nВведите заказ:")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "writing_order")
def receive_order(message):
    user_id = message.from_user.id
    shop = user_states[user_id]["shop"]
    positions = [p.strip() for p in message.text.split("\n") if p.strip()]
    orders[shop].extend(positions)
    position_counter.update(positions)
    save_counter()

    formatted = "\n".join(f"▪️ {p}" for p in positions)
    bot.send_message(message.chat.id, f"Заказ для {shop}:\n{formatted}", parse_mode="HTML")
    bot.send_message(CHAT_ID_REPORT, f"🛒 Новый заказ для {shop}:\n{formatted}", parse_mode="HTML", message_thread_id=THREAD_ID_ORDERS)
    user_states.pop(user_id)

@bot.message_handler(commands=["топ_позиции"])
def top_positions(message):
    top = position_counter.most_common(10)
    result = [f"{i+1}. {item} — {count} раз(а)" for i, (item, count) in enumerate(top)]
    bot.send_message(message.chat.id, "\n".join(result) or "Нет заказов.")

# =======================
# Start Bot
# =======================
if __name__ == "__main__":
    logger.info("Bot started.")
    bot.remove_webhook()
    bot.infinity_polling()
