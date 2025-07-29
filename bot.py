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
THREAD_ID_FOR_ORDER = 4
GOOGLE_SHEET_NAME = 'Отчёты'
CREDENTIALS_FILE = 'credentials.json'

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
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
    markup.add("🛍 Заказ", "📦 Прием поставки")
    markup.add("❌ Отменить", "🔁 Повторить заказ")
    return markup

def get_shop_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Янтарь", "Хайп", "Полка")
    return markup

def get_confirm_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ Отправить", "✏️ Изменить данные", "🗓 Изменить дату", "❌ Отмена")
    return markup

# === ВСПОМОГАТЕЛЬНЫЕ ===
def sanitize_input(text):
    return [item.strip() for item in text.split(',') if item.strip()]

# === ОБРАБОТКА ФОТО ===
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    user = user_data.get(chat_id)
    if not user or user.get("stage") != "order_input":
        bot.send_message(chat_id, "📷 Фото получено, но вы сейчас не оформляете заказ.")
        return
    file_id = message.photo[-1].file_id
    user.setdefault("order_photos", []).append(file_id)
    bot.send_message(chat_id, "📸 Фото добавлено к заказу!")

# === ОБРАБОТКА ТЕКСТА ===
@bot.message_handler(func=lambda m: True)
def handle_any_message(message):
    chat_id = message.chat.id
    text = message.text.strip()

    # Инициализация данных пользователя
    if chat_id not in user_data:
        user_data[chat_id] = {
            "shop": None,                # магазин для переводов
            "order_shop": None,          # магазин для заказов
            "transfers": [],
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "stage": "choose_shop",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "order_items": [],
            "order_photos": [],
            "order_date": None,
            "pending_delivery": [],
            "last_order": []
        }
        bot.send_message(chat_id, "Ну что, поcчитаем копеечки! Выбери магазин:", reply_markup=get_shop_menu())
        return

    user = user_data[chat_id]

    # Выбор магазина для переводов (основной магазин)
    if user["stage"] == "choose_shop" and text in ["Янтарь", "Хайп", "Полка"]:
        user.update({
            "shop": text,
            "transfers": [],
            "order_items": [],
            "pending_delivery": [],
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "stage": "main",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "order_shop": None,
            "order_photos": [],
            "order_date": None
        })
        bot.send_message(chat_id, f"Выбран магазин для переводов: <b>{text}</b>", reply_markup=get_main_menu())
        return

    # Если нажали "🛍 Заказ" — выбираем магазин для заказа с подсказкой
    if text == "🛍 Заказ":
        user["stage"] = "order_choose_shop"
        bot.send_message(chat_id,
                         "Если не можете описать товар словами нормально — ПРИКРЕПЛЯЙТЕ ФОТО ТОВАРА!\n"
                         "Выберите магазин для заказа:", reply_markup=get_shop_menu())
        return

    # Выбор магазина для заказа
    if user["stage"] == "order_choose_shop" and text in ["Янтарь", "Хайп", "Полка"]:
        user["order_shop"] = text
        user["order_items"] = []
        user["order_photos"] = []
        user["order_date"] = datetime.now().strftime("%d.%m.%Y")
        user["stage"] = "order_input"
        bot.send_message(chat_id,
                         f"Выбран магазин для заказа: <b>{text}</b>\n"
                         "Введите заказ (товары через запятую):")
        return

    # Ввод заказа (список товаров через запятую)
    if user["stage"] == "order_input" and text != "✅ Отправить":
        items = sanitize_input(text)
        user["order_items"].extend(items)
        user["last_order"] = items[:]
        bot.send_message(chat_id, "🛒 Товары добавлены в заказ:")
        for item in items:
            bot.send_message(chat_id, f"• {item}")
        bot.send_message(chat_id, "Можешь прикрепить фото или нажми ✅ Отправить", reply_markup=get_confirm_menu())
        return

    # Отправка заказа
    if text == "✅ Отправить" and user["stage"] == "order_input":
        send_order(chat_id)
        user["stage"] = "main"
        return

    # Остальной функционал (переводы, отчёты, прием поставки, повторы, отмена)
    if text in ["Янтарь", "Хайп", "Полка"]:
        # Меняем магазин для переводов, не трогаем заказ
        user.update({
            "shop": text,
            "transfers": [],
            "order_items": [],
            "pending_delivery": [],
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "stage": "main",
            "date": datetime.now().strftime("%d.%m.%Y")
        })
        bot.send_message(chat_id, f"Выбран магазин для переводов: <b>{text}</b>", reply_markup=get_main_menu())
        return

    if text == "❌ Отменить":
        user.update({"mode": "add", "cash": 0, "terminal": 0, "stage": "main"})
        bot.send_message(chat_id, "❌ Действие отменено. Выберите действие:", reply_markup=get_main_menu())
        return

    if text == "💰 Перевод":
        user["mode"] = "add"
        user["stage"] = "amount_input"
        bot.send_message(chat_id, "Оп, лавешечка капнула! Сколько пришло?:")
        return

    if text == "💸 Возврат":
        user["mode"] = "subtract"
        user["stage"] = "amount_input"
        bot.send_message(chat_id, "Смешно, возврат на сумму:")
        return

    if text == "👀 Посмотреть сумму":
        total = sum(user["transfers"])
        count = len(user["transfers"])
        bot.send_message(chat_id, f"📊 Сумма переводов: <b>{total}₽</b>\nКол-во транзакций: {count}")
        return

    if text == "📄 Составить отчёт":
        user["stage"] = "cash_input"
        total = sum(user["transfers"])
        bot.send_message(chat_id, f"🧾 Переводов на сумму: <b>{total}₽</b>\nВведите сумму наличных:")
        return

    if text == "📦 Прием поставки":
        if user["pending_delivery"]:
            items = "\n".join(f"• {item}" for item in user["pending_delivery"])
            bot.send_message(chat_id, f"Выберите что приехало (введите через запятую):\n{items}")
            user["stage"] = "delivery_confirm"
        else:
            bot.send_message(chat_id, "Нет отложенных товаров на поставку.")
        return

    if text == "🔁 Повторить заказ":
        if user["last_order"]:
            user["order_items"].extend(user["last_order"])
            bot.send_message(chat_id, "🔁 Заказ повторён.")
            for item in user["last_order"]:
                bot.send_message(chat_id, f"• {item}")
        else:
            bot.send_message(chat_id, "Нет последнего заказа для повтора.")
        return

    if text == "✏️ Изменить данные":
        user["stage"] = "cash_input"
        bot.send_message(chat_id, "Сколько наличных?:")
        return

    if text == "🗓 Изменить дату":
        user["stage"] = "custom_date_input"
        bot.send_message(chat_id, "Введите дату отчёта в формате ДД.ММ.ГГГГ:")
        return

    # Обработка ввода даты отчёта
    if user["stage"] == "custom_date_input":
        try:
            custom_date = datetime.strptime(text, "%d.%m.%Y")
            user["date"] = custom_date.strftime("%d.%m.%Y")
            user["stage"] = "confirm_report"
            bot.send_message(chat_id, f"✅ Дата изменена на: <b>{user['date']}</b>")
            preview_report(chat_id)
        except ValueError:
            bot.send_message(chat_id, "⚠️ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ:")
        return

    # Обработка цифрового ввода — суммы
    if text.isdigit():
        amount = int(text)
        if user["stage"] in ["main", "amount_input"]:
            user["transfers"].append(-amount if user["mode"] == "subtract" else amount)
            bot.send_message(chat_id, f"{'➖ Возврат' if user['mode']=='subtract' else '✅ Добавлено'}: {amount}₽")
            total = sum(user["transfers"])
            bot.send_message(chat_id, f"💰 Текущая сумма: <b>{total}₽</b>", reply_markup=get_main_menu())
            user["mode"] = "add"
            user["stage"] = "main"
            return

        elif user["stage"] == "cash_input":
            user["cash"] = amount
            user["stage"] = "terminal_input"
            bot.send_message(chat_id, "Сколько по терминалу:")
            return

        elif user["stage"] == "terminal_input":
            user["terminal"] = amount
            user["stage"] = "confirm_report"
            preview_report(chat_id)
            return

    # Если на главном экране вводим товары в заказ
    if user["stage"] == "main":
        items = sanitize_input(text)
        if items:
            user["order_items"].extend(items)
            bot.send_message(chat_id, "🛒 Добавлено в заказ:")
            for item in items:
                bot.send_message(chat_id, f"• {item}")
        return

    # Если на этапе подтверждения отчёта - просто проигнорим
    if user["stage"] == "confirm_report":
        bot.send_message(chat_id, "Используйте кнопки меню для дальнейших действий.")
        return

    # На всякий случай: любое неизвестное сообщение
    bot.send_message(chat_id, "Не понял, выберите действие из меню.", reply_markup=get_main_menu())

# === Функции отчётов и отправки ===
def round_to_50(value):
    remainder = value % 50
    return int(value - remainder) if remainder < 25 else int(value + (50 - remainder))

def preview_report(chat_id):
    data = user_data[chat_id]
    transfers = sum(data["transfers"])
    total = transfers + data["cash"] + data["terminal"]
    if data["shop"] == "Янтарь":
        each = round_to_50((total * 0.10) / 2) if total >= 40000 else 2000
        salary = each * 2
        salary_text = f"👔 ЗП: {salary}₽\n👤 По {each}₽ каждому"
    else:
        salary = max(2000, round_to_50(total * 0.10))
        salary_text = f"👔 ЗП: {salary}₽"
    report = (
        f"📦 Магазин: {data['shop']}\n"
        f"📅 Дата: {data['date']}\n"
        f"💳 Переводы: {transfers}₽\n"
        f"💵 Наличные: {data['cash']}₽\n"
        f"🏧 Терминал: {data['terminal']}₽\n"
        f"📊 Итого: {total}₽\n{salary_text}"
    )
    bot.send_message(chat_id, report, reply_markup=get_confirm_menu())

def send_report(chat_id):
    data = user_data[chat_id]
    row = [data["date"], data["shop"], sum(data["transfers"]), data["cash"], data["terminal"]]
    sheet.append_row(row)
    total = sum(data["transfers"]) + data["cash"] + data["terminal"]
    report = (
        f"📦 Магазин: {data['shop']}\n"
        f"📅 Дата: {data['date']}\n"
        f"💳 Переводы: {row[2]}₽\n"
        f"💵 Наличные: {row[3]}₽\n"
        f"🏧 Терминал: {row[4]}₽\n"
        f"📊 Итого: {total}₽"
    )
    bot.send_message(CHAT_ID_FOR_REPORT, report, message_thread_id=THREAD_ID_FOR_REPORT)
    user_data[chat_id] = {
        "shop": user["shop"],  # сохраняем магазин перевода
        "order_shop": None,
        "transfers": [],
        "mode": "add",
        "cash": 0,
        "terminal": 0,
        "stage": "main",
        "date": datetime.now().strftime("%d.%m.%Y"),
        "order_items": [],
        "order_photos": [],
        "order_date": None,
        "pending_delivery": [],
        "last_order": []
    }
    bot.send_message(chat_id, "✅ Отчёт отправлен! Выберите действие:", reply_markup=get_main_menu())

def send_order(chat_id):
    user = user_data[chat_id]
    items = user.get("order_items", [])
    photos = user.get("order_photos", [])
    shop = user.get("order_shop") or user.get("shop")
    date = user.get("order_date") or datetime.now().strftime("%d.%m.%Y")

    if not items and not photos:
        bot.send_message(chat_id, "⚠️ Нельзя отправить пустой заказ.")
        return

    message = f"🛍 Новый заказ:\n📦 Магазин: {shop}\n📅 Дата заказа: {date}\n"
    if items:
        message += "\n" + "\n".join(f"• {item}" for item in items)

    msg = bot.send_message(CHAT_ID_FOR_REPORT, message, message_thread_id=THREAD_ID_FOR_ORDER)

    for file_id in photos:
        bot.send_photo(CHAT_ID_FOR_REPORT, file_id, reply_to_message_id=msg.message_id)

    # Отложенные поставки (сохраняем товары, чтобы потом принять)
    user["pending_delivery"] = items[:]
    user["order_items"] = []
    user["order_photos"] = []
    user["order_date"] = None
    user["order_shop"] = None

# === ЗАПУСК БОТА ===
print("✅ Бот запущен...")
bot.infinity_polling()
