import os
import json
from collections import defaultdict, Counter
from datetime import datetime

import telebot
from telebot import types
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

# === ENV ===
BOT_TOKEN = os.getenv("BOT_TOKEN_1")
CHAT_ID_FOR_REPORT = int(os.getenv("CHAT_ID_FOR_REPORT"))
THREAD_ID_FOR_REPORT = int(os.getenv("THREAD_ID_FOR_REPORT"))
THREAD_ID_FOR_ORDER = int(os.getenv("THREAD_ID_FOR_ORDER"))
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME")
CREDENTIALS_FILE = os.getenv("CREDENTIALS_FILE")

# === Check ENV ===
if not all([BOT_TOKEN, CHAT_ID_FOR_REPORT, THREAD_ID_FOR_REPORT, THREAD_ID_FOR_ORDER, GOOGLE_SHEET_NAME, CREDENTIALS_FILE]):
    raise ValueError("Одна или несколько переменных окружения не заданы")

# === Init Bot ===
bot = telebot.TeleBot(BOT_TOKEN)

# === Init Sheets ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).sheet1

# === DATA ===
user_data = {}
orders = defaultdict(list)
position_counter = Counter()
user_states = {}  # user_id -> {'state': ..., 'shop': ...}
TOP_COUNTER_FILE = "top_counter.json"

# === Load previous positions ===
if os.path.exists(TOP_COUNTER_FILE):
    with open(TOP_COUNTER_FILE, "r", encoding="utf-8") as f:
        position_counter.update(json.load(f))

# === Menus ===
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💰 Переводы", "📦 Заказы")
    return markup

def get_shop_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Янтарь", "Хайп", "Полка")
    markup.add("🔙 Назад")
    return markup

def get_money_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💰 Перевод", "💸 Возврат")
    markup.add("📄 Составить отчёт", "👀 Посмотреть сумму")
    markup.add("❌ Отменить", "📦 К заказам")
    return markup

def get_confirm_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ Отправить", "✏️ Изменить данные", "🗓 Изменить дату", "❌ Отмена")
    return markup

def shop_keyboard_inline():
    keyboard = types.InlineKeyboardMarkup()
    for shop in ["янтарь", "хайп", "полка"]:
        keyboard.add(types.InlineKeyboardButton(text=shop.capitalize(), callback_data=f"shop_{shop}"))
    return keyboard

# === General Start ===
@bot.message_handler(commands=["start"])
def start(message):
    chat_id = message.chat.id
    bot.send_message(chat_id, "Выберите режим:", reply_markup=get_main_menu())

# === Navigation ===
@bot.message_handler(func=lambda m: m.text == "📦 Заказы")
def order_mode(message):
    user_states[message.from_user.id] = {"state": "choosing_shop"}
    bot.send_message(message.chat.id, "Выберите магазин:", reply_markup=shop_keyboard_inline())

@bot.message_handler(func=lambda m: m.text == "💰 Переводы")
def money_mode(message):
    chat_id = message.chat.id
    user_data[chat_id] = {
        "shop": None, "transfers": [], "mode": "add",
        "cash": 0, "terminal": 0, "stage": "choose_shop",
        "date": datetime.now().strftime("%d.%m.%Y")
    }
    bot.send_message(chat_id, "Выберите магазин:", reply_markup=get_shop_menu())

@bot.message_handler(func=lambda m: m.text == "📦 К заказам")
def go_to_orders(message):
    order_mode(message)

@bot.message_handler(func=lambda m: m.text == "🔙 Назад")
def back_to_main(message):
    start(message)

# === Order Flow ===
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
    shop = user_states[user_id]["shop"]
    positions = [line.strip() for line in message.text.replace(",", "\n").split("\n") if line.strip()]

    orders[shop].extend(positions)
    position_counter.update(positions)

    with open(TOP_COUNTER_FILE, "w", encoding="utf-8") as f:
        json.dump(position_counter, f, ensure_ascii=False)

    formatted = "\n".join(f"▪️ {p}" for p in positions)
    bot.send_message(message.chat.id, f"✅ Заказ принят для <b>{shop.capitalize()}</b>:\n{formatted}", parse_mode="HTML")

    bot.send_message(
        CHAT_ID_FOR_REPORT,
        f"🛒 <b>Новый заказ для {shop.capitalize()}</b>:\n{formatted}",
        parse_mode="HTML",
        message_thread_id=THREAD_ID_FOR_ORDER,
    )

    user_states.pop(user_id, None)

# === Money Flow ===
@bot.message_handler(func=lambda m: m.text in ["Янтарь", "Хайп", "Полка"])
def choose_shop(message):
    chat_id = message.chat.id
    user_data[chat_id].update({
        "shop": message.text,
        "transfers": [],
        "mode": "add",
        "cash": 0,
        "terminal": 0,
        "stage": "main",
        "date": datetime.now().strftime("%d.%m.%Y")
    })
    bot.send_message(chat_id, f"Выбран магазин: {message.text}", reply_markup=get_money_menu())

@bot.message_handler(func=lambda m: m.text == "❌ Отменить")
def cancel_action(message):
    chat_id = message.chat.id
    if user_data.get(chat_id, {}).get("shop"):
        user_data[chat_id].update({"mode": "add", "cash": 0, "terminal": 0, "stage": "main"})
        bot.send_message(chat_id, "❌ Действие отменено.", reply_markup=get_money_menu())
    else:
        bot.send_message(chat_id, "Сначала выбери магазин:", reply_markup=get_shop_menu())

@bot.message_handler(func=lambda m: m.text == "💰 Перевод")
def handle_transfer(message):
    chat_id = message.chat.id
    user_data[chat_id]["mode"] = "add"
    user_data[chat_id]["stage"] = "amount_input"
    bot.send_message(chat_id, "Сколько пришло?")

@bot.message_handler(func=lambda m: m.text == "💸 Возврат")
def handle_return(message):
    chat_id = message.chat.id
    user_data[chat_id]["mode"] = "subtract"
    user_data[chat_id]["stage"] = "amount_input"
    bot.send_message(chat_id, "Сумма возврата:")

@bot.message_handler(func=lambda m: m.text == "👀 Посмотреть сумму")
def show_total(message):
    chat_id = message.chat.id
    total = sum(user_data.get(chat_id, {}).get("transfers", []))
    count = len(user_data.get(chat_id, {}).get("transfers", []))
    bot.send_message(chat_id, f"📊 Сумма: {total}₽\nТранзакций: {count}")

@bot.message_handler(func=lambda m: m.text == "📄 Составить отчёт")
def start_report(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        money_mode(message)
        return
    total = sum(user_data[chat_id]["transfers"])
    user_data[chat_id]["stage"] = "cash_input"
    bot.send_message(chat_id, f"🧾 Переводов: {total}₽\nВведите сумму наличных:")

@bot.message_handler(func=lambda m: m.text.isdigit())
def handle_amount(message):
    chat_id = message.chat.id
    stage = user_data.get(chat_id, {}).get("stage", "main")
    mode = user_data[chat_id].get("mode", "add")
    amount = int(message.text)

    if stage in ["main", "amount_input"]:
        user_data[chat_id]["transfers"].append(-amount if mode == "subtract" else amount)
        user_data[chat_id]["stage"] = "main"
        bot.send_message(chat_id, f"Текущая сумма: {sum(user_data[chat_id]['transfers'])}₽", reply_markup=get_money_menu())
    elif stage == "cash_input":
        user_data[chat_id]["cash"] = amount
        user_data[chat_id]["stage"] = "terminal_input"
        bot.send_message(chat_id, "Сумма по терминалу:")
    elif stage == "terminal_input":
        user_data[chat_id]["terminal"] = amount
        user_data[chat_id]["stage"] = "confirm_report"
        preview_report(chat_id)

@bot.message_handler(func=lambda m: m.text == "✅ Отправить")
def confirm_and_send(message):
    chat_id = message.chat.id
    send_report(chat_id)
    user_data[chat_id].update({"stage": "main", "transfers": [], "cash": 0, "terminal": 0})
    bot.send_message(chat_id, "✅ Отчёт отправлен.", reply_markup=get_money_menu())

@bot.message_handler(func=lambda m: m.text == "✏️ Изменить данные")
def edit_data(message):
    user_data[message.chat.id]["stage"] = "amount_input"
    bot.send_message(message.chat.id, "Введите сумму заново:")

@bot.message_handler(func=lambda m: m.text == "🗓 Изменить дату")
def change_date(message):
    user_data[message.chat.id]["stage"] = "date_input"
    bot.send_message(message.chat.id, "Введите дату в формате ДД.ММ.ГГГГ")

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get("stage") == "date_input")
def set_date(message):
    try:
        datetime.strptime(message.text, "%d.%m.%Y")
        user_data[message.chat.id]["date"] = message.text
        user_data[message.chat.id]["stage"] = "confirm_report"
        preview_report(message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, "❌ Неверный формат даты")

# === Helpers ===
def round_to_50(value):
    remainder = value % 50
    return int(value - remainder) if remainder < 25 else int(value + (50 - remainder))

def preview_report(chat_id):
    data = user_data[chat_id]
    shop = data["shop"]
    transfers = sum(data["transfers"])
    cash = data["cash"]
    terminal = data["terminal"]
    total = transfers + cash + terminal
    date = data["date"]

    salary = 4000 if shop == "Янтарь" and total < 40000 else round_to_50(total * 0.10)
    salary_text = f"👔 ЗП: {salary}₽"

    report = (
        f"📦 Магазин: {shop}\n📅 Дата: {date}\n💳 Переводы: {transfers}₽\n💵 Наличные: {cash}₽\n🏧 Терминал: {terminal}₽\n📊 Итого: {total}₽\n{salary_text}"
    )
    bot.send_message(chat_id, report, reply_markup=get_confirm_menu())

def send_report(chat_id):
    data = user_data[chat_id]
    transfers = sum(data["transfers"])
    cash = data["cash"]
    terminal = data["terminal"]
    total = transfers + cash + terminal
    shop = data["shop"]
    date = data["date"]
    salary = 4000 if shop == "Янтарь" and total < 40000 else round_to_50(total * 0.10)

    sheet.append_row([date, shop, transfers, cash, terminal, total, salary])

    bot.send_message(
        CHAT_ID_FOR_REPORT,
        f"📦 Магазин: {shop}\n📅 {date}\n💳 Переводы: {transfers}₽\n💵 Наличные: {cash}₽\n🏧 Терминал: {terminal}₽\n📊 Итого: {total}₽\n👔 ЗП: {salary}₽",
        message_thread_id=THREAD_ID_FOR_REPORT
    )

# === Start polling ===
if __name__ == "__main__":
    print("✅ Бот запущен...")
    bot.remove_webhook()
    bot.infinity_polling()
