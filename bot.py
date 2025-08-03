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
import requests

# === ЗАГРУЗКА .ENV ===
load_dotenv()

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID_FOR_REPORT = -1002826712980  # ID чата для отчётов
THREAD_ID_FOR_REPORT = 3  # ID топика для отчётов
THREAD_ID_FOR_ORDER = 64  # ID топика для заказов
GOOGLE_SHEET_NAME = 'Отчёты'
CREDENTIALS_FILE = 'credentials.json'

# API ключ для погоды (OpenWeatherMap)
WEATHER_API_KEY = os.getenv("0657e04209d46b14a466de79282d9ca7")
WEATHER_CITY = "Gelendzhik"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
user_data = {}

# === GOOGLE SHEETS ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).sheet1

# === СПИСОК СОТРУДНИКОВ ===
EMPLOYEES = ['Данил', 'Даниз', 'Даша', 'Оксана', 'Лиза', 'Соня']

# === КНОПКИ ===
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💰 Перевод", "💸 Возврат")
    markup.add("📄 Составить отчёт", "👀 Посмотреть сумму")
    markup.add("🛍 Заказ", "📦 Прием поставки")
    markup.add("❌ Отменить")
    return markup

def get_yes_no_keyboard():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("✅ Да", "❌ Нет")
    return markup

def get_shop_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Янтарь", "Хайп", "Полка")
    return markup

def get_confirm_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ Отправить", "✏️ Изменить данные", "🗓 Изменить дату", "❌ Отмена")
    return markup

def get_order_action_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ Отправить заказ", "✏️ Изменить заказ")
    markup.add("💾 Сохранить заказ (не отправлять)", "❌ Отмена")
    return markup

def get_employee_menu(max_selection=2, current_selection=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    current_selection = current_selection or []
    buttons = []
    for emp in EMPLOYEES:
        label = f"✅ {emp}" if emp in current_selection else emp
        buttons.append(types.KeyboardButton(label))
    markup.add(*buttons)
    if current_selection:
        markup.add("✅ Завершить выбор")
    else:
        markup.add("❌ Отмена")
    return markup

# === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===
def sanitize_input(text):
    items = []
    for part in text.split(','):
        items.extend([x.strip() for x in part.split('\n') if x.strip()])
    return items

def format_order_list(items):
    if not items:
        return "📋 Заказ пуст."
    return "📋 Текущий заказ:\n" + "\n".join(f"• {item}" for item in items)

def round_to_50(value):
    remainder = value % 50
    if remainder < 25:
        return int(value - remainder)
    else:
        return int(value + (50 - remainder))

# === ПОЛУЧЕНИЕ ПОГОДЫ ===
def get_weather():
    try:
        url = (f"http://api.openweathermap.org/data/2.5/weather?"
               f"q={WEATHER_CITY}&appid={WEATHER_API_KEY}&units=metric&lang=ru")
        response = requests.get(url, timeout=5)
        data = response.json()
        weather = {
            'description': data['weather'][0]['description'].capitalize(),
            'temp': round(data['main']['temp']),
            'humidity': data['main']['humidity'],
            'wind_speed': round(data['wind']['speed'], 1)
        }
        return weather
    except Exception as e:
        logging.error(f"Ошибка получения погоды: {e}")
        return None

# === ОБРАБОТКА ФОТО ===
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    user = user_data.get(chat_id)
    caption = message.caption or ""
    if not user:
        bot.send_message(chat_id, "📷 Фото получено, но вы не в сессии.")
        return

    stage = user.get("stage")
    if stage not in ["order_input", "delivery_confirm"]:
        bot.send_message(chat_id, "📷 Фото получено, но сейчас вы не оформляете заказ или приемку.")
        return

    file_id = message.photo[-1].file_id

    if stage == "order_input":
        user.setdefault("order_photos", []).append({"file_id": file_id, "caption": caption})
        if caption:
            user["order_items"].append(caption)
        bot.send_message(chat_id, "📸 Фото и текст добавлены к заказу!")
    elif stage == "delivery_confirm":
        user.setdefault("delivery_photos", []).append({"file_id": file_id, "caption": caption})
        bot.send_message(chat_id, "📸 Фото и текст приняты для приемки поставки.")

# === ОБРАБОТКА /START ===
@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_data[chat_id] = {
        "shop": None,
        "order_shop": None,
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
        "accepted_delivery": [],
        "last_order": [],
        "saved_order": [],
        "employees": [],
        "employee_selection_count": 0
    }
    bot.send_message(chat_id, "Привет! Выберите магазин для переводов:", reply_markup=get_shop_menu())
    
 if text == "📄 Составить отчёт":
        if not user["transfers"]:
            bot.send_message(chat_id, "⚠️ Нет переводов для отчёта. Пожалуйста, сначала добавьте переводы.")
            return
        if user["cash"] == 0 and user["terminal"] == 0:
            bot.send_message(chat_id, "⚠️ Наличные и терминал равны 0. Пожалуйста, введите суммы.")
            user["stage"] = "cash_input"
            return
        user["stage"] = "confirm_report"
        preview_report(chat_id)
        return
     
# === ВЫБОР МАГАЗИНА ===
@bot.message_handler(func=lambda m: m.text in ["Янтарь", "Хайп", "Полка"])
def choose_shop(message):
    chat_id = message.chat.id
    user = user_data.get(chat_id)
    if not user:
        start(message)
        return

    text = message.text

    if user.get("stage") == "choose_shop":
        user.update({
            "shop": text,
            "transfers": [],
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "stage": "main",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "order_shop": None,
            "order_items": [],
            "order_photos": [],
            "pending_delivery": [],
            "accepted_delivery": [],
            "employees": [],
            "employee_selection_count": 0
        })
        bot.send_message(chat_id, f"Выбран магазин: <b>{text}</b>", reply_markup=get_main_menu())
        return

    if user.get("stage") == "choose_shop_order":
        user["order_shop"] = text
        user["order_items"] = []
        user["order_photos"] = []
        user["stage"] = "order_input"
        bot.send_message(chat_id, f"Выбран магазин для заказа: <b>{text}</b>\nВведите товары через запятую или с новой строки:", reply_markup=None)
        return

    if user.get("stage") == "choose_shop_delivery":
        user["order_shop"] = text
        pending = []
        for u in user_data.values():
            if u.get("order_shop") == text and u.get("last_order"):
                pending.extend(u["last_order"])
        pending = list(set(pending))
        user["pending_delivery"] = [item for item in pending if item not in user.get("accepted_delivery", [])]
        if user["pending_delivery"]:
            items_list = "\n".join(f"• {item}" for item in user["pending_delivery"])
            bot.send_message(chat_id, f"Выберите что приехало (через запятую или с новой строки):\n{items_list}")
            user["stage"] = "delivery_confirm"
        else:
            bot.send_message(chat_id, "Нет отложенных товаров на поставку для этого магазина.")
            user["stage"] = "main"
        return

    bot.send_message(chat_id, "Пожалуйста, выберите магазин из меню.", reply_markup=get_shop_menu())

# === ОБРАБОТКА ЛЮБОГО ТЕКСТА ===
@bot.message_handler(func=lambda m: True)
def handle_any_message(message):
    chat_id = message.chat.id
    text = message.text.strip()
    user = user_data.get(chat_id)

    if not user:
        start(message)
        return

    # --- ЗАКАЗ ---
    if text == "🛍 Заказ":
        if user.get("saved_order"):
            user["order_items"] = user["saved_order"].copy()
            user["stage"] = "order_input"
            order_text = format_order_list(user["order_items"])
            bot.send_message(chat_id,
                             f"💾 У вас есть сохранённый заказ:\n{order_text}\nВы можете продолжить работу с ним.",
                             reply_markup=get_order_action_menu())
        else:
            user["stage"] = "choose_shop_order"
            bot.send_message(chat_id, "Выберите магазин для заказа:", reply_markup=get_shop_menu())
        return

    if user["stage"] == "order_input":
        if text in ["✅ Отправить заказ", "✏️ Изменить заказ", "💾 Сохранить заказ (не отправлять)", "❌ Отмена"]:
            if text == "✅ Отправить заказ":
                if not user["order_items"]:
                    bot.send_message(chat_id, "⚠️ Заказ пуст, нечего отправлять.")
                    return
                send_order(chat_id)
                user["saved_order"] = []
                user["order_items"] = []
                user["order_shop"] = None
                user["order_photos"] = []
                user["stage"] = "main"
                bot.send_message(chat_id, "✅ Заказ отправлен!", reply_markup=get_main_menu())
                return

            if text == "✏️ Изменить заказ":
                if not user["order_items"]:
                    bot.send_message(chat_id, "⚠️ Заказ пуст, нечего изменять.")
                    return
                bot.send_message(chat_id,
                                 "✏️ Напишите позиции, которые хотите удалить через запятую или с новой строки.\n"
                                 "Если хотите очистить весь заказ — напишите 'удалить всё', 'очистить', 'сбросить'.")
                user["stage"] = "order_edit"
                return

            if text == "💾 Сохранить заказ (не отправлять)":
                if not user["order_items"]:
                    bot.send_message(chat_id, "⚠️ Заказ пуст, нечего сохранять.")
                    return
                user["saved_order"] = user["order_items"].copy()
                user["order_items"] = []
                user["order_shop"] = None
                user["order_photos"] = []
                user["stage"] = "main"
                bot.send_message(chat_id, "💾 Заказ сохранён. Чтобы отправить — зайдите в заказ и нажмите «✅ Отправить заказ».", reply_markup=get_main_menu())
                return

            if text == "❌ Отмена":
                user["order_items"] = []
                user["order_shop"] = None
                user["order_photos"] = []
                user["stage"] = "main"
                bot.send_message(chat_id, "❌ Действие отменено.", reply_markup=get_main_menu())
                return

        else:
            items = sanitize_input(text)
            if items:
                user["order_items"].extend(items)
                order_text = format_order_list(user["order_items"])
                bot.send_message(chat_id, order_text)
                bot.send_message(chat_id, "Выберите действие:", reply_markup=get_order_action_menu())
            else:
                bot.send_message(chat_id, "⚠️ Введите товары через запятую или с новой строки.")
        return

    if user["stage"] == "order_edit":
        text_lower = text.lower()
        if any(word in text_lower for word in ["удалить всё", "удалить все", "очистить", "сбросить"]):
            user["order_items"] = []
            bot.send_message(chat_id, "🗑️ Заказ очищен.")
        else:
            to_delete = sanitize_input(text)
            initial_len = len(user["order_items"])
            remaining = []
            for order_item in user["order_items"]:
                if not any(order_item.lower() == del_item.lower() for del_item in to_delete):
                    remaining.append(order_item)
            deleted_count = initial_len - len(remaining)
            user["order_items"] = remaining
            if deleted_count:
                bot.send_message(chat_id, f"Удалено позиций: {deleted_count}")
            else:
                bot.send_message(chat_id, "⚠️ Не найдено позиций для удаления.")
        order_text = format_order_list(user["order_items"])
        bot.send_message(chat_id, order_text)
        bot.send_message(chat_id, "Выберите действие:", reply_markup=get_order_action_menu())
        user["stage"] = "order_input"
        return

    # --- ПРИЕМ ПОСТАВКИ ---
    if text == "📦 Прием поставки":
        user["stage"] = "choose_shop_delivery"
        bot.send_message(chat_id, "Выберите магазин для приемки поставки:", reply_markup=get_shop_menu())
        return

    if user["stage"] == "delivery_confirm":
        arrived = sanitize_input(text)
        invalid_items = [item for item in arrived if item not in user.get("pending_delivery", [])]
        if invalid_items:
            bot.send_message(chat_id, f"⚠️ Товар(ы) не найден(ы) в списке ожидаемых: {', '.join(invalid_items)}.\nПожалуйста, введите точно как в списке.")
            return

        not_arrived = [item for item in user.get("pending_delivery", []) if item not in arrived]

        user.setdefault("accepted_delivery", [])
        for item in arrived:
            if item not in user["accepted_delivery"]:
                user["accepted_delivery"].append(item)

        user["pending_delivery"] = not_arrived

        if arrived:
            bot.send_message(chat_id, f"Отмечено приехавшим:\n" + "\n".join(f"• {item}" for item in arrived))
        else:
            bot.send_message(chat_id, "Нет отмеченных товаров.")

        if not_arrived:
            bot.send_message(chat_id, "Оставшиеся товары перенесены в следующую заявку.")
        else:
            bot.send_message(chat_id, "Все товары приняты.")
            user["accepted_delivery"] = []

        user["stage"] = "main"
        return

    # --- ФИНАНСЫ ---
    if text == "❌ Отменить":
        user.update({"mode": "add", "cash": 0, "terminal": 0, "stage": "main", "employees": [], "employee_selection_count": 0})
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

    # --- ЧИСЛОВОЙ ВВОД ---
    if text.isdigit():
        amount = int(text)
        stage = user.get("stage", "main")

        if stage == "amount_input":
            user["transfers"].append(-amount if user["mode"] == "subtract" else amount)
            bot.send_message(chat_id, f"{'➖ Возврат' if user['mode']=='subtract' else '✅ Добавлено'}: {amount}₽")
            total = sum(user["transfers"])
            bot.send_message(chat_id, f"💰 Текущая сумма: <b>{total}₽</b>", reply_markup=get_main_menu())
            user["mode"] = "add"
            user["stage"] = "main"
            return

        elif stage == "cash_input":
            user["cash"] = amount
            user["stage"] = "terminal_input"
            bot.send_message(chat_id, "Сколько по терминалу:")
            return

        elif stage == "terminal_input":
            user["terminal"] = amount
            user["stage"] = "choose_employee"
            ask_for_employees(chat_id)
            return

    # --- ВЫБОР СОТРУДНИКОВ ---
    if user.get("stage") == "choose_employee":
        current = user.get("employees", [])
        text_clean = text.replace("✅ ", "").strip()
        if text == "❌ Отмена":
            user["employees"] = []
            user["employee_selection_count"] = 0
            user["stage"] = "main"
            bot.send_message(chat_id, "Выбор сотрудников отменён.", reply_markup=get_main_menu())
            return
        elif text == "✅ Завершить выбор":
            shop = user.get("shop")
            count = len(user.get("employees", []))
            if shop == "Янтарь" and count != 2:
                bot.send_message(chat_id, "⚠️ Для магазина Янтарь нужно выбрать ровно двух сотрудников.")
                return
            if shop in ["Хайп", "Полка"] and count != 1:
                bot.send_message(chat_id, "⚠️ Для магазина Хайп или Полка нужно выбрать ровно одного сотрудника.")
                return
            user["stage"] = "confirm_report"
            preview_report(chat_id)
            return
        elif text_clean in EMPLOYEES:
            if text_clean in current:
                current.remove(text_clean)
                user["employee_selection_count"] -= 1
                bot.send_message(chat_id, f"Удалён сотрудник: {text_clean}")
            else:
                max_select = 2 if user.get("shop") == "Янтарь" else 1
                if user.get("employee_selection_count", 0) >= max_select:
                    bot.send_message(chat_id, f"⚠️ Можно выбрать максимум {max_select} сотрудника(ов). Уберите кого-нибудь, чтобы добавить нового.")
                    return
                current.append(text_clean)
                user["employee_selection_count"] += 1
                bot.send_message(chat_id, f"Добавлен сотрудник: {text_clean}")
            user["employees"] = current
            bot.send_message(chat_id, f"Выбранные сотрудники: {', '.join(current)}",
                             reply_markup=get_employee_menu(max_selection=max_select, current_selection=current))
            return
        else:
            bot.send_message(chat_id, "Пожалуйста, выберите сотрудника с кнопок.", reply_markup=get_employee_menu(max_selection=2, current_selection=current))
            return

    # --- ПОДТВЕРЖДЕНИЕ ОТЧЁТА ---
    if user.get("stage") == "confirm_report":
        if text == "✅ Отправить":
            send_report(chat_id)
            user["transfers"] = []
            user["cash"] = 0
            user["terminal"] = 0
            user["employees"] = []
            user["employee_selection_count"] = 0
            user["stage"] = "main"
            bot.send_message(chat_id, "✅ Отчёт отправлен! Выберите магазин для переводов:", reply_markup=get_shop_menu())
            return
        elif text == "✏️ Изменить данные":
            user["stage"] = "amount_input"
            bot.send_message(chat_id, "Введите сумму перевода:", reply_markup=None)
            return
        elif text == "🗓 Изменить дату":
            user["stage"] = "custom_date_input"
            bot.send_message(chat_id, "Введите дату отчёта в формате ДД.ММ.ГГГГ:", reply_markup=None)
            return
        elif text == "❌ Отмена":
            user["stage"] = "main"
            bot.send_message(chat_id, "Отмена подтверждения отчёта.", reply_markup=get_main_menu())
            return
        else:
            bot.send_message(chat_id, "Пожалуйста, выберите действие из меню.", reply_markup=get_confirm_menu())
            return

    # --- КАСТОМНАЯ ДАТА ---
    if user.get("stage") == "custom_date_input":
        try:
            custom_date = datetime.strptime(text, "%d.%m.%Y")
            user["date"] = custom_date.strftime("%d.%m.%Y")
            user["stage"] = "confirm_report"
            bot.send_message(chat_id, f"✅ Дата изменена на: {user['date']}")
            preview_report(chat_id)
        except ValueError:
            bot.send_message(chat_id, "⚠️ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ:")
        return

    # --- ЕСЛИ НИЧЕГО НЕ ПОДОШЛО ---
    bot.send_message(chat_id, "Я не понял команду. Пожалуйста, выберите действие из меню.", reply_markup=get_main_menu())

def ask_for_employees(chat_id):
    user = user_data.get(chat_id)
    if not user:
        return
    max_select = 2 if user.get("shop") == "Янтарь" else 1
    user["employees"] = []
    user["employee_selection_count"] = 0
    bot.send_message(chat_id, f"Выберите сотрудников (максимум {max_select}):", reply_markup=get_employee_menu(max_selection=max_select))

def preview_report(chat_id):
    data = user_data[chat_id]
    shop = data["shop"]
    transfers = sum(data["transfers"]) if data.get("transfers") else 0
    cash = data.get("cash", 0)
    terminal = data.get("terminal", 0)
    total = transfers + cash + terminal
    date = data.get("date", datetime.now().strftime("%d.%m.%Y"))
    employees = data.get("employees", [])

    weather = get_weather()
    if weather:
        weather_text = (f"Погода: {weather['description']}, {weather['temp']}°C, "
                        f"Влажность {weather['humidity']}%, Ветер {weather['wind_speed']} м/с")
    else:
        weather_text = "Погода: данные недоступны"

    # Расчёт зарплаты с учётом магазина
    if shop == "Янтарь":
        if total < 40000:
            salary = 4000
            each = 2000
        else:
            each = round_to_50((total * 0.10) / 2)
            salary = each * 2
    else:
        if total < 25000:
            salary = 2500
            each = 2500
        else:
            salary = round_to_50(total * 0.10)
            each = salary

    report_text = (
        f"🧾 Отчёт за {date}\n"
        f"🏬 Магазин: <b>{shop}</b>\n"
        f"💵 Переводы: {transfers}₽\n"
        f"💰 Наличные: {cash}₽\n"
        f"💳 Терминал: {terminal}₽\n"
        f"📊 Итого: <b>{total}₽</b>\n"
        f"👥 Сотрудники: {', '.join(employees) if employees else 'не выбраны'}\n"
        f"💸 Зарплата: {salary}₽ ({each}₽ на сотрудника)\n"
        f"{weather_text}\n\n"
        f"Отправить отчёт?"
    )
    bot.send_message(chat_id, report_text, reply_markup=get_confirm_menu())

def send_report(chat_id):
    data = user_data[chat_id]
    shop = data["shop"]
    transfers = sum(data["transfers"]) if data.get("transfers") else 0
    cash = data.get("cash", 0)
    terminal = data.get("terminal", 0)
    total = transfers + cash + terminal
    date = data.get("date", datetime.now().strftime("%d.%m.%Y"))
    employees = data.get("employees", [])

    weather = get_weather()
    if weather:
        weather_text = (f"Погода: {weather['description']}, {weather['temp']}°C, "
                        f"Влажность {weather['humidity']}%, Ветер {weather['wind_speed']} м/с")
    else:
        weather_text = "Погода: данные недоступны"

    if shop == "Янтарь":
        if total < 40000:
            salary = 4000
            each = 2000
        else:
            each = round_to_50((total * 0.10) / 2)
            salary = each * 2
    else:
        if total < 25000:
            salary = 2500
            each = 2500
        else:
            salary = round_to_50(total * 0.10)
            each = salary

    report_text = (
        f"🧾 Отчёт за {date}\n"
        f"🏬 Магазин: <b>{shop}</b>\n"
        f"💵 Переводы: {transfers}₽\n"
        f"💰 Наличные: {cash}₽\n"
        f"💳 Терминал: {terminal}₽\n"
        f"📊 Итого: <b>{total}₽</b>\n"
        f"👥 Сотрудники: {', '.join(employees) if employees else 'не выбраны'}\n"
        f"💸 Зарплата: {salary}₽ ({each}₽ на сотрудника)\n"
        f"{weather_text}"
    )
    bot.send_message(CHAT_ID_FOR_REPORT, report_text, message_thread_id=THREAD_ID_FOR_REPORT)

    try:
        sheet.append_row([date, shop, transfers, cash, terminal, total, ', '.join(employees), salary])
    except Exception as e:
        logging.error(f"Ошибка записи в Google Sheets: {e}")

def send_order(chat_id):
    user = user_data[chat_id]
    shop = user.get("order_shop")
    items = user.get("order_items", [])
    photos = user.get("order_photos", [])

    if not shop or not items:
        bot.send_message(chat_id, "⚠️ Ошибка: магазин или заказ не указаны.")
        return

    text = f"🛒 Новый заказ для магазина <b>{shop}</b>:\n\n" + "\n".join(f"• {item}" for item in items)
    bot.send_message(CHAT_ID_FOR_REPORT, text, message_thread_id=THREAD_ID_FOR_ORDER)

    for photo in photos:
        try:
            bot.send_photo(CHAT_ID_FOR_REPORT, photo["file_id"], caption=photo.get("caption", ""), message_thread_id=THREAD_ID_FOR_ORDER)
        except Exception as e:
            logging.error(f"Ошибка отправки фото заказа: {e}")

    user["last_order"] = items.copy()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    print("Бот запущен.")
    bot.infinity_polling()
