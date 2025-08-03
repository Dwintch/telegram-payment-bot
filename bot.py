import os
import json
import logging
from datetime import datetime

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
CHAT_ID_FOR_REPORT = -1002826712980
THREAD_ID_FOR_REPORT = 3
THREAD_ID_FOR_ORDER = 64
GOOGLE_SHEET_NAME = 'Отчёты'
CREDENTIALS_FILE = 'credentials.json'
WEATHER_API_KEY = "0657e04209d46b14a466de79282d9ca7"
WEATHER_CITY = "Gelendzhik"  # Можно поменять на нужный город

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
user_data = {}

# === СПИСОК СОТРУДНИКОВ ===
EMPLOYEES = ['Данил', 'Даниз', 'Даша', 'Оксана', 'Лиза', 'Соня']

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

def get_order_action_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ Отправить заказ", "✏️ Изменить заказ")
    markup.add("💾 Сохранить заказ (не отправлять)", "❌ Отмена")
    return markup

# === МЕНЮ ВЫБОРА ПЕРСОНАЛА ===
def get_employee_selection_menu(selected=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    selected = selected or []
    for emp in EMPLOYEES:
        label = f"{emp} ✅" if emp in selected else emp
        markup.add(label)
    markup.add("Готово", "❌ Отмена")
    return markup

def ask_for_employees(chat_id):
    user = user_data[chat_id]
    user["selected_employees"] = []
    user["stage"] = "choose_employee"
    bot.send_message(chat_id, "Выберите сотрудника(ов):", reply_markup=get_employee_selection_menu())

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get("stage") == "choose_employee")
def handle_employee_selection(message):
    chat_id = message.chat.id
    user = user_data[chat_id]
    text = message.text

    if text == "Готово":
        shop = user["shop"]
        selected = user.get("selected_employees", [])

        if shop == "Янтарь" and len(selected) != 2:
            bot.send_message(chat_id, "Для магазина Янтарь нужно выбрать ровно двух сотрудников. Выберите ещё.")
            bot.send_message(chat_id, "Выберите сотрудника(ов):", reply_markup=get_employee_selection_menu(selected))
            return
        elif shop in ["Хайп", "Полка"] and len(selected) != 1:
            bot.send_message(chat_id, "Для магазина Хайп и Полка нужно выбрать ровно одного сотрудника. Выберите ещё.")
            bot.send_message(chat_id, "Выберите сотрудника(ов):", reply_markup=get_employee_selection_menu(selected))
            return

        user["employees"] = selected
        user["stage"] = "confirm_report"
        preview_report(chat_id)
        return

    elif text == "❌ Отмена":
        user["stage"] = "main"
        bot.send_message(chat_id, "Отмена выбора сотрудников.", reply_markup=get_main_menu())
        return

    if text in EMPLOYEES:
        selected = user.get("selected_employees", [])
        if text in selected:
            selected.remove(text)
        else:
            selected.append(text)
        user["selected_employees"] = selected
        bot.send_message(chat_id, "Выберите сотрудника(ов):", reply_markup=get_employee_selection_menu(selected))
        return

    bot.send_message(chat_id, "Пожалуйста, выберите сотрудника из списка или нажмите 'Готово'.")

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

# === ФУНКЦИЯ ПОЛУЧЕНИЯ ПОГОДЫ ===
def get_weather():
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={WEATHER_CITY}&appid={WEATHER_API_KEY}&units=metric&lang=ru"
        response = requests.get(url, timeout=10)
        data = response.json()
        if data.get("cod") != 200:
            return None
        weather = {
            "temp": data["main"]["temp"],
            "humidity": data["main"]["humidity"],
            "wind_speed": data["wind"]["speed"],
            "description": data["weather"][0]["description"].capitalize()
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
        "saved_order": []
    }
    bot.send_message(chat_id, "Привет! Выберите магазин для переводов:", reply_markup=get_shop_menu())

# === ВЫБОР МАГАЗИНА ===
@bot.message_handler(func=lambda m: m.text in ["Янтарь", "Хайп", "Полка"])
def choose_shop(message):
    chat_id = message.chat.id
    user = user_data.get(chat_id)
    if not user or user.get("stage") == "choose_shop":
        user_data[chat_id] = user or {}
        user_data[chat_id].update({
            "shop": message.text,
            "transfers": [],
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "stage": "main",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "order_shop": None,
            "order_items": [],
            "order_photos": [],
            "order_date": None,
            "pending_delivery": [],
            "accepted_delivery": []
        })
        bot.send_message(chat_id, f"Выбран магазин: <b>{message.text}</b>", reply_markup=get_main_menu())
        return

    if user.get("stage") == "choose_shop_order":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if message.text in allowed_shops:
            user["order_shop"] = message.text
            user["order_items"] = []
            user["order_photos"] = []
            user["stage"] = "order_input"
            bot.send_message(chat_id, f"Выбран магазин для заказа: <b>{message.text}</b>\nВведите товары через запятую или с новой строки:", reply_markup=None)
            return

    if user.get("stage") == "choose_shop_delivery":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if message.text in allowed_shops:
            user["order_shop"] = message.text
            pending = []
            for u in user_data.values():
                if u.get("order_shop") == message.text and u.get("last_order"):
                    pending.extend(u["last_order"])
            pending = list(set(pending))

            if "accepted_delivery" not in user:
                user["accepted_delivery"] = []
            user["pending_delivery"] = [item for item in pending if item not in user["accepted_delivery"]]

            if user["pending_delivery"]:
                items_list = "\n".join(f"• {item}" for item in user["pending_delivery"])
                bot.send_message(chat_id, f"Выберите что приехало (через запятую или с новой строки):\n{items_list}")
                user["stage"] = "delivery_confirm"
            else:
                bot.send_message(chat_id, "Нет отложенных товаров на поставку для этого магазина.")
                user["stage"] = "main"
            return

    bot.send_message(chat_id, "Пожалуйста, выберите магазин из меню.", reply_markup=get_shop_menu())

# === ОБРАБОТКА ТЕКСТА ===
@bot.message_handler(func=lambda m: True)
def handle_any_message(message):
    chat_id = message.chat.id
    text = message.text.strip()
    user = user_data.get(chat_id)

    if not user:
        start(message)
        return

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
        bot.send_message(chat_id, "Сколько денег ушло?:")
        return

    if user["stage"] == "amount_input":
        try:
            amount = int(text)
            if amount < 0:
                bot.send_message(chat_id, "⚠️ Введите положительное число.")
                return
        except ValueError:
            bot.send_message(chat_id, "⚠️ Введите корректное число.")
            return

        shop = user["shop"]
        mode = user["mode"]
        if mode == "add":
            user["transfers"].append(amount)
        else:
            user["transfers"].append(-amount)
        user["stage"] = "cash_input"
        bot.send_message(chat_id, "А сколько налички в кассе сейчас?:")
        return

    if user["stage"] == "cash_input":
        try:
            cash = int(text)
            if cash < 0:
                bot.send_message(chat_id, "⚠️ Введите положительное число.")
                return
            user["cash"] = cash
            user["stage"] = "terminal_input"
            bot.send_message(chat_id, "А сколько по терминалу?:")
            return
        except ValueError:
            bot.send_message(chat_id, "⚠️ Введите корректное число.")
            return

    if user["stage"] == "terminal_input":
        try:
            terminal = int(text)
            if terminal < 0:
                bot.send_message(chat_id, "⚠️ Введите положительное число.")
                return
            user["terminal"] = terminal
            user["stage"] = "choose_employee"
            ask_for_employees(chat_id)
            return
        except ValueError:
            bot.send_message(chat_id, "⚠️ Введите корректное число.")
            return

    if user["stage"] == "confirm_report":
        if text == "✅ Отправить":
            send_report(chat_id)
            user["stage"] = "main"
            user["transfers"] = []
            user["cash"] = 0
            user["terminal"] = 0
            user["employees"] = []
            bot.send_message(chat_id, "✅ Отчёт отправлен!", reply_markup=get_main_menu())
            return
        elif text == "✏️ Изменить данные":
            user["stage"] = "amount_input"
            bot.send_message(chat_id, "Введите сумму перевода:", reply_markup=None)
            return
        elif text == "🗓 Изменить дату":
            user["stage"] = "date_input"
            bot.send_message(chat_id, "Введите дату в формате ДД.ММ.ГГГГ:", reply_markup=None)
            return
        elif text == "❌ Отмена":
            user["stage"] = "main"
            bot.send_message(chat_id, "Отмена.", reply_markup=get_main_menu())
            return
        else:
            bot.send_message(chat_id, "Пожалуйста, выберите действие из меню.", reply_markup=get_confirm_menu())
            return

    if user["stage"] == "date_input":
        try:
            datetime.strptime(text, "%d.%m.%Y")
            user["date"] = text
            user["stage"] = "confirm_report"
            preview_report(chat_id)
        except ValueError:
            bot.send_message(chat_id, "⚠️ Неверный формат даты. Введите в формате ДД.ММ.ГГГГ.")
        return

    if text == "📄 Составить отчёт":
        if not user["transfers"] and user["cash"] == 0 and user["terminal"] == 0:
            bot.send_message(chat_id, "Нет данных для отчёта. Введите переводы и суммы.")
            return
        user["stage"] = "confirm_report"
        preview_report(chat_id)
        return

    if text == "👀 Посмотреть сумму":
        total = sum(user["transfers"])
        bot.send_message(chat_id, f"Текущая сумма переводов: <b>{total}</b> руб.")
        return

    bot.send_message(chat_id, "Я не понял команду. Пожалуйста, выберите действие из меню.", reply_markup=get_main_menu())

def preview_report(chat_id):
    user = user_data[chat_id]
    total = sum(user.get("transfers", []))
    cash = user.get("cash", 0)
    terminal = user.get("terminal", 0)
    date = user.get("date", datetime.now().strftime("%d.%m.%Y"))
    employees = user.get("employees", [])

    weather = get_weather()
    if weather:
        weather_text = (f"Погода: {weather['description']}, {weather['temp']}°C, "
                        f"Влажность {weather['humidity']}%, Ветер {weather['wind_speed']} м/с")
    else:
        weather_text = "Погода: данные недоступны"

    report_text = (
        f"Отчёт за {date}\n"
        f"Магазин: {user.get('shop')}\n"
        f"Переводы: {total} руб.\n"
        f"Наличные: {cash} руб.\n"
        f"Терминал: {terminal} руб.\n"
        f"Сотрудники: {', '.join(employees)}\n"
        f"{weather_text}\n"
        f"\nВыберите действие:"
    )
    bot.send_message(chat_id, report_text, reply_markup=get_confirm_menu())

def send_report(chat_id):
    user = user_data[chat_id]
    total = sum(user.get("transfers", []))
    cash = user.get("cash", 0)
    terminal = user.get("terminal", 0)
    date = user.get("date", datetime.now().strftime("%d.%m.%Y"))
    employees = user.get("employees", [])

    weather = get_weather()
    if weather:
        weather_text = (f"Погода: {weather['description']}, {weather['temp']}°C, "
                        f"Влажность {weather['humidity']}%, Ветер {weather['wind_speed']} м/с")
    else:
        weather_text = "Погода: данные недоступны"

    report_text = (
        f"Отчёт за {date}\n"
        f"Магазин: {user.get('shop')}\n"
        f"Переводы: {total} руб.\n"
        f"Наличные: {cash} руб.\n"
        f"Терминал: {terminal} руб.\n"
        f"Сотрудники: {', '.join(employees)}\n"
        f"{weather_text}"
    )
    # Отправляем в топик
    bot.send_message(CHAT_ID_FOR_REPORT, report_text, message_thread_id=THREAD_ID_FOR_REPORT)

    # Записываем в Google Sheets
    try:
        row = [
            date,
            user.get('shop'),
            total,
            cash,
            terminal,
            ", ".join(employees),
            weather['temp'] if weather else '',
            weather['humidity'] if weather else '',
            weather['wind_speed'] if weather else '',
            weather['description'] if weather else ''
        ]
        sheet.append_row(row)
    except Exception as e:
        logging.error(f"Ошибка записи в Google Sheets: {e}")

def send_order(chat_id):
    user = user_data[chat_id]
    shop = user.get("order_shop")
    order_items = user.get("order_items", [])
    order_photos = user.get("order_photos", [])

    if not shop or not order_items:
        bot.send_message(chat_id, "⚠️ Нет данных для отправки заказа.")
        return

    order_text = f"🛍 Заказ для {shop}:\n" + "\n".join(f"• {item}" for item in order_items)
    bot.send_message(CHAT_ID_FOR_REPORT, order_text, message_thread_id=THREAD_ID_FOR_ORDER)

    # Отправляем фото если есть
    for photo in order_photos:
        file_id = photo.get("file_id")
        caption = photo.get("caption", "")
        bot.send_photo(CHAT_ID_FOR_REPORT, file_id, caption=caption, message_thread_id=THREAD_ID_FOR_ORDER)

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    bot.infinity_polling()
