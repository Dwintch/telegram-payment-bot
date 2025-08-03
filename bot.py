import os
import json
import logging
from datetime import datetime

import requests
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
THREAD_ID_FOR_ORDER = 64
GOOGLE_SHEET_NAME = 'Отчёты'
CREDENTIALS_FILE = 'credentials.json'

# Ключ API погоды OpenWeatherMap
WEATHER_API_KEY = "0657e04209d46b14a466de79282d9ca7"
CITY = "Gelendzhik"

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

# === ПОЛУЧЕНИЕ ПОГОДЫ ===
def get_weather():
    try:
        url = (f"http://api.openweathermap.org/data/2.5/weather?"
               f"q={CITY}&appid={WEATHER_API_KEY}&units=metric&lang=ru")
        response = requests.get(url)
        data = response.json()
        if data.get("cod") != 200:
            return None
        weather_info = {
            "temp": data["main"]["temp"],
            "humidity": data["main"]["humidity"],
            "description": data["weather"][0]["description"],
            "wind_speed": data["wind"]["speed"]
        }
        return weather_info
    except Exception as e:
        logging.error(f"Ошибка при получении погоды: {e}")
        return None

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
        bot.send_message(chat_id, f"🧾 Переводов за смену: <b>{total}₽</b>\n"
                                  f"Введите сумму наличных:")
        return

    if user["stage"] == "amount_input":
        try:
            amount = int(text.replace(' ', ''))
        except:
            bot.send_message(chat_id, "⚠️ Пожалуйста, введите корректное число.")
            return

        if user["mode"] == "add":
            user["transfers"].append(amount)
            bot.send_message(chat_id, f"Добавлено: {amount}₽")
        elif user["mode"] == "subtract":
            user["transfers"].append(-amount)
            bot.send_message(chat_id, f"Возврат на сумму: {amount}₽")

        user["stage"] = "main"
        bot.send_message(chat_id, "Выберите действие:", reply_markup=get_main_menu())
        return

    if user["stage"] == "cash_input":
        try:
            cash = int(text.replace(' ', ''))
            user["cash"] = cash
        except:
            bot.send_message(chat_id, "⚠️ Введите корректное число наличных.")
            return
        user["stage"] = "terminal_input"
        bot.send_message(chat_id, "Введите сумму с терминала:")
        return

    if user["stage"] == "terminal_input":
        try:
            terminal = int(text.replace(' ', ''))
            user["terminal"] = terminal
        except:
            bot.send_message(chat_id, "⚠️ Введите корректное число терминала.")
            return

        # Дальше выбираем сотрудников
        user["stage"] = "choose_employee"
        user["selected_employees"] = []
        bot.send_message(chat_id, "Выберите сотрудника(ов):", reply_markup=get_employee_selection_menu())
        return

    if user["stage"] == "choose_employee":
        if text == "Готово":
            if not user.get("selected_employees"):
                bot.send_message(chat_id, "⚠️ Выберите хотя бы одного сотрудника.")
                return
            user["stage"] = "confirm_report"
            # Показываем отчет
            total_transfers = sum(user["transfers"])
            cash = user["cash"]
            terminal = user["terminal"]
            shop = user["shop"]
            employees_str = ", ".join(user["selected_employees"])
            date = user["date"]

            weather = get_weather()
            weather_str = "Погода не получена"
            if weather:
                weather_str = (f"{weather['description'].capitalize()}, "
                               f"{weather['temp']}°C, влажность {weather['humidity']}%, "
                               f"ветер {weather['wind_speed']} м/с")

            report_text = (
                f"🧾 Отчёт по смене\n"
                f"Магазин: <b>{shop}</b>\n"
                f"Дата: <b>{date}</b>\n"
                f"Переводы: <b>{total_transfers}₽</b>\n"
                f"Наличные: <b>{cash}₽</b>\n"
                f"Терминал: <b>{terminal}₽</b>\n"
                f"Сотрудники: <b>{employees_str}</b>\n"
                f"Погода: <i>{weather_str}</i>\n\n"
                f"Подтвердите отправку отчёта."
            )

            user["report_text"] = report_text
            user["weather_data"] = weather
            bot.send_message(chat_id, report_text, reply_markup=get_confirm_menu())
            return

        if text == "❌ Отмена":
            user["stage"] = "main"
            bot.send_message(chat_id, "❌ Отмена выбора сотрудников.", reply_markup=get_main_menu())
            return

        if text in EMPLOYEES:
            selected = user.get("selected_employees", [])
            if text in selected:
                selected.remove(text)
            else:
                # Проверка на количество выбранных сотрудников в зависимости от магазина
                if user["shop"] == "Янтарь" and len(selected) >= 2:
                    bot.send_message(chat_id, "⚠️ Для Янтаря можно выбрать максимум 2 сотрудников.")
                    return
                elif user["shop"] in ["Хайп", "Полка"] and len(selected) >= 1:
                    bot.send_message(chat_id, "⚠️ Для Хайпа и Полки можно выбрать только 1 сотрудника.")
                    return
                selected.append(text)
            user["selected_employees"] = selected
            bot.send_message(chat_id, "Выберите сотрудников:", reply_markup=get_employee_selection_menu(selected))
            return

        bot.send_message(chat_id, "⚠️ Пожалуйста, выбирайте сотрудников из списка.", reply_markup=get_employee_selection_menu(user.get("selected_employees", [])))
        return

    if user["stage"] == "confirm_report":
        if text == "✅ Отправить":
            # Запись в Google Sheets
            try:
                total_transfers = sum(user["transfers"])
                cash = user["cash"]
                terminal = user["terminal"]
                shop = user["shop"]
                employees = ", ".join(user["selected_employees"])
                date = user["date"]
                weather = user.get("weather_data", {})

                sheet.append_row([
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    date,
                    shop,
                    total_transfers,
                    cash,
                    terminal,
                    employees,
                    weather.get("temp", ""),
                    weather.get("humidity", ""),
                    weather.get("description", ""),
                    weather.get("wind_speed", "")
                ])

                # Отправка отчёта в Telegram топик
                bot.send_message(
                    CHAT_ID_FOR_REPORT,
                    user["report_text"],
                    disable_web_page_preview=True
                )

                # Сброс данных
                user.update({
                    "transfers": [],
                    "cash": 0,
                    "terminal": 0,
                    "selected_employees": [],
                    "stage": "main",
                })
            except Exception as e:
                logging.error(f"Ошибка при записи отчёта: {e}")
                bot.send_message(chat_id, "⚠️ Ошибка при записи отчёта. Попробуйте позже.")
                return
            bot.send_message(chat_id, "✅ Отчёт отправлен!", reply_markup=get_main_menu())
            return

        if text == "✏️ Изменить данные":
            user["stage"] = "cash_input"
            bot.send_message(chat_id, "Введите сумму наличных:")
            return

        if text == "🗓 Изменить дату":
            bot.send_message(chat_id, "Введите дату в формате ДД.ММ.ГГГГ (например, 31.07.2025):")
            user["stage"] = "date_input"
            return

        if text == "❌ Отмена":
            user["stage"] = "main"
            bot.send_message(chat_id, "❌ Отмена отправки отчёта.", reply_markup=get_main_menu())
            return

    if user["stage"] == "date_input":
        try:
            dt = datetime.strptime(text, "%d.%m.%Y")
            user["date"] = dt.strftime("%d.%m.%Y")
            bot.send_message(chat_id, f"Дата изменена на {user['date']}")
            user["stage"] = "confirm_report"
            bot.send_message(chat_id, user.get("report_text", "Перейдите к подтверждению отчёта."), reply_markup=get_confirm_menu())
        except:
            bot.send_message(chat_id, "⚠️ Неверный формат даты. Попробуйте ещё раз (ДД.ММ.ГГГГ).")
        return

    # Если ни одно условие не сработало
    bot.send_message(chat_id, "⚠️ Неизвестная команда или состояние. Попробуйте /start.")

# === ОТПРАВКА ЗАКАЗА В ТОПИК ===
def send_order(chat_id):
    user = user_data.get(chat_id)
    if not user or not user.get("order_items"):
        bot.send_message(chat_id, "⚠️ Нет товаров для заказа.")
        return

    order_shop = user.get("order_shop")
    order_text = format_order_list(user["order_items"])

    # Отправляем заказ в топик с ID THREAD_ID_FOR_ORDER
    try:
        bot.send_message(
            CHAT_ID_FOR_REPORT,
            f"🛍 Новый заказ в магазине <b>{order_shop}</b>:\n\n{order_text}",
            reply_markup=None
        )
    except Exception as e:
        logging.error(f"Ошибка при отправке заказа: {e}")
        bot.send_message(chat_id, "⚠️ Ошибка при отправке заказа.")

# === ЛОГИ ===
logging.basicConfig(level=logging.INFO)

if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()
