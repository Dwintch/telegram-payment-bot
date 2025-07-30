import os
import json
import logging
from datetime import datetime

import telebot
from telebot import types
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID_FOR_REPORT = -1002826712980
THREAD_ID_FOR_REPORT = 3
THREAD_ID_FOR_ORDER = 64
GOOGLE_SHEET_NAME = 'Отчёты'
CREDENTIALS_FILE = 'credentials.json'

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
user_data = {}

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).sheet1


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
    markup.add("⬅️ Назад")
    return markup


def get_confirm_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ Отправить отчёт", "✏️ Изменить данные", "❌ Отмена")
    return markup


def get_order_action_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ Отправить заказ", "✏️ Изменить заказ")
    markup.add("💾 Сохранить заказ (не отправлять)", "❌ Отмена")
    return markup


def sanitize_input(text):
    return [item.strip() for item in text.split(',') if item.strip()]


def format_order_list(items):
    if not items:
        return "📋 Заказ пуст."
    return "📋 Текущий заказ:\n" + "\n".join(f"• {item}" for item in items)


def ensure_user(chat_id):
    if chat_id not in user_data:
        user_data[chat_id] = {
            "shop": None,
            "order_shop": None,
            "orders_by_shop": {"Янтарь": [], "Хайп": [], "Полка": []},
            "pending_delivery": {"Янтарь": [], "Хайп": [], "Полка": []},
            "transfers": [],
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "stage": "main",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "order_items": [],
            "order_photos": [],
            "order_date": None,
            "last_order": [],
            "saved_order": []
        }
    return user_data[chat_id]


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


@bot.message_handler(func=lambda m: True)
def handle_any_message(message):
    chat_id = message.chat.id
    text = message.text.strip()
    user = ensure_user(chat_id)

    if text == "/start":
        user_data[chat_id].update({
            "shop": None,
            "order_shop": None,
            "orders_by_shop": {"Янтарь": [], "Хайп": [], "Полка": []},
            "pending_delivery": {"Янтарь": [], "Хайп": [], "Полка": []},
            "transfers": [],
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "stage": "main",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "order_items": [],
            "order_photos": [],
            "order_date": None,
            "last_order": [],
            "saved_order": []
        })
        bot.send_message(chat_id, "Привет! Выберите магазин для переводов:", reply_markup=get_shop_menu())
        return

    # Главный выбор магазина для переводов
    if user["stage"] == "main" and text in ["Янтарь", "Хайп", "Полка"]:
        user.update({
            "shop": text,
            "transfers": [],
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "date": datetime.now().strftime("%d.%m.%Y"),
        })
        bot.send_message(chat_id, f"Выбран магазин для переводов: <b>{text}</b>", reply_markup=get_main_menu())
        return

    if text == "❌ Отменить":
        user.update({"mode": "add", "cash": 0, "terminal": 0, "stage": "main", "order_shop": None, "order_items": [], "order_photos": []})
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
        if not user["transfers"]:
            bot.send_message(chat_id, "⚠️ Нет данных для отчёта. Сначала добавьте переводы.")
            return
        user["stage"] = "cash_input"
        total = sum(user["transfers"])
        bot.send_message(chat_id, f"🧾 Переводов на сумму: <b>{total}₽</b>\nВведите сумму наличных:")
        return

    if text.isdigit():
        amount = int(text)
        if user["stage"] in ["amount_input", "main"]:
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

    if user["stage"] == "confirm_report":
        if text == "✅ Отправить отчёт":
            send_report(chat_id)
            user["stage"] = "main"
            user["transfers"] = []
            user["cash"] = 0
            user["terminal"] = 0
            bot.send_message(chat_id, "✅ Отчёт успешно отправлен!", reply_markup=get_main_menu())
            return
        elif text == "✏️ Изменить данные":
            user["stage"] = "cash_input"
            bot.send_message(chat_id, "Сколько наличных?:")
            return
        elif text == "❌ Отмена":
            user["stage"] = "main"
            bot.send_message(chat_id, "❌ Отмена отправки отчёта.", reply_markup=get_main_menu())
            return
        else:
            bot.send_message(chat_id, "⚠️ Пожалуйста, используйте кнопки меню.", reply_markup=get_confirm_menu())
            return

    # --- Заказы ---
    if text == "🛍 Заказ":
        user["stage"] = "choose_shop"
        bot.send_message(chat_id, "Выберите магазин для заказа:", reply_markup=get_shop_menu())
        return

    if user["stage"] == "choose_shop":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if text in allowed_shops:
            user["order_shop"] = text
            current_order = user["orders_by_shop"].get(text, [])
            user["order_items"] = current_order.copy()
            user["order_photos"] = []
            user["stage"] = "order_input"
            order_text = format_order_list(user["order_items"])
            bot.send_message(chat_id, f"Выбран магазин для заказа: <b>{text}</b>\n{order_text}\nВведите товары через запятую или кнопки действия:", reply_markup=get_order_action_menu())
            return
        elif text == "⬅️ Назад":
            user["stage"] = "main"
            bot.send_message(chat_id, "Возвращаемся в главное меню.", reply_markup=get_main_menu())
            return
        else:
            bot.send_message(chat_id, "Пожалуйста, выберите магазин из меню или нажмите '⬅️ Назад'.", reply_markup=get_shop_menu())
            return

    if user["stage"] == "order_input":
        if text == "✅ Отправить заказ":
            if not user["order_items"]:
                bot.send_message(chat_id, "⚠️ Заказ пуст, нечего отправлять.")
                return
            send_order(chat_id)
            # Сохраняем заказ в orders_by_shop
            user["orders_by_shop"][user["order_shop"]] = user["order_items"].copy()
            # Добавляем в pending_delivery (для приёма поставки)
            pending = user["pending_delivery"].get(user["order_shop"], [])
            for item in user["order_items"]:
                if item not in pending:
                    pending.append(item)
            user["pending_delivery"][user["order_shop"]] = pending

            user["last_order"] = user["order_items"].copy()
            user["order_items"] = []
            user["order_photos"] = []
            user["order_shop"] = None
            user["stage"] = "main"
            bot.send_message(chat_id, "✅ Заказ отправлен!", reply_markup=get_main_menu())
            return

        elif text == "✏️ Изменить заказ":
            if not user["order_items"]:
                bot.send_message(chat_id, "⚠️ Заказ пуст, нечего изменять.")
                return
            bot.send_message(chat_id,
                             "✏️ Напишите позиции, которые хотите удалить через запятую.\n"
                             "Если хотите очистить весь заказ — напишите 'удалить всё'.")
            user["stage"] = "order_edit"
            return

        elif text == "💾 Сохранить заказ (не отправлять)":
            if not user["order_items"]:
                bot.send_message(chat_id, "⚠️ Заказ пуст, нечего сохранять.")
                return
            user["saved_order"] = user["order_items"].copy()
            user["stage"] = "main"
            bot.send_message(chat_id, "💾 Хорошо, я сохранил заказ. Вы можете зайти позже и дописать.\nЧтобы заявка ушла — нажмите «✅ Отправить заказ».", reply_markup=get_main_menu())
            return

        else:
            items = sanitize_input(text)
            if items:
                user["order_items"].extend(items)
                order_text = format_order_list(user["order_items"])
                bot.send_message(chat_id, order_text)
                bot.send_message(chat_id, "Выберите действие:", reply_markup=get_order_action_menu())
            else:
                bot.send_message(chat_id, "⚠️ Введите товары через запятую.")
            return

    if text == "❌ Отмена" and user["stage"] in ["order_input", "order_edit"]:
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

    # --- Прием поставки ---
    if text == "📦 Прием поставки":
        shops_with_pending = [shop for shop, items in user["pending_delivery"].items() if items]
        if not shops_with_pending:
            bot.send_message(chat_id, "Нет отложенных товаров на поставку.")
            return
        user["stage"] = "delivery_choose_shop"
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        for shop in shops_with_pending:
            markup.add(shop)
        markup.add("⬅️ Назад")
        bot.send_message(chat_id, "Выберите магазин, по которому принимаем поставку:", reply_markup=markup)
        return

    if user["stage"] == "delivery_choose_shop":
        if text in ["Янтарь", "Хайп", "Полка"]:
            pending_items = user["pending_delivery"].get(text, [])
            if not pending_items:
                bot.send_message(chat_id, f"Нет отложенных товаров для магазина {text}.")
                user["stage"] = "main"
                bot.send_message(chat_id, "Возвращаемся в главное меню.", reply_markup=get_main_menu())
                return
            user["order_shop"] = text
            user["stage"] = "delivery_confirm"
            bot.send_message(chat_id,
                             f"Товары, ожидающие поставку для <b>{text}</b>:\n" +
                             "\n".join(f"• {item}" for item in pending_items) +
                             "\n\nВведите через запятую те товары, которые приехали (или 'все', если все приехали).",
                             reply_markup=None)
            return
        elif text == "⬅️ Назад":
            user["stage"] = "main"
            bot.send_message(chat_id, "Возвращаемся в главное меню.", reply_markup=get_main_menu())
            return
        else:
            bot.send_message(chat_id, "Пожалуйста, выберите магазин из меню или нажмите '⬅️ Назад'.", reply_markup=get_shop_menu())
            return

    if user["stage"] == "delivery_confirm":
        pending_items = user["pending_delivery"].get(user["order_shop"], [])
        if not pending_items:
            bot.send_message(chat_id, "Нет отложенных товаров для данного магазина.")
            user["stage"] = "main"
            return

        if text.lower() == "все":
            # Все товары приехали — очищаем pending_delivery для магазина
            user["pending_delivery"][user["order_shop"]] = []
            bot.send_message(chat_id, f"Все товары для магазина <b>{user['order_shop']}</b> отмечены как приехавшие.")
        else:
            arrived = sanitize_input(text)
            # Оставляем в pending_delivery только те, что НЕ приехали
            new_pending = [item for item in pending_items if item not in arrived]
            user["pending_delivery"][user["order_shop"]] = new_pending
            bot.send_message(chat_id,
                             f"Отмечено как приехавшие: {len(arrived)}\n"
                             f"Осталось в отложенных: {len(new_pending)}")
        user["stage"] = "main"
        user["order_shop"] = None
        bot.send_message(chat_id, "Поставку обработали. Возвращаемся в главное меню.", reply_markup=get_main_menu())
        return

    # Если ничего не подошло — предлагаем меню
    bot.send_message(chat_id, "⚠️ Выберите действие из меню.", reply_markup=get_main_menu())


def round_to_50(value):
    remainder = value % 50
    return int(value - remainder) if remainder < 25 else int(value + (50 - remainder))


def preview_report(chat_id):
    data = user_data[chat_id]
    transfers = sum(data["transfers"])
    total = transfers + data["cash"] + data["terminal"]
    if data["shop"] == "Янтарь":
        total = round_to_50(total)
    msg = (
        f"Отчёт по магазину <b>{data['shop']}</b> за <b>{data['date']}</b>:\n"
        f"Переводы: <b>{transfers}₽</b>\n"
        f"Наличные: <b>{data['cash']}₽</b>\n"
        f"Терминал: <b>{data['terminal']}₽</b>\n"
        f"Итого: <b>{total}₽</b>"
    )
    bot.send_message(chat_id, msg, reply_markup=get_confirm_menu())


def send_report(chat_id):
    data = user_data[chat_id]
    transfers = sum(data["transfers"])
    total = transfers + data["cash"] + data["terminal"]
    if data["shop"] == "Янтарь":
        total = round_to_50(total)
    text = (
        f"Отчёт по магазину <b>{data['shop']}</b> за <b>{data['date']}</b>:\n"
        f"Переводы: <b>{transfers}₽</b>\n"
        f"Наличные: <b>{data['cash']}₽</b>\n"
        f"Терминал: <b>{data['terminal']}₽</b>\n"
        f"Итого: <b>{total}₽</b>"
    )
    # Отправляем в группу отчетов в нужный топик
    bot.send_message(CHAT_ID_FOR_REPORT, text, message_thread_id=THREAD_ID_FOR_REPORT)


def send_order(chat_id):
    data = user_data[chat_id]
    shop = data["order_shop"]
    items = data["order_items"]
    photos = data.get("order_photos", [])
    if not shop or not items:
        bot.send_message(chat_id, "Ошибка: нет магазина или товаров для отправки заказа.")
        return
    text = f"🛒 <b>Заказ по магазину {shop}</b>:\n" + "\n".join(f"• {item}" for item in items)
    # Отправляем в группу заказов в топик 64
    bot.send_message(CHAT_ID_FOR_REPORT, text, message_thread_id=THREAD_ID_FOR_ORDER)
    # Отправляем фото, если есть
    for photo_id in photos:
        bot.send_photo(CHAT_ID_FOR_REPORT, photo_id, message_thread_id=THREAD_ID_FOR_ORDER)


if __name__ == '__main__':
    print("Bot started...")
    bot.infinity_polling()
