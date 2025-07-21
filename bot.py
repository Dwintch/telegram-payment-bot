import os
from dotenv import load_dotenv
import telebot
from telebot import types
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

CHAT_ID_FOR_REPORT = -1002826712980
THREAD_ID_FOR_REPORT = 3
GOOGLE_SHEET_NAME = 'Отчёты'
CREDENTIALS_FILE = 'credentials.json'

user_data = {}

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).sheet1

def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💰 Перевод", "💸 Возврат")
    markup.add("📄 Составить отчёт", "👀 Посмотреть сумму")
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

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_data[chat_id] = {
        "shop": None,
        "transfers": [],
        "mode": "add",
        "cash": 0,
        "terminal": 0,
        "stage": "choose_shop",
        "date": datetime.now().strftime("%d.%m.%Y"),
        "salary": 0
    }
    bot.send_message(chat_id, "Ну что по считаем копеечки! Выбери магазин:", reply_markup=get_shop_menu())

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
        "date": datetime.now().strftime("%d.%m.%Y"),
        "salary": 0
    })
    bot.send_message(chat_id, f"Выбран магазин: {message.text}", reply_markup=get_main_menu())

@bot.message_handler(func=lambda m: m.text == "❌ Отменить")
def cancel_action(message):
    chat_id = message.chat.id
    if user_data.get(chat_id, {}).get("shop"):
        user_data[chat_id].update({
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "stage": "main",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "salary": 0
        })
        bot.send_message(chat_id, "❌ Действие отменено. Выберите действие:", reply_markup=get_main_menu())
    else:
        bot.send_message(chat_id, "Сначала выбери магазин:", reply_markup=get_shop_menu())

@bot.message_handler(func=lambda m: m.text == "💰 Перевод")
def handle_transfer(message):
    chat_id = message.chat.id
    user_data[chat_id]["mode"] = "add"
    user_data[chat_id]["stage"] = "amount_input"
    bot.send_message(chat_id, "Оп еще лавешечка капнула! Сколько пришло?:")

@bot.message_handler(func=lambda m: m.text == "💸 Возврат")
def handle_return(message):
    chat_id = message.chat.id
    user_data[chat_id]["mode"] = "subtract"
    user_data[chat_id]["stage"] = "amount_input"
    bot.send_message(chat_id, "Смешно, возват на сумму:")

@bot.message_handler(func=lambda m: m.text == "👀 Посмотреть сумму")
def show_total(message):
    chat_id = message.chat.id
    total = sum(user_data[chat_id]["transfers"])
    count = len(user_data[chat_id]["transfers"])
    bot.send_message(chat_id, f"📊 Сумма переводов: {total}₽\nКол-во транзакций: {count}")

@bot.message_handler(func=lambda m: m.text == "📄 Составить отчёт")
def start_report(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        start(message)
        return
    total = sum(user_data[chat_id]["transfers"])
    user_data[chat_id]["stage"] = "cash_input"
    bot.send_message(chat_id, f"🧾 Переводов на сумму: {total}₽\nВведите сумму наличных:")

@bot.message_handler(func=lambda m: m.text.isdigit())
def handle_amount(message):
    chat_id = message.chat.id
    stage = user_data.get(chat_id, {}).get("stage", "main")
    mode = user_data[chat_id].get("mode", "add")
    amount = int(message.text)

    if stage in ["main", "amount_input"]:
        if mode == "subtract":
            user_data[chat_id]["transfers"].append(-amount)
            bot.send_message(chat_id, f"➖ Возврат: {amount}₽")
        else:
            user_data[chat_id]["transfers"].append(amount)
            bot.send_message(chat_id, f"✅ Добавлено: {amount}₽")
        total = sum(user_data[chat_id]["transfers"])
        bot.send_message(chat_id, f"💰 Текущая сумма: {total}₽", reply_markup=get_main_menu())
        user_data[chat_id]["mode"] = "add"
        user_data[chat_id]["stage"] = "main"

    elif stage == "cash_input":
        user_data[chat_id]["cash"] = amount
        user_data[chat_id]["stage"] = "terminal_input"
        bot.send_message(chat_id, "Сколько капнуло по терминалу:")

    elif stage == "terminal_input":
        user_data[chat_id]["terminal"] = amount
        shop = user_data[chat_id]["shop"]
        cash = user_data[chat_id]["cash"]

        if shop in ["Полка", "Хайп"]:
            salary = max(round(cash * 0.10), 2000)
        elif shop == "Янтарь":
            salary = max(round(cash * 0.05 * 2), 2000)
        else:
            salary = 0

        user_data[chat_id]["salary"] = salary
        user_data[chat_id]["stage"] = "confirm_report"
        preview_report(chat_id)

def preview_report(chat_id):
    data = user_data[chat_id]
    shop = data["shop"]
    transfers = sum(data["transfers"])
    cash = data["cash"]
    terminal = data["terminal"]
    total = transfers + cash + terminal
    date = data["date"]
    salary = data["salary"]

    report_text = (
        f"📦 Магазин: {shop}\n"
        f"📅 Дата: {date}\n"
        f"💳 Переводы: {transfers}₽\n"
        f"💵 Наличные: {cash}₽\n"
        f"🏧 Терминал: {terminal}₽\n"
        f"📊 Итого: {total}₽\n"
        f"💼 ЗП (не отправляется): {salary}₽"
    )
    bot.send_message(chat_id, report_text, reply_markup=get_confirm_menu())

@bot.message_handler(func=lambda m: m.text == "✅ Отправить")
def confirm_and_send(message):
    chat_id = message.chat.id
    send_report(chat_id)

@bot.message_handler(func=lambda m: m.text == "✏️ Изменить данные")
def edit_data(message):
    chat_id = message.chat.id
    user_data[chat_id]["stage"] = "cash_input"
    bot.send_message(chat_id, "Сколько наличных?:")

@bot.message_handler(func=lambda m: m.text == "🗓 Изменить дату")
def ask_for_custom_date(message):
    chat_id = message.chat.id
    user_data[chat_id]["stage"] = "custom_date_input"
    bot.send_message(chat_id, "Введите дату отчёта в формате ДД.ММ.ГГГГ:")

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get("stage") == "custom_date_input")
def handle_custom_date(message):
    chat_id = message.chat.id
    try:
        custom_date = datetime.strptime(message.text, "%d.%m.%Y")
        user_data[chat_id]["date"] = custom_date.strftime("%d.%m.%Y")
        user_data[chat_id]["stage"] = "confirm_report"
        bot.send_message(chat_id, f"✅ Дата изменена на: {user_data[chat_id]['date']}")
        preview_report(chat_id)
    except ValueError:
        bot.send_message(chat_id, "⚠️ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ:")

def send_report(chat_id):
    data = user_data[chat_id]
    shop = data["shop"]
    transfers = sum(data["transfers"])
    cash = data["cash"]
    terminal = data["terminal"]
    date = data["date"]

    report_text = (
        f"📦 Магазин: {shop}\n"
        f"📅 Дата: {date}\n"
        f"💳 Переводы: {transfers}₽\n"
        f"💵 Наличные: {cash}₽\n"
        f"🏧 Терминал: {terminal}₽\n"
        f"📊 Итого: {transfers + cash + terminal}₽"
    )

    sheet.append_row([date, shop, transfers, cash, terminal])
    bot.send_message(CHAT_ID_FOR_REPORT, report_text, message_thread_id=THREAD_ID_FOR_REPORT)
    bot.send_message(chat_id, "✅ Отчёт отправлен!", reply_markup=get_shop_menu())
    user_data[chat_id] = {}

@bot.message_handler(func=lambda message: True)
def handle_any_message(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        start(message)
    else:
        bot.send_message(chat_id, "Выберите действие:", reply_markup=get_main_menu())

print("✅ Бот запущен...")
bot.infinity_polling()
