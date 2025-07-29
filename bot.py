import os
import json
import logging
from datetime import datetime
from collections import defaultdict

import telebot
from telebot import types
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# === ЗАГРУЗКА .ENV ===
load_dotenv()

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID_FOR_REPORT = -1002826712980
THREAD_ID_FOR_REPORT = 3
GOOGLE_SHEET_NAME = 'Отчёты'
CREDENTIALS_FILE = 'credentials.json'

bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}

# === GOOGLE SHEETS ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).sheet1

# === КНОПКИ ===
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

# === START ===
@bot.message_handler(func=lambda m: True)
def handle_any_message(message):
    chat_id = message.chat.id
    if chat_id not in user_data:
        user_data[chat_id] = {
            "shop": None,
            "transfers": [],
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "stage": "choose_shop",
            "date": datetime.now().strftime("%d.%m.%Y")
        }
        bot.send_message(chat_id, "Ну что по считаем копеечки! Выбери магазин:", reply_markup=get_shop_menu())
        return

    text = message.text
    if text in ["Янтарь", "Хайп", "Полка"]:
        user_data[chat_id].update({
            "shop": text,
            "transfers": [],
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "stage": "main",
            "date": datetime.now().strftime("%d.%m.%Y")
        })
        bot.send_message(chat_id, f"Выбран магазин: {text}", reply_markup=get_main_menu())
    elif text == "❌ Отменить":
        if user_data.get(chat_id, {}).get("shop"):
            user_data[chat_id].update({
                "mode": "add",
                "cash": 0,
                "terminal": 0,
                "stage": "main",
                "date": datetime.now().strftime("%d.%m.%Y")
            })
            bot.send_message(chat_id, "❌ Действие отменено. Выберите действие:", reply_markup=get_main_menu())
        else:
            bot.send_message(chat_id, "Сначала выбери магазин:", reply_markup=get_shop_menu())
    elif text == "💰 Перевод":
        user_data[chat_id]["mode"] = "add"
        user_data[chat_id]["stage"] = "amount_input"
        bot.send_message(chat_id, "Оп еще лавешечка капнула! Сколько пришло?:")
    elif text == "💸 Возврат":
        user_data[chat_id]["mode"] = "subtract"
        user_data[chat_id]["stage"] = "amount_input"
        bot.send_message(chat_id, "Смешно, возват на сумму:")
    elif text == "👀 Посмотреть сумму":
        total = sum(user_data.get(chat_id, {}).get("transfers", []))
        count = len(user_data.get(chat_id, {}).get("transfers", []))
        bot.send_message(chat_id, f"📊 Сумма переводов: {total}₽\nКол-во транзакций: {count}")
    elif text == "📄 Составить отчёт":
        total = sum(user_data[chat_id]["transfers"])
        user_data[chat_id]["stage"] = "cash_input"
        bot.send_message(chat_id, f"🧾 Переводов на сумму: {total}₽\nВведите сумму наличных:")
    elif text == "✅ Отправить":
        send_report(chat_id)
    elif text == "✏️ Изменить данные":
        user_data[chat_id]["stage"] = "cash_input"
        bot.send_message(chat_id, "Сколько наличных?:")
    elif text == "🗓 Изменить дату":
        user_data[chat_id]["stage"] = "custom_date_input"
        bot.send_message(chat_id, "Введите дату отчёта в формате ДД.ММ.ГГГГ:")
    elif user_data[chat_id].get("stage") == "custom_date_input":
        try:
            custom_date = datetime.strptime(text, "%d.%m.%Y")
            user_data[chat_id]["date"] = custom_date.strftime("%d.%m.%Y")
            user_data[chat_id]["stage"] = "confirm_report"
            bot.send_message(chat_id, f"✅ Дата изменена на: {user_data[chat_id]['date']}")
            preview_report(chat_id)
        except ValueError:
            bot.send_message(chat_id, "⚠️ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ:")
    elif text.isdigit():
        stage = user_data.get(chat_id, {}).get("stage", "main")
        mode = user_data[chat_id].get("mode", "add")
        amount = int(text)

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
            user_data[chat_id]["stage"] = "confirm_report"
            preview_report(chat_id)
    else:
        if user_data[chat_id].get("stage") == "main":
            items = [item.strip() for item in text.split(',') if item.strip()]
            formatted_items = "\n".join(f"• {item}" for item in items)
            bot.send_message(chat_id, f"🛒 Добавлено в заказ:\n{formatted_items}")
        else:
            bot.send_message(chat_id, "Выберите действие:", reply_markup=get_main_menu())

# === ПРЕДПРОСМОТР ОТЧЕТА ===
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

    if shop == "Янтарь":
        if total < 40000:
            salary = 4000
        else:
            each = round_to_50((total * 0.10) / 2)
            salary = each * 2
        salary_text = f"👔 ЗП: {salary}₽\n👤 По {each}₽ каждому"
    else:
        salary = max(2000, round_to_50(total * 0.10))
        salary_text = f"👔 ЗП: {salary}₽"

    report_text = (
        f"📦 Магазин: {shop}\n"
        f"📅 Дата: {date}\n"
        f"💳 Переводы: {transfers}₽\n"
        f"💵 Наличные: {cash}₽\n"
        f"🏧 Терминал: {terminal}₽\n"
        f"📊 Итого: {total}₽\n"
        f"{salary_text}"
    )

    bot.send_message(chat_id, report_text, reply_markup=get_confirm_menu())

# === ОТПРАВКА ОТЧЕТА ===
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
    bot.send_message(chat_id, "✅ Отчёт отправлен! Выбери магазин:", reply_markup=get_shop_menu())
    user_data[chat_id] = {}

# === ЗАПУСК ===
print("✅ Бот запущен...")
bot.infinity_polling()
