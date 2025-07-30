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
    markup.add("✅ Отправить", "✏️ Изменить данные", "❌ Отмена")
    return markup

def get_order_action_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ Отправить заказ", "✏️ Изменить заказ")
    markup.add("💾 Сохранить заказ (не отправлять)", "❌ Отмена")
    return markup

# === ВСПОМОГАТЕЛЬНЫЕ ===
def sanitize_input(text):
    # Разделяем и по запятым, и по новым строкам, убираем пустые
    items = []
    for part in text.split(','):
        items.extend([x.strip() for x in part.split('\n') if x.strip()])
    return items

def format_order_list(items):
    if not items:
        return "📋 Заказ пуст."
    return "📋 Текущий заказ:\n" + "\n".join(f"• {item}" for item in items)

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

# === ОБРАБОТКА ТЕКСТА ===
@bot.message_handler(func=lambda m: True)
def handle_any_message(message):
    chat_id = message.chat.id
    text = message.text.strip()

    # Инициализация данных пользователя
    if chat_id not in user_data or text == "/start":
        user_data[chat_id] = {
            "shop": None,
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
            "accepted_delivery": [],
            "last_order": [],
            "saved_order": []
        }
        bot.send_message(chat_id, "Привет! Выберите магазин для переводов:", reply_markup=get_shop_menu())
        return

    user = user_data[chat_id]

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

    if user["stage"] == "choose_shop_order":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if text in allowed_shops:
            user["order_shop"] = text
            user["order_items"] = []
            user["order_photos"] = []
            user["stage"] = "order_input"
            bot.send_message(chat_id, f"Выбран магазин для заказа: <b>{text}</b>\nВведите товары через запятую или с новой строки:", reply_markup=None)
            return
        else:
            bot.send_message(chat_id, "Пожалуйста, выберите магазин из меню.", reply_markup=get_shop_menu())
            return

    if user["stage"] == "order_input":
        if text in ["✅ Отправить заказ", "✏️ Изменить заказ", "💾 Сохранить заказ (не отправлять)", "❌ Отмена"]:
            # Обработка кнопок
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
                                 "Если хотите очистить весь заказ — напишите что-то типа 'удалить всё', 'очистить', 'сбросить'.")
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
                return

            if text == "❌ Отмена":
                user["order_items"] = []
                user["order_shop"] = None
                user["order_photos"] = []
                user["stage"] = "main"
                bot.send_message(chat_id, "❌ Действие отменено.", reply_markup=get_main_menu())
                return

        else:
            # Добавляем позиции из текста
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
            # Удаляем приблизительно с учетом регистра и пробелов
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

    if user["stage"] == "choose_shop_delivery":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if text in allowed_shops:
            user["order_shop"] = text
            # Собираем ожидаемые товары из последнего заказа для этого магазина из всех пользователей
            pending = []
            for u in user_data.values():
                if u.get("order_shop") == text and u.get("last_order"):
                    pending.extend(u["last_order"])
            pending = list(set(pending))  # Уникальные позиции

            if "accepted_delivery" not in user:
                user["accepted_delivery"] = []
            # Исключаем уже принятые товары
            user["pending_delivery"] = [item for item in pending if item not in user["accepted_delivery"]]

            if user["pending_delivery"]:
                items_list = "\n".join(f"• {item}" for item in user["pending_delivery"])
                bot.send_message(chat_id, f"Выберите что приехало (введите через запятую или с новой строки):\n{items_list}")
                user["stage"] = "delivery_confirm"
            else:
                bot.send_message(chat_id, "Нет отложенных товаров на поставку для этого магазина.")
                user["stage"] = "main"
            return
        else:
            bot.send_message(chat_id, "Пожалуйста, выберите магазин из меню.", reply_markup=get_shop_menu())
            return

    if user["stage"] == "delivery_confirm":
        arrived = sanitize_input(text)

        # Проверяем, есть ли товары, которых нет в списке ожидаемых
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
            bot.send_message(chat_id, f"Оставшиеся товары перенесены в следующую заявку.")
        else:
            bot.send_message(chat_id, "Все товары приняты.")
            # Сброс принятого после полного приема
            user["accepted_delivery"] = []

        user["stage"] = "main"
        return

    # === ФИНАНСЫ ===
    if text in ["Янтарь", "Хайп", "Полка"] and user["stage"] == "main":
        user.update({
            "shop": text,
            "transfers": [],
            "order_items": [],
            "pending_delivery": [],
            "accepted_delivery": [],
            "mode": "add",
            "cash": 0,
            "terminal": 0,
            "stage": "main",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "order_shop": None,
            "order_photos": [],
            "order_date": None
        })
        bot.send_message(chat_id, f"Выбран магазин для переводов: <b>{text}</b>\nРекомендуем проверить остатки и сделать заказ!", reply_markup=get_main_menu())
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

    # Обработка числового ввода (суммы и т.п.)
    if text.isdigit():
        amount = int(text)
        if user["stage"] == "main":
            # Добавляем перевод если на главном меню просто число
            user["transfers"].append(amount)
            bot.send_message(chat_id, f"✅ Добавлено в переводы: {amount}₽")
            total = sum(user["transfers"])
            bot.send_message(chat_id, f"💰 Текущая сумма: <b>{total}₽</b>", reply_markup=get_main_menu())
            return

        if user["stage"] == "amount_input":
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
        elif text == "❌ Отмена":
            user["stage"] = "main"
            bot.send_message(chat_id, "❌ Отмена. Выберите действие:", reply_markup=get_main_menu())
            return

    bot.send_message(chat_id, "❓ Неизвестная команда. Выберите действие:", reply_markup=get_main_menu())

# === ФУНКЦИИ ОТПРАВКИ ===
def send_order(chat_id):
    user = user_data[chat_id]
    shop = user.get("order_shop", "Неизвестный магазин")
    order_items = user.get("order_items", [])
    order_photos = user.get("order_photos", [])

    text = f"🛒 Новый заказ из магазина <b>{shop}</b>:\n"
    text += "\n".join(f"• {item}" for item in order_items)

    bot.send_message(CHAT_ID_FOR_REPORT, text, disable_web_page_preview=True)

    for photo in order_photos:
        bot.send_photo(CHAT_ID_FOR_REPORT, photo["file_id"], caption=photo["caption"] or None)

    user["last_order"] = order_items.copy()

def preview_report(chat_id):
    user = user_data[chat_id]
    total_transfers = sum(user.get("transfers", []))
    cash = user.get("cash", 0)
    terminal = user.get("terminal", 0)
    text = f"🧾 Отчёт по переводам:\n"
    text += f"Сумма переводов: <b>{total_transfers}₽</b>\n"
    text += f"Наличные: <b>{cash}₽</b>\n"
    text += f"Терминал: <b>{terminal}₽</b>\n"
    text += "✅ Отправить / ✏️ Изменить данные / ❌ Отмена"
    bot.send_message(chat_id, text, reply_markup=get_confirm_menu())

def send_report(chat_id):
    user = user_data[chat_id]
    total_transfers = sum(user.get("transfers", []))
    cash = user.get("cash", 0)
    terminal = user.get("terminal", 0)
    date = user.get("date", datetime.now().strftime("%d.%m.%Y"))
    shop = user.get("shop", "Неизвестный магазин")

    text = f"📅 Отчёт за {date}\n"
    text += f"Магазин: <b>{shop}</b>\n"
    text += f"Сумма переводов: <b>{total_transfers}₽</b>\n"
    text += f"Наличные: <b>{cash}₽</b>\n"
    text += f"Терминал: <b>{terminal}₽</b>"

    bot.send_message(CHAT_ID_FOR_REPORT, text)

    try:
        sheet.append_row([date, shop, total_transfers, cash, terminal])
    except Exception as e:
        logging.error(f"Ошибка записи в Google Sheets: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Бот запущен...")
    bot.infinity_polling()
