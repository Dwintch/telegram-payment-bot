import os
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

# Список сотрудников
EMPLOYEES_LIST = ['Данил', 'Даниз', 'Даша', 'Оксана', 'Лиза', 'Соня']

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
user_data = {}

# === GOOGLE SHEETS ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).sheet1

# === ПОГОДА ===
def get_weather():
    # Можно здесь вставить свой API ключ OpenWeatherMap или другой сервиса
    # Для примера делаем запрос в OpenWeatherMap на Геленджик
    API_KEY = os.getenv("OPENWEATHER_API_KEY")
    if not API_KEY:
        return None

    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q=Gelendzhik&units=metric&appid={API_KEY}&lang=ru"
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200:
            weather = {
                "temp": data['main']['temp'],
                "humidity": data['main']['humidity'],
                "wind_speed": data['wind']['speed'],
                "description": data['weather'][0]['description'].capitalize()
            }
            return weather
        else:
            return None
    except Exception as e:
        logging.error(f"Ошибка при получении погоды: {e}")
        return None

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

def get_employee_selection_menu(shop):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    if shop == "Янтарь":
        # Для Янтаря выбираем двух сотрудников
        for emp in EMPLOYEES_LIST:
            markup.add(emp)
        markup.add("Готово")
    else:
        # Для других — одного сотрудника
        for emp in EMPLOYEES_LIST:
            markup.add(emp)
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
        "employee_selection_done": False
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
            "accepted_delivery": [],
            "employees": [],
            "employee_selection_done": False
        })
        bot.send_message(chat_id, f"Выбран магазин: <b>{message.text}</b>", reply_markup=get_main_menu())
        return

    # Заказы — выбор магазина
    if user.get("stage") == "choose_shop_order":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if message.text in allowed_shops:
            user["order_shop"] = message.text
            user["order_items"] = []
            user["order_photos"] = []
            user["stage"] = "order_input"
            bot.send_message(chat_id, f"Выбран магазин для заказа: <b>{message.text}</b>\nВведите товары через запятую или с новой строки:", reply_markup=None)
            return

    # Приёмка — выбор магазина
    if user.get("stage") == "choose_shop_delivery":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if message.text in allowed_shops:
            user["order_shop"] = message.text
            # Собираем все last_order из других пользователей для данного магазина
            pending = []
            for u in user_data.values():
                if u.get("order_shop") == message.text and u.get("last_order"):
                    pending.extend(u["last_order"])
            pending = list(set(pending))  # Уникальные товары

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

    # === ЗАКАЗЫ ===
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

    # === ПРИЕМ ПОСТАВКИ ===
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

    # === ФИНАНСЫ ===
    if text == "❌ Отменить":
        user.update({"mode": "add", "cash": 0, "terminal": 0, "stage": "main", "employees": [], "employee_selection_done": False})
        bot.send_message(chat_id, "❌ Действие отменено. Выберите действие:", reply_markup=get_main_menu())
        return

    if text == "💰 Перевод":
        user["mode"] = "add"
        user["stage"] = "amount_input"
        user["employees"] = []
        user["employee_selection_done"] = False
        bot.send_message(chat_id, "Оп, лавешечка капнула! Сколько пришло?:")
        return

    if text == "💸 Возврат":
        user["mode"] = "subtract"
        user["stage"] = "amount_input"
        user["employees"] = []
        user["employee_selection_done"] = False
        bot.send_message(chat_id, "Смешно, возврат на сумму:")
        return

    if text == "👀 Посмотреть сумму":
        total = sum(user["transfers"])
        count = len(user["transfers"])
        bot.send_message(chat_id, f"📊 Сумма переводов: <b>{total}₽</b>\nКол-во транзакций: {count}")
        return

    if text == "📄 Составить отчёт":
        if not user["transfers"] and user["cash"] == 0 and user["terminal"] == 0:
            bot.send_message(chat_id, "⚠️ Нет данных для отчёта.")
            return

        if not user["employee_selection_done"]:
            user["stage"] = "employee_select"
            # Подсказка с выбором сотрудников по правилам
            shop = user.get("shop")
            if shop == "Янтарь":
                bot.send_message(chat_id,
                                 "Выберите двух сотрудников, которые работали сегодня (отправляйте по одному имени).\n"
                                 "Когда закончите — нажмите кнопку <b>Готово</b>.", reply_markup=get_employee_selection_menu(shop))
            else:
                bot.send_message(chat_id, "Выберите одного сотрудника, который работал сегодня:", reply_markup=get_employee_selection_menu(shop))
            return

        send_report(chat_id)
        return

    # Ввод суммы наличных или терминала
    if user["stage"] == "amount_input":
        # Ожидаем сумму наличных, затем терминала
        try:
            val = int(text.replace(" ", "").replace("₽", ""))
            if val < 0:
                bot.send_message(chat_id, "Введите положительное число.")
                return
        except Exception:
            bot.send_message(chat_id, "Введите корректное число.")
            return

        if user["cash"] == 0:
            user["cash"] = val
            bot.send_message(chat_id, "Теперь введите сумму терминала:")
            return
        elif user["terminal"] == 0:
            user["terminal"] = val
            # После ввода наличных и терминала — переход к выбору сотрудников
            user["stage"] = "employee_select"
            shop = user.get("shop")
            if shop == "Янтарь":
                bot.send_message(chat_id,
                                 "Выберите двух сотрудников, которые работали сегодня (отправляйте по одному имени).\n"
                                 "Когда закончите — нажмите кнопку <b>Готово</b>.", reply_markup=get_employee_selection_menu(shop))
            else:
                bot.send_message(chat_id, "Выберите одного сотрудника, который работал сегодня:", reply_markup=get_employee_selection_menu(shop))
            return

    # Выбор сотрудников
    if user["stage"] == "employee_select":
        if text == "Готово" and user.get("shop") == "Янтарь":
            if len(user["employees"]) != 2:
                bot.send_message(chat_id, "Выберите ровно двух сотрудников для Янтаря или продолжайте выбор.")
                return
            user["employee_selection_done"] = True
            send_report(chat_id)
            return

        if text in EMPLOYEES_LIST:
            if user.get("shop") == "Янтарь":
                if text in user["employees"]:
                    bot.send_message(chat_id, f"Сотрудник {text} уже выбран.")
                    return
                if len(user["employees"]) < 2:
                    user["employees"].append(text)
                    bot.send_message(chat_id, f"Сотрудник {text} выбран. Выберите второго или нажмите 'Готово'.")
                else:
                    bot.send_message(chat_id, "Вы уже выбрали 2 сотрудников. Нажмите 'Готово'.")
            else:
                user["employees"] = [text]
                user["employee_selection_done"] = True
                send_report(chat_id)
            return

        bot.send_message(chat_id, "Пожалуйста, выберите сотрудника из списка.")

# === ФУНКЦИИ ОТПРАВКИ ОТЧЁТОВ И ЗАКАЗОВ ===

def send_report(chat_id):
    user = user_data.get(chat_id)
    if not user:
        return

    shop = user.get("shop")
    transfers = user.get("transfers", [])
    mode = user.get("mode")
    cash = user.get("cash")
    terminal = user.get("terminal")
    employees = user.get("employees")
    date = user.get("date")

    total_transfers = sum(transfers)
    if mode == "subtract":
        total_transfers = -total_transfers

    weather = get_weather()
    weather_text = ""
    if weather:
        weather_text = (f"\n🌡️ Погода: {weather['description']}, {weather['temp']}°C, "
                        f"Влажность: {weather['humidity']}%, Ветер: {weather['wind_speed']} м/с")

    # Округляем наличные и терминал до ближайших 50 (по твоему правилу)
    cash_rounded = round_to_50(cash)
    terminal_rounded = round_to_50(terminal)

    # Формируем текст отчёта
    report_text = f"""
<b>📅 Отчёт за {date}</b>
<b>Магазин:</b> {shop}
<b>Сотрудники:</b> {', '.join(employees)}
<b>Переводы:</b> {total_transfers}₽
<b>Наличные:</b> {cash_rounded}₽
<b>Терминал:</b> {terminal_rounded}₽
{weather_text}
"""

    # Логика зарплаты
    if shop == "Янтарь":
        report_text += f"\n💰 Зарплата рассчитана на 2 сотрудников: {', '.join(employees)}"
    else:
        report_text += f"\n💰 Зарплата рассчитана на сотрудника: {employees[0] if employees else 'не указан'}"

    # Отправляем в Google Sheets
    try:
        sheet.append_row([
            date, shop, ', '.join(employees), total_transfers, cash_rounded, terminal_rounded,
            weather_text.replace("\n", " ")
        ])
    except Exception as e:
        logging.error(f"Ошибка записи в Google Sheets: {e}")

    # Отправляем в телеграм
    bot.send_message(chat_id, report_text, reply_markup=get_main_menu())
    # Отправляем в чат с топиком
    try:
        bot.send_message(CHAT_ID_FOR_REPORT, report_text, message_thread_id=THREAD_ID_FOR_REPORT)
    except Exception as e:
        logging.error(f"Ошибка отправки отчёта в чат: {e}")

    # Сброс данных
    user.update({
        "transfers": [],
        "mode": "add",
        "cash": 0,
        "terminal": 0,
        "stage": "main",
        "employees": [],
        "employee_selection_done": False,
        "date": datetime.now().strftime("%d.%m.%Y")
    })

def send_order(chat_id):
    user = user_data.get(chat_id)
    if not user or not user.get("order_items"):
        bot.send_message(chat_id, "⚠️ Нет заказа для отправки.")
        return

    shop = user.get("order_shop")
    items = user.get("order_items")
    photos = user.get("order_photos", [])

    order_text = f"<b>Заказ магазина {shop}:</b>\n"
    for i, item in enumerate(items, 1):
        order_text += f"{i}. {item}\n"

    try:
        bot.send_message(CHAT_ID_FOR_REPORT, order_text, message_thread_id=THREAD_ID_FOR_ORDER)
        # Отправляем фото, если есть
        for p in photos:
            bot.send_photo(CHAT_ID_FOR_REPORT, p["file_id"], caption=p.get("caption", ""), message_thread_id=THREAD_ID_FOR_ORDER)
    except Exception as e:
        logging.error(f"Ошибка отправки заказа: {e}")

    # Сохраняем последний заказ
    user["last_order"] = items.copy()
    user["order_items"] = []
    user["order_photos"] = []
    user["order_shop"] = None

# === РАБОТА С ПЕРЕВОДАМИ ===
@bot.message_handler(func=lambda m: m.text and m.text.replace(' ', '').isdigit())
def handle_number(message):
    chat_id = message.chat.id
    user = user_data.get(chat_id)
    if not user:
        start(message)
        return

    if user["stage"] != "amount_input":
        return

    try:
        val = int(message.text.replace(" ", ""))
    except:
        bot.send_message(chat_id, "Введите число.")
        return

    if val < 0:
        bot.send_message(chat_id, "Введите положительное число.")
        return

    if user["cash"] == 0:
        user["cash"] = val
        bot.send_message(chat_id, "Теперь введите сумму терминала:")
        return
    elif user["terminal"] == 0:
        user["terminal"] = val
        # После ввода наличных и терминала — переход к выбору сотрудников
        user["stage"] = "employee_select"
        shop = user.get("shop")
        if shop == "Янтарь":
            bot.send_message(chat_id,
                             "Выберите двух сотрудников, которые работали сегодня (отправляйте по одному имени).\n"
                             "Когда закончите — нажмите кнопку <b>Готово</b>.", reply_markup=get_employee_selection_menu(shop))
        else:
            bot.send_message(chat_id, "Выберите одного сотрудника, который работал сегодня:", reply_markup=get_employee_selection_menu(shop))
        return

# Запускаем бота
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    bot.infinity_polling()
