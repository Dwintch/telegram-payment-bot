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
THREAD_ID_FOR_ORDER = 64
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
    markup.add("❌ Отменить")
    return markup

def get_shop_menu_for_order():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Янтарь", "Хайп", "Полка")
    markup.add("⬅️ Назад")
    return markup

def get_shop_menu_for_transfer():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    # Кнопки без "⬅️ Назад"
    markup.add("Янтарь", "Хайп", "Полка")
    return markup

def get_confirm_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ Отправить", "✏️ Изменить данные", "❌ Отмена")
    return markup

def get_order_action_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ Отправить заказ", "✏️ Изменить заказ")
    markup.add("💾 Сохранить заказ (не отправлять)", "❌ Отмена")
    return markup

# === ВСПОМОГАТЕЛЬНЫЕ ===
def sanitize_input(text):
    return [item.strip() for item in text.split(',') if item.strip()]

def format_order_list(items):
    if not items:
        return "📋 Заказ пуст."
    return "📋 Текущий заказ:\n" + "\n".join(f"• {item}" for item in items)

# === ОБРАБОТКА ФОТО ===
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    user = user_data.get(chat_id)
    if not user:
        bot.send_message(chat_id, "📷 Фото получено, но вы сейчас не оформляете заказ или приёмку.")
        return

    file_id = message.photo[-1].file_id
    caption = message.caption

    # Если пользователь в режиме заказа
    if user.get("stage") == "order_input":
        user.setdefault("order_photos", []).append(file_id)
        if caption:
            user.setdefault("order_items", []).append(caption)
        shop = user.get("order_shop", "не выбран")
        bot.send_message(chat_id, f"📸 Фото добавлено к заказу для магазина <b>{shop}</b>!")
        if caption:
            bot.send_message(chat_id, f"📝 Текст из подписи добавлен в заказ:\n{caption}")
        return

    # Если пользователь в режиме приёма поставки
    if user.get("stage") == "delivery_confirm":
        user.setdefault("pending_delivery_photos", []).append(file_id)
        if caption:
            user.setdefault("pending_delivery", []).append(caption)
            bot.send_message(chat_id, f"📦 Текст из подписи добавлен в приёмку:\n{caption}")
        else:
            bot.send_message(chat_id, "📦 Фото добавлено к приёмке.")
        return

    bot.send_message(chat_id, "📷 Фото получено, но вы сейчас не оформляете заказ или приёмку.")

# === ОБРАБОТКА ТЕКСТА ===
@bot.message_handler(func=lambda m: True)
def handle_any_message(message):
    chat_id = message.chat.id
    text = message.text.strip() if message.text else ""

    # Обработка команды /start — сброс и выбор магазина для переводов
    if text == "/start":
        user_data[chat_id] = {
            "shop": None,
            "order_shop": None,
            "transfers": [],
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "stage": "choose_shop_transfer",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "order_items": [],
            "order_photos": [],
            "order_date": None,
            "pending_delivery": [],
            "pending_delivery_photos": [],
            "last_order": [],
            "saved_order": []
        }
        bot.send_message(chat_id, "Привет! Выберите магазин для переводов:", reply_markup=get_shop_menu_for_transfer())
        return

    if chat_id not in user_data:
        user_data[chat_id] = {
            "shop": None,
            "order_shop": None,
            "transfers": [],
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "stage": "choose_shop_transfer",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "order_items": [],
            "order_photos": [],
            "order_date": None,
            "pending_delivery": [],
            "pending_delivery_photos": [],
            "last_order": [],
            "saved_order": []
        }

    user = user_data[chat_id]

    # === ВЫБОР МАГАЗИНА ДЛЯ ПЕРЕВОДОВ ===
    if user["stage"] == "choose_shop_transfer":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if text in allowed_shops:
            user.update({
                "shop": text,
                "transfers": [],
                "order_items": [],
                "pending_delivery": [],
                "pending_delivery_photos": [],
                "mode": "add",
                "cash": 0,
                "terminal": 0,
                "stage": "main",
                "date": datetime.now().strftime("%d.%m.%Y"),
                "order_shop": None,
                "order_photos": [],
                "order_date": None
            })
            bot.send_message(chat_id, f"Выбран магазин для переводов: <b>{text}</b>\nСовет: лучше проверить остатки и сделать заказ, чтобы товара было достаточно.", reply_markup=get_main_menu())
            return
        else:
            bot.send_message(chat_id, "Пожалуйста, выберите магазин из списка.", reply_markup=get_shop_menu_for_transfer())
            return

    # === БЛОК ЗАКАЗОВ ===

    if text == "🛍 Заказ":
        if user.get("saved_order"):
            user["order_items"] = user["saved_order"].copy()
            user["stage"] = "order_input"
            order_text = format_order_list(user["order_items"])
            bot.send_message(chat_id,
                             f"💾 У вас есть сохранённый заказ:\n{order_text}\n"
                             "Вы можете продолжить работу с ним.",
                             reply_markup=get_order_action_menu())
        else:
            user["stage"] = "choose_shop_order"
            bot.send_message(chat_id, "Выберите магазин для заказа:", reply_markup=get_shop_menu_for_order())
        return

    if user["stage"] == "choose_shop_order":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if text in allowed_shops:
            user["order_shop"] = text
            user["order_items"] = []
            user["order_photos"] = []
            user["stage"] = "order_input"
            bot.send_message(chat_id, f"Выбран магазин для заказа: <b>{text}</b>\nВведите товары через запятую:", reply_markup=None)
            return
        elif text == "⬅️ Назад":
            user["stage"] = "main"
            bot.send_message(chat_id, "Возвращаемся в главное меню.", reply_markup=get_main_menu())
            return
        else:
            bot.send_message(chat_id, "Пожалуйста, выберите магазин из меню или нажмите '⬅️ Назад'.", reply_markup=get_shop_menu_for_order())
            return

    if user["stage"] == "order_input" and text and text not in ["✅ Отправить заказ", "✏️ Изменить заказ", "💾 Сохранить заказ (не отправлять)", "❌ Отмена"]:
        # Добавляем товары в заказ
        items = sanitize_input(text)
        if items:
            user["order_items"].extend(items)
            order_text = format_order_list(user["order_items"])
            bot.send_message(chat_id, order_text)
            bot.send_message(chat_id, "Выберите действие:", reply_markup=get_order_action_menu())
        else:
            bot.send_message(chat_id, "⚠️ Введите товары через запятую.")
        return

    if text == "✅ Отправить заказ":
        if not user["order_items"]:
            bot.send_message(chat_id, "⚠️ Заказ пуст, нечего отправлять.")
            return
        # Отправляем предупреждение перед отправкой
        warning_text = (
            "📢 Внимание! Если в заказе есть фото, они будут отправлены отдельно с подписью.\n"
            "Отправляем заказ..."
        )
        bot.send_message(chat_id, warning_text)
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
                         "✏️ Напишите позиции, которые хотите удалить через запятую.\n"
                         "Если хотите очистить весь заказ — напишите 'удалить всё'.")
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
        bot.send_message(chat_id, "💾 Хорошо, я сохранил заказ. Вы можете зайти позже и дописать.\nЧтобы заявка ушла — нажмите «✅ Отправить заказ».", reply_markup=get_main_menu())
        return  # выход в главное меню

    if text == "❌ Отмена":
        user["order_items"] = []
        user["order_shop"] = None
        user["order_photos"] = []
        user["stage"] = "main"
        bot.send_message(chat_id, "❌ Действие отменено.", reply_markup=get_main_menu())
        return

    if user["stage"] == "order_edit":
        if text.lower() == "удалить всё":
            user["order_items"] = []
            bot.send_message(chat_id, "🗑️ Заказ очищен.")
        else:
            to_delete = sanitize_input(text)
            initial_len = len(user["order_items"])
            user["order_items"] = [item for item in user["order_items"] if item not in to_delete]
            deleted_count = initial_len - len(user["order_items"])
            if deleted_count:
                bot.send_message(chat_id, f"Удалено позиций: {deleted_count}")
            else:
                bot.send_message(chat_id, "⚠️ Не найдено позиций для удаления.")
        order_text = format_order_list(user["order_items"])
        bot.send_message(chat_id, order_text)
        bot.send_message(chat_id, "Выберите действие:", reply_markup=get_order_action_menu())
        user["stage"] = "order_input"
        return

    # === БЛОК ПРИЕМ ПОСТАВКИ ===

    if text == "📦 Прием поставки":
        user["stage"] = "choose_shop_delivery"
        bot.send_message(chat_id, "Выберите магазин для приёмки поставки:", reply_markup=get_shop_menu_for_order())
        return

    if user["stage"] == "choose_shop_delivery":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if text in allowed_shops:
            user["delivery_shop"] = text
            if user.get("pending_delivery"):
                items = "\n".join(f"• {item}" for item in user["pending_delivery"])
                bot.send_message(chat_id, f"Выберите что приехало (введите через запятую):\n{items}")
                user["stage"] = "delivery_confirm"
            else:
                bot.send_message(chat_id, "Нет отложенных товаров на поставку.")
                user["stage"] = "main"
                bot.send_message(chat_id, "Возвращаемся в главное меню.", reply_markup=get_main_menu())
            return
        elif text == "⬅️ Назад":
            user["stage"] = "main"
            bot.send_message(chat_id, "Возвращаемся в главное меню.", reply_markup=get_main_menu())
            return
        else:
            bot.send_message(chat_id, "Пожалуйста, выберите магазин из меню или нажмите '⬅️ Назад'.", reply_markup=get_shop_menu_for_order())
            return

    if user["stage"] == "delivery_confirm":
        if text.lower() == "удалить всё":
            user["pending_delivery"] = []
            bot.send_message(chat_id, "🗑️ Список отложенных товаров очищен.")
        else:
            arrived = sanitize_input(text)
            initial_pending = user.get("pending_delivery", [])
            not_arrived = [item for item in initial_pending if item not in arrived]
            user["pending_delivery"] = not_arrived
            bot.send_message(chat_id, f"Приняты позиции:\n" + "\n".join(f"• {item}" for item in arrived))
            if not_arrived:
                bot.send_message(chat_id, f"Остались не принятые позиции:\n" + "\n".join(f"• {item}" for item in not_arrived))
            else:
                bot.send_message(chat_id, "Все позиции приняты.")
        user["stage"] = "main"
        bot.send_message(chat_id, "Приёмка завершена.", reply_markup=get_main_menu())
        return

    # === БЛОК ФИНАНСОВ ===

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

    if text.isdigit():
        amount = int(text)
        if user["stage"] == "amount_input":
            # Добавляем перевод или возврат
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

    if user["stage"] == "confirm_report" and text == "✅ Отправить":
        send_report(chat_id)
        user["transfers"] = []
        user["cash"] = 0
        user["terminal"] = 0
        # После отправки отчёта переводим в выбор магазина для переводов
        user["stage"] = "choose_shop_transfer"
        bot.send_message(chat_id, "✅ Отчёт отправлен!\nВыберите магазин для переводов:", reply_markup=get_shop_menu_for_transfer())
        return

    if user["stage"] == "confirm_report" and text == "✏️ Изменить данные":
        user["stage"] = "cash_input"
        bot.send_message(chat_id, "Сколько наличных?:")
        return

    if user["stage"] == "confirm_report" and text == "❌ Отмена":
        user["stage"] = "main"
        bot.send_message(chat_id, "❌ Отмена отправки отчёта.", reply_markup=get_main_menu())
        return

    # В остальных случаях, если ввод текста не ожидается — предлагаем меню
    if user["stage"] not in ["order_input", "order_edit", "amount_input", "cash_input", "terminal_input", "delivery_confirm"]:
        bot.send_message(chat_id, "⚠️ Выберите действие из меню.", reply_markup=get_main_menu())

# === ФУНКЦИИ ОТПРАВКИ ===

def preview_report(chat_id):
    user = user_data[chat_id]
    total_transfer = sum(user["transfers"])
    cash = user.get("cash", 0)
    terminal = user.get("terminal", 0)
    report_text = (f"📄 Отчёт за {user['date']}:\n"
                   f"Сумма переводов: {total_transfer}₽\n"
                   f"Наличные: {cash}₽\n"
                   f"Терминал: {terminal}₽\n"
                   f"Всего: {cash + terminal}₽\n\n"
                   "Подтвердите отправку отчёта:")
    bot.send_message(chat_id, report_text, reply_markup=get_confirm_menu())

def send_report(chat_id):
    user = user_data[chat_id]
    total_transfer = sum(user["transfers"])
    cash = user.get("cash", 0)
    terminal = user.get("terminal", 0)
    date = user.get("date", datetime.now().strftime("%d.%m.%Y"))
    shop = user.get("shop", "не выбран")
    text = (f"📄 <b>Отчёт</b>\n"
            f"Магазин: <b>{shop}</b>\n"
            f"Дата: {date}\n"
            f"Переводы: {total_transfer}₽\n"
            f"Наличные: {cash}₽\n"
            f"Терминал: {terminal}₽\n"
            f"Итого: {cash + terminal}₽")
    # Отправляем в группу в топик отчётов
    bot.send_message(CHAT_ID_FOR_REPORT, text, disable_notification=True)

def send_order(chat_id):
    user = user_data[chat_id]
    order_items = user.get("order_items", [])
    order_photos = user.get("order_photos", [])
    shop = user.get("order_shop", "не выбран")
    date = user.get("order_date", datetime.now().strftime("%d.%m.%Y"))

    text = f"🛒 <b>Новый заказ</b>\nМагазин: <b>{shop}</b>\nДата: {date}\n\n"
    if order_items:
        text += "Заказ:\n" + "\n".join(f"• {item}" for item in order_items)
    else:
        text += "Заказ пуст."

    # Отправляем текст заказа в группу в топик заказов
    bot.send_message(CHAT_ID_FOR_REPORT, text, disable_notification=True)

    # Отправляем фото отдельными сообщениями с подписью
    for photo_id in order_photos:
        bot.send_photo(CHAT_ID_FOR_REPORT, photo_id, caption=f"Фото из заказа магазина <b>{shop}</b>", disable_notification=True)

if __name__ == "__main__":
    print("Бот запущен...")
    bot.infinity_polling()
