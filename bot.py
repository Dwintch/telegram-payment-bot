import os
import json
import logging
from datetime import datetime

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

EMPLOYEES = ['Данил', 'Даниз', 'Даша', 'Оксана', 'Лиза', 'Соня']

def get_employee_selection_menu(selected=None):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    selected = selected or []

    for emp in EMPLOYEES:
        # Если сотрудник уже выбран, показываем с галочкой
        label = f"{emp} ✅" if emp in selected else emp
        markup.add(label)
    markup.add("Готово", "❌ Отмена")
    return markup

def ask_for_employees(chat_id):
    user = user_data[chat_id]
    user["selected_employees"] = []  # Обнуляем выбор сотрудников перед новым выбором
    bot.send_message(chat_id, "Выберите сотрудника(ов):", reply_markup=get_employee_selection_menu())

@bot.message_handler(func=lambda m: user_data.get(m.chat.id, {}).get("stage") == "choose_employee")
def handle_employee_selection(message):
    chat_id = message.chat.id
    user = user_data[chat_id]
    text = message.text

    if text == "Готово":
        # Проверяем, сколько сотрудников выбрано для магазина
        shop = user["shop"]
        selected = user.get("selected_employees", [])

        # Правила выбора сотрудников по магазину
        if shop == "Янтарь" and len(selected) != 2:
            bot.send_message(chat_id, "Для магазина Янтарь нужно выбрать ровно двух сотрудников. Выберите ещё.")
            bot.send_message(chat_id, "Выберите сотрудника(ов):", reply_markup=get_employee_selection_menu(selected))
            return
        elif shop in ["Хайп", "Полка"] and len(selected) != 1:
            bot.send_message(chat_id, "Для магазина Хайп и Полка нужно выбрать ровно одного сотрудника. Выберите ещё.")
            bot.send_message(chat_id, "Выберите сотрудника(ов):", reply_markup=get_employee_selection_menu(selected))
            return

        # Сохраняем выбор
        user["employees"] = selected
        user["stage"] = "confirm_report"

        # Далее показываем отчет для подтверждения
        preview_report(chat_id)
        return

    elif text == "❌ Отмена":
        user["stage"] = "main"
        bot.send_message(chat_id, "Отмена выбора сотрудников.", reply_markup=get_main_menu())
        return

    # Если нажали имя сотрудника - добавляем/удаляем из выбранных
    if text in EMPLOYEES:
        selected = user.get("selected_employees", [])
        if text in selected:
            selected.remove(text)
        else:
            selected.append(text)
        user["selected_employees"] = selected

        # Обновляем клавиатуру с выбранными
        bot.send_message(chat_id, "Выберите сотрудника(ов):", reply_markup=get_employee_selection_menu(selected))
        return

    # Если пришло что-то другое
    bot.send_message(chat_id, "Пожалуйста, выберите сотрудника из списка или нажмите 'Готово'.")


# === КНОПКИ ПЕРСОНАЛА ===

def get_employee_selection_menu(shop, selected=None):
    """
    shop: строка — название магазина
    selected: список выбранных сотрудников (имена)
    """
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    selected = selected or []

    # Варианты кнопок: имя сотрудника + отметка, если выбран
    for emp in EMPLOYEES:
        label = f"{emp} ✅" if emp in selected else emp
        markup.add(label)

    markup.add("Готово", "❌ Отмена")
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

# === ОКРУГЛЕНИЕ ДО 50 ===
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

    # === ОБРАБОТКА ВЫБОРА МАГАЗИНА ДЛЯ ЗАКАЗОВ ===
    if user.get("stage") == "choose_shop_order":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if message.text in allowed_shops:
            user["order_shop"] = message.text
            user["order_items"] = []
            user["order_photos"] = []
            user["stage"] = "order_input"
            bot.send_message(chat_id, f"Выбран магазин для заказа: <b>{message.text}</b>\nВведите товары через запятую или с новой строки:", reply_markup=None)
            return

    # === ОБРАБОТКА ВЫБОРА МАГАЗИНА ДЛЯ ПРИЁМКИ ===
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

    # === ЧИСЛОВОЙ ВВОД ===
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
    user["stage"] = "choose_employee"  # Меняем стадию на выбор сотрудника
    ask_for_employees(chat_id)
    return

    

    # === ОБРАБОТКА ПОДТВЕРЖДЕНИЯ ОТЧЕТА ===
    if user.get("stage") == "confirm_report":
        if text == "✅ Отправить":
            send_report(chat_id)
            user["transfers"] = []
            user["cash"] = 0
            user["terminal"] = 0
            user["stage"] = "main"
            bot.send_message(chat_id, "✅ Отчёт отправлен! Выберите магазин для переводов:", reply_markup=get_shop_menu())
            return
        elif text == "✏️ Изменить данные":
            user["stage"] = "cash_input"
            bot.send_message(chat_id, "Введите сумму наличных:")
            return
        elif text == "🗓 Изменить дату":
            user["stage"] = "custom_date_input"
            bot.send_message(chat_id, "Введите дату отчёта в формате ДД.ММ.ГГГГ:")
            return
        elif text == "❌ Отмена":
            user["stage"] = "main"
            bot.send_message(chat_id, "Отмена подтверждения отчёта.", reply_markup=get_main_menu())
            return

    # === ВВОД КАСТОМНОЙ ДАТЫ ===
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

    # Если ничего из выше не сработало
    bot.send_message(chat_id, "Выберите действие:", reply_markup=get_main_menu())

# === ПРЕДПРОСМОТР ОТЧЕТА ===
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
            each = 2000
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

# === ОТПРАВКА ОТЧЁТА В ТАБЛИЦУ И В ТГ ===
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

# === ОТПРАВКА ЗАКАЗА В ТЕЛЕГРАМ ===
def send_order(chat_id):
    user = user_data[chat_id]
    shop = user.get("order_shop", "Не указан")
    items = user.get("order_items", [])
    photos = user.get("order_photos", [])

    if not items:
        bot.send_message(chat_id, "⚠️ Заказ пуст, нечего отправлять.")
        return

    order_text = f"🛒 Заказ для магазина: <b>{shop}</b>\n\n" + "\n".join(f"• {item}" for item in items)
    bot.send_message(CHAT_ID_FOR_REPORT, order_text, message_thread_id=THREAD_ID_FOR_ORDER)

    # Отправляем фото с подписями, если есть
    for photo in photos:
        try:
            bot.send_photo(CHAT_ID_FOR_REPORT, photo["file_id"], caption=photo.get("caption", ""), message_thread_id=THREAD_ID_FOR_ORDER)
        except Exception as e:
            print(f"Ошибка отправки фото: {e}")

    # Сохраняем последний отправленный заказ у пользователя
    user["last_order"] = items.copy()

# === ЗАПУСК ===
print("✅ Бот запущен...")
bot.infinity_polling()
