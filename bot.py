import os
import json
import logging
from datetime import datetime
import threading
import schedule
import time

import telebot
from telebot import types
from dotenv import load_dotenv
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests  # Для работы с OpenWeather

# === ЗАГРУЗКА .ENV ===
load_dotenv()

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID_FOR_REPORT = -1002826712980
THREAD_ID_FOR_REPORT = 3
THREAD_ID_FOR_ORDER = 64
GOOGLE_SHEET_NAME = 'Отчёты'
CREDENTIALS_FILE = 'credentials.json'

# === НАСТРОЙКИ ПОГОДЫ ===
OPENWEATHER_API_KEY = "0657e04209d46b14a466de79282d9ca7"
OPENWEATHER_CITY = "Gelendzhik"  # Город всегда Геленджик!
WEATHER_LOG_FILE = "weather_log.json"

bot = telebot.TeleBot(BOT_TOKEN, parse_mode='HTML')
user_data = {}

# === ГЛОБАЛЬНОЕ ХРАНИЛИЩЕ ДАННЫХ ПО МАГАЗИНАМ ===
shop_data = {
    "Янтарь": {
        "last_order": [],
        "pending_delivery": [],
        "accepted_delivery": []
    },
    "Хайп": {
        "last_order": [],
        "pending_delivery": [],
        "accepted_delivery": []
    },
    "Полка": {
        "last_order": [],
        "pending_delivery": [],
        "accepted_delivery": []
    }
}

# === ХРАНИЛИЩЕ MESSAGE_ID ЗАКАЗОВ ПО МАГАЗИНАМ ===
shop_order_messages = {}  # {shop_name: {"message_id": int, "photos": [], "videos": []}}

# === СПИСОК СОТРУДНИКОВ ===
STAFF_LIST = ["Данил", "Даниз", "Даша", "Соня", "Оксана", "Лиза"]

# === GOOGLE SHEETS ===
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)
sheet = client.open(GOOGLE_SHEET_NAME).sheet1

# === ФУНКЦИИ ДЛЯ АВТОМАТИЧЕСКОГО МОНИТОРИНГА ПОГОДЫ ===
def get_weather_raw():
    url = f"http://api.openweathermap.org/data/2.5/weather?q={OPENWEATHER_CITY}&appid={OPENWEATHER_API_KEY}&units=metric&lang=ru"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            temp = data["main"]["temp"]
            weather_main = data["weather"][0]["main"].lower()
            weather_desc = data["weather"][0]["description"]
            wind_speed = data["wind"]["speed"]
            rain = 0
            if "rain" in data and "1h" in data["rain"]:
                rain = data["rain"]["1h"]
            return {
                "timestamp": datetime.now().isoformat(),
                "temp": temp,
                "weather": weather_main,
                "weather_desc": weather_desc,
                "rain": rain,
                "wind": wind_speed
            }
        else:
            logging.warning(f"OpenWeather error: {response.status_code}")
            return None
    except Exception as e:
        logging.error(f"Ошибка получения погоды: {e}")
        return None

def log_weather():
    now = datetime.now()
    if 9 <= now.hour < 23:
        weather = get_weather_raw()
        if weather:
            try:
                if os.path.exists(WEATHER_LOG_FILE):
                    with open(WEATHER_LOG_FILE, "r") as f:
                        weather_log = json.load(f)
                else:
                    weather_log = []
                weather_log.append(weather)
                with open(WEATHER_LOG_FILE, "w") as f:
                    json.dump(weather_log, f)
            except Exception as e:
                logging.error(f"Ошибка сохранения погоды: {e}")

def weather_monitor_thread():
    schedule.every(10).minutes.do(log_weather)
    while True:
        schedule.run_pending()
        time.sleep(5)

# Запуск мониторинга в отдельном потоке
weather_thread = threading.Thread(target=weather_monitor_thread, daemon=True)
weather_thread.start()

def get_weather_report():
    if not os.path.exists(WEATHER_LOG_FILE):
        return "Нет данных по погоде за сегодня."
    with open(WEATHER_LOG_FILE, "r") as f:
        weather_log = json.load(f)
    today = datetime.now().date()
    today_log = [entry for entry in weather_log if datetime.fromisoformat(entry["timestamp"]).date() == today]
    if not today_log:
        return "Нет данных по погоде за сегодня."
    temps = [entry["temp"] for entry in today_log]
    wind_speeds = [entry["wind"] for entry in today_log]
    rain_periods = [entry for entry in today_log if entry["rain"] > 0]
    rain_total = sum(entry["rain"] for entry in rain_periods)
    rain_hours = len(rain_periods) * 10 / 60
    # Вместо средней температуры — максимальная (пиковая)
    max_temp = round(max(temps), 1)
    avg_wind = round(sum(wind_speeds) / len(wind_speeds), 1)
    rain_was = "да" if rain_total > 0 else "нет"
    report = (
        f"<b>Погодный отчёт за сегодня:</b>\n"
        f"Пиковая температура: <b>{max_temp}°C</b>\n"
        f"Дождь был: <b>{rain_was}</b>\n"
        f"Дождь (время): <b>{rain_hours:.2f} ч</b>, всего выпало <b>{rain_total:.2f} мм</b>\n"
        f"Средний ветер: <b>{avg_wind} м/с</b>"
    )
    return report

# === КНОПКИ ===
def get_main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("💰 Перевод", "💸 Возврат")
    markup.add("📄 Составить отчёт", "👀 Посмотреть сумму")
    markup.add("🛍 Заказ", "📦 Прием поставки")
    markup.add("❌ Отменить")
    return markup

def get_shop_menu(include_back=False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Янтарь", "Хайп", "Полка")
    if include_back:
        markup.add("⬅️ Назад")
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

def get_delivery_confirm_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("✅ Всё верно, отправить отчёт", "✏️ Изменить отметки")
    markup.add("❌ Отмена")
    return markup

def get_staff_keyboard(selected_staff=None):
    selected_staff = selected_staff or []
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for staff in STAFF_LIST:
        text = f"✅ {staff}" if staff in selected_staff else staff
        callback_data = f"staff_{staff}"
        buttons.append(types.InlineKeyboardButton(text, callback_data=callback_data))
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("Далее", callback_data="staff_done"))
    return markup

def get_delivery_keyboard(pending_items, arrived_items=None):
    """Создаёт инлайн-клавиатуру для отметки товаров при приёмке поставки"""
    arrived_items = arrived_items or []
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for item in pending_items:
        status = "✅" if item in arrived_items else "❌"
        text = f"{status} {item}"
        callback_data = f"delivery_toggle_{pending_items.index(item)}"
        markup.add(types.InlineKeyboardButton(text, callback_data=callback_data))
    
    markup.add(types.InlineKeyboardButton("📦 Отправить приёмку", callback_data="delivery_submit"))
    return markup

def sanitize_input(text):
    items = []
    for part in text.split(','):
        items.extend([x.strip() for x in part.split('\n') if x.strip()])
    return items

def deduplicate_order_items(items):
    """Remove duplicates from order items while preserving order"""
    seen = set()
    unique_items = []
    for item in items:
        item_lower = item.lower().strip()
        if item_lower not in seen:
            seen.add(item_lower)
            unique_items.append(item)
    return unique_items

def merge_order(chat_id, new_items):
    """Merge new items with current session order items"""
    user = user_data.get(chat_id)
    if not user:
        return new_items
    
    previous_order = user.get("order_items", [])
    
    if not previous_order:
        # No previous order in session, just return new items
        return new_items
    
    # Combine current session order with new items
    combined_items = previous_order + new_items
    # Remove duplicates while preserving order
    combined_items = deduplicate_order_items(combined_items)
    
    # Send informative message to user
    previous_order_text = ", ".join(previous_order)
    new_items_text = ", ".join(new_items)
    combined_text = ", ".join(combined_items)
    
    merge_message = (
        f"📦 <b>У тебя был заказ:</b> {previous_order_text}\n"
        f"➕ <b>Добавляю к твоему заказу:</b> {new_items_text}\n"
        f"🔄 <b>Вот обновлённый заказ:</b> {combined_text}"
    )
    
    bot.send_message(chat_id, merge_message)
    
    return combined_items

def format_order_list(items, arrived=None, show_appended_info=False, original_count=0):
    if not items:
        return "📋 Заказ пуст."
    
    result = "📋 Текущий заказ:\n"
    if show_appended_info and original_count > 0:
        result += f"📦 Оригинальных позиций: {original_count}\n"
        result += f"➕ Добавлено до-заказом: {len(items) - original_count}\n"
        result += f"📊 Всего позиций: {len(items)}\n\n"
    
    for i, item in enumerate(items):
        if arrived is not None:
            if item in arrived:
                result += f"✅ {item}\n"
            else:
                result += f"❌ {item}\n"
        else:
            # Show which items are original vs appended
            if show_appended_info and original_count > 0:
                if i < original_count:
                    result += f"📦 {item}\n"
                else:
                    result += f"➕ {item}\n"
            else:
                result += f"• {item}\n"
    return result

def round_to_50(value):
    remainder = value % 50
    if remainder < 25:
        return int(value - remainder)
    else:
        return int(value + (50 - remainder))

@bot.message_handler(content_types=['photo', 'video'])
def handle_media(message):
    chat_id = message.chat.id
    user = user_data.get(chat_id)
    caption = message.caption or ""
    if not user:
        bot.send_message(chat_id, "📷/🎬 Медиа получено, но вы не в сессии.")
        return

    stage = user.get("stage")
    if stage not in ["order_input", "delivery_confirm"]:
        bot.send_message(chat_id, "📷/🎬 Медиа получено, но сейчас вы не оформляете заказ/приемку/до-заказ.")
        return

    # Prevent media from being added during delivery confirmation
    if stage == "delivery_confirm":
        bot.send_message(chat_id, "⚠️ Медиа-файлы нельзя добавлять во время приёмки поставки.")
        return

    if message.content_type == 'photo':
        file_id = message.photo[-1].file_id
        # Add clarification note to caption
        clarification_caption = f"Фото для уточнения, не отмечается в приёмке. {caption}".strip()
        user.setdefault("order_photos", []).append({"file_id": file_id, "caption": clarification_caption})
        bot.send_message(chat_id, "📸 Фото добавлено с пометкой для уточнения!")
    elif message.content_type == 'video':
        file_id = message.video.file_id
        # Add clarification note to caption
        clarification_caption = f"Видео для уточнения, не отмечается в приёмке. {caption}".strip()
        user.setdefault("order_videos", []).append({"file_id": file_id, "caption": clarification_caption})
        bot.send_message(chat_id, "🎬 Видео добавлено с пометкой для уточнения!")

@bot.message_handler(commands=['start'])
def start(message):
    chat_id = message.chat.id
    user_data[chat_id] = {
        # === ТОЛЬКО UI СОСТОЯНИЕ И ВРЕМЕННЫЕ ДАННЫЕ СЕССИИ ===
        "shop": None,  # Выбранный магазин для отчетов
        "order_shop": None,  # Выбранный магазин для заказов (временно во время сессии)
        "transfers": [],  # Переводы для отчета
        "mode": "add",  # Режим добавления/вычитания переводов
        "cash": 0,  # Наличные для отчета
        "terminal": 0,  # Терминал для отчета
        "stage": "choose_shop",  # Стадия диалога
        "date": datetime.now().strftime("%d.%m.%Y"),  # Дата отчета
        "order_items": [],  # Временные товары для текущей сессии заказа
        "order_photos": [],  # Временные фото для текущей сессии заказа
        "order_videos": [],  # Временные видео для текущей сессии заказа
        "delivery_arrived": [],  # Временный список прибывших товаров при приемке
        "delivery_message_id": None,  # ID сообщения с кнопками приёмки
        "selected_staff": [],  # Выбранные сотрудники для отчета
        "order_is_appended": False,  # Флаг объединения заказа (временный)
        "original_order_count": 0,  # Количество позиций до объединения (временно)
        "saved_order": []  # Локально сохраненный заказ пользователя
    }
    bot.send_message(chat_id, "Привет! Выберите магазин для переводов:", reply_markup=get_shop_menu())

@bot.message_handler(func=lambda m: m.text in ["Янтарь", "Хайп", "Полка", "⬅️ Назад"])
def choose_shop(message):
    chat_id = message.chat.id
    user = user_data.get(chat_id)
    # Кнопка Назад для заказа
    if message.text == "⬅️ Назад":
        user["stage"] = "main"
        bot.send_message(chat_id, "Вы вернулись в главное меню.", reply_markup=get_main_menu())
        return

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
            "order_videos": [],
            "delivery_arrived": [],
            "delivery_message_id": None,
            "selected_staff": [],
            "order_is_appended": False,
            "original_order_count": 0,
            "saved_order": []
        })
        bot.send_message(chat_id, f"Выбран магазин: <b>{message.text}</b>", reply_markup=get_main_menu())
        return

    if user.get("stage") == "choose_shop_order":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if message.text in allowed_shops:
            user["order_shop"] = message.text
            shop = message.text
            
            # Step 1: Start with pending delivery items (leftovers from previous deliveries)
            # ИСПОЛЬЗУЕМ ГЛОБАЛЬНЫЕ ДАННЫЕ МАГАЗИНА
            shop_info = shop_data[shop]
            leftovers = shop_info["pending_delivery"].copy()
            combined_items = leftovers.copy() if leftovers else []
            
            # Step 2: Check if there's an existing last_order for this shop and merge it
            # BUT exclude items that have already been accepted
            existing_order_items = shop_info["last_order"].copy()
            accepted_items = shop_info["accepted_delivery"]
            
            # Filter out already accepted items from existing order
            filtered_existing_items = [item for item in existing_order_items if item not in accepted_items]
            
            if filtered_existing_items:
                combined_items.extend(filtered_existing_items)
                existing_order_combined = True
            
            # Step 3: Remove duplicates from combined items
            combined_items = deduplicate_order_items(combined_items)
            
            # Step 4: Set up order state (no automatic media copying)
            user["order_items"] = combined_items
            user["order_photos"] = []
            user["order_videos"] = []
            user["order_is_appended"] = len(combined_items) > 0
            user["original_order_count"] = len(combined_items)
            
            # Note: Media files are NOT automatically copied from previous orders
            # Users must add new media files if needed
            
            user["stage"] = "order_input"
            
            # Step 6: Prepare consolidated info message
            if leftovers or filtered_existing_items:
                info_parts = []
                
                if leftovers and filtered_existing_items:
                    info_parts.append(f"📦 Добавлено из прошлой поставки: {len(leftovers)} поз.")
                    info_parts.append(f"🔄 Объединено из существующего заказа: {len(filtered_existing_items)} поз.")
                elif leftovers:
                    info_parts.append(f"📦 Автоматически добавлены товары из прошлой поставки ({len(leftovers)} поз.)")
                elif filtered_existing_items:
                    info_parts.append(f"🔄 Объединены товары из существующего заказа ({len(filtered_existing_items)} поз.)")
                
                total_before_dedup = len(leftovers) + len(filtered_existing_items)
                total_combined = len(combined_items)
                duplicates_removed = total_before_dedup - total_combined
                
                if duplicates_removed > 0:
                    info_parts.append(f"🗑️ Удалено дублей: {duplicates_removed}")
                
                if accepted_items:
                    info_parts.append(f"✅ Исключено уже принятых товаров: {len(accepted_items)} поз.")
                
                info_parts.append(f"📊 Итого позиций в заказе: {total_combined}")
                
                consolidated_message = f"ℹ️ <b>Информация о заказе:</b>\n" + "\n".join(f"• {part}" for part in info_parts)
                bot.send_message(chat_id, consolidated_message)
            
            # Main shop selection message
            shop_msg = f"🛒 Выбран магазин для заказа: <b>{shop}</b>\n"
            if total_combined > 0:
                shop_msg += f"📝 Текущий заказ содержит {total_combined} позиций. Можете дополнить заказ или отправить его:"
                # Show current order
                current_order_text = format_order_list(user["order_items"], show_appended_info=user.get("order_is_appended", False), original_count=user.get("original_order_count", 0))
                bot.send_message(chat_id, current_order_text)
            else:
                shop_msg += "📝 Введите товары через запятую или с новой строки:"
                
            bot.send_message(chat_id, shop_msg, reply_markup=get_order_action_menu())
            return

    if user.get("stage") == "choose_shop_delivery":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if message.text in allowed_shops:
            user["order_shop"] = message.text
            shop = message.text
            
            # ИСПОЛЬЗУЕМ ГЛОБАЛЬНЫЕ ДАННЫЕ МАГАЗИНА ДЛЯ ПРИЕМКИ
            shop_info = shop_data[shop]
            pending_items = shop_info["pending_delivery"].copy()
            
            if pending_items:
                # Новый интерфейс с инлайн-кнопками
                user["delivery_arrived"] = []  # Список прибывших товаров
                user["stage"] = "delivery_buttons"
                
                items_text = f"📦 <b>Приёмка поставки для магазина {shop}</b>\n\n"
                items_text += "Отметьте какие товары приехали, нажимая на кнопки:\n"
                items_text += "✅ = приехало, ❌ = не приехало\n\n"
                
                delivery_msg = bot.send_message(
                    chat_id, 
                    items_text, 
                    reply_markup=get_delivery_keyboard(pending_items, user["delivery_arrived"])
                )
                user["delivery_message_id"] = delivery_msg.message_id
            else:
                bot.send_message(chat_id, "Нет отложенных товаров на поставку для этого магазина.")
                user["stage"] = "main"
            return

    bot.send_message(chat_id, "Пожалуйста, выберите магазин из меню.", reply_markup=get_shop_menu(include_back=(user.get("stage") == "choose_shop_order")))

@bot.callback_query_handler(func=lambda call: call.data.startswith('staff_'))
def handle_staff_callback(call):
    chat_id = call.message.chat.id
    user = user_data.get(chat_id)
    if not user or user.get('stage') != 'choose_staff':
        bot.answer_callback_query(call.id)
        return

    staff_name = call.data.replace('staff_', '')
    if staff_name == 'done':
        user['stage'] = 'confirm_report'
        preview_report(chat_id)
        bot.answer_callback_query(call.id)
        return

    selected = user.setdefault('selected_staff', [])
    if staff_name in selected:
        selected.remove(staff_name)
    else:
        selected.append(staff_name)

    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=get_staff_keyboard(selected))
    bot.answer_callback_query(call.id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delivery_'))
def handle_delivery_callback(call):
    chat_id = call.message.chat.id
    user = user_data.get(chat_id)
    if not user or user.get('stage') != 'delivery_buttons':
        bot.answer_callback_query(call.id, "❌ Сессия истекла")
        return

    # Получаем магазин для приемки
    shop = user.get("order_shop")
    if not shop or shop not in shop_data:
        bot.answer_callback_query(call.id, "❌ Ошибка: магазин не выбран")
        return
    
    shop_info = shop_data[shop]

    if call.data == 'delivery_submit':
        # Обработка завершения приёмки
        pending_items = shop_info["pending_delivery"].copy()
        arrived_items = user.get("delivery_arrived", [])
        not_arrived = [item for item in pending_items if item not in arrived_items]
        
        # ОБНОВЛЯЕМ ГЛОБАЛЬНЫЕ ДАННЫЕ МАГАЗИНА
        shop_info["accepted_delivery"].extend(arrived_items)
        shop_info["pending_delivery"] = not_arrived.copy()
        
        # Создание итогового отчёта
        report_lines = [f"📦 <b>Итоговый отчёт по поставке для {shop}:</b>"]
        
        if arrived_items:
            report_lines.append("\n<b>✅ Приехало:</b>")
            for item in arrived_items:
                report_lines.append(f"✅ {item}")
        
        if not_arrived:
            report_lines.append("\n<b>❌ НЕ ПРИЕХАЛО:</b>")
            for item in not_arrived:
                report_lines.append(f"❌ {item}")
            report_lines.append("\n⚠️ <b>Не приехавшие товары будут автоматически добавлены в следующий заказ.</b>")
        else:
            report_lines.append("\n✅ <b>Всё приехало в полном объёме.</b>")
        
        final_report = "\n".join(report_lines)
        bot.send_message(CHAT_ID_FOR_REPORT, final_report, message_thread_id=THREAD_ID_FOR_ORDER)
        
        if not_arrived:
            bot.send_message(chat_id, "❌ Товары, которые не приехали, будут автоматически добавлены в следующий заказ.", reply_markup=get_main_menu())
        else:
            bot.send_message(chat_id, "✅ Поставка принята полностью. Остатков нет.", reply_markup=get_main_menu())
        
        # Очищаем временные данные пользователя
        user["delivery_arrived"] = []
        user["stage"] = "main"
        user["order_shop"] = None
        bot.answer_callback_query(call.id, "✅ Приёмка завершена")
        
        # Удаляем сообщение с кнопками
        try:
            bot.delete_message(chat_id, user.get("delivery_message_id"))
        except:
            pass
        return
    
    if call.data.startswith('delivery_toggle_'):
        # Переключение статуса товара
        item_index = int(call.data.replace('delivery_toggle_', ''))
        pending_items = shop_info["pending_delivery"]
        
        if 0 <= item_index < len(pending_items):
            item = pending_items[item_index]
            arrived_items = user.setdefault("delivery_arrived", [])
            
            if item in arrived_items:
                arrived_items.remove(item)
            else:
                arrived_items.append(item)
            
            # Обновляем клавиатуру
            try:
                bot.edit_message_reply_markup(
                    chat_id, 
                    call.message.message_id, 
                    reply_markup=get_delivery_keyboard(pending_items, arrived_items)
                )
            except:
                pass
        
        bot.answer_callback_query(call.id)

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
            # Load saved order (no automatic pending delivery merge for saved orders)
            saved_items = user["saved_order"]
            
            user["order_items"] = saved_items.copy()
            user["order_is_appended"] = False
            user["original_order_count"] = 0
            user["stage"] = "order_input"
            
            order_text = format_order_list(user["order_items"], show_appended_info=False, original_count=0)
            bot.send_message(chat_id, f"💾 <b>Загружен сохранённый заказ:</b>\n{order_text}\nВы можете продолжить работу с ним.", reply_markup=get_order_action_menu())
        else:
            user["stage"] = "choose_shop_order"
            bot.send_message(chat_id, "Выберите магазин для заказа:", reply_markup=get_shop_menu(include_back=True))
        return

    # Order handling
    if user["stage"] == "order_input":
        if text in ["✅ Отправить заказ", "✏️ Изменить заказ", "💾 Сохранить заказ (не отправлять)", "❌ Отмена"]:
            if text == "✅ Отправить заказ":
                if not user["order_items"]:
                    bot.send_message(chat_id, "⚠️ Заказ пуст, нечего отправлять.")
                    return
                
                # Check if this is an appended order
                is_appended = user.get("order_is_appended", False)
                send_order(chat_id, appended=is_appended)
                
                # Reset order state
                user["saved_order"] = []
                user["order_items"] = []
                user["order_shop"] = None
                user["order_photos"] = []
                user["order_videos"] = []
                user["order_is_appended"] = False
                user["original_order_count"] = 0
                user["stage"] = "main"
                
                success_msg = "✅ Заказ дополнен и отправлен!" if is_appended else "✅ Заказ отправлен!"
                bot.send_message(chat_id, success_msg, reply_markup=get_main_menu())
                return

            if text == "✏️ Изменить заказ":
                if not user["order_items"]:
                    bot.send_message(chat_id, "⚠️ Заказ пуст, нечего изменять.")
                    return
                bot.send_message(chat_id, "✏️ Напишите позиции, которые хотите удалить через запятую или с новой строки.\nЕсли хотите очистить весь заказ — напишите 'удалить всё', 'очистить', 'сбросить'.")
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
                user["order_videos"] = []
                user["order_is_appended"] = False
                user["original_order_count"] = 0
                user["stage"] = "main"
                bot.send_message(chat_id, "💾 Заказ сохранён. Чтобы отправить — зайдите в заказ и нажмите «✅ Отправить заказ»", reply_markup=get_main_menu())
                return

            if text == "❌ Отмена":
                user["order_items"] = []
                user["order_shop"] = None
                user["order_photos"] = []
                user["order_videos"] = []
                user["order_is_appended"] = False
                user["original_order_count"] = 0
                user["stage"] = "main"
                bot.send_message(chat_id, "❌ Действие отменено.", reply_markup=get_main_menu())
                return
        else:
            items = sanitize_input(text)
            if items:
                # Use merge_order function instead of simple addition
                user["order_items"] = merge_order(chat_id, items)
                
                # Show enhanced order information if this is an appended order
                is_appended = user.get("order_is_appended", False)
                original_count = user.get("original_order_count", 0)
                order_text = format_order_list(user["order_items"], show_appended_info=is_appended, original_count=original_count)
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
        order_text = format_order_list(user["order_items"], show_appended_info=user.get("order_is_appended", False), original_count=user.get("original_order_count", 0))
        bot.send_message(chat_id, order_text)
        bot.send_message(chat_id, "Выберите действие:", reply_markup=get_order_action_menu())
        user["stage"] = "order_input"
        return

    if text == "📦 Прием поставки":
        user["stage"] = "choose_shop_delivery"
        bot.send_message(chat_id, "Выберите магазин для приемки поставки:", reply_markup=get_shop_menu())
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

    if text.isdigit():
        amount = int(text)
        stage = user.get("stage", "main")
        if stage == "main" and user.get("shop"):
            user["transfers"].append(amount)
            bot.send_message(chat_id, f"✅ Добавлено: {amount}₽")
            total = sum(user["transfers"])
            bot.send_message(chat_id, f"💰 Текущая сумма: <b>{total}₽</b>", reply_markup=get_main_menu())
            return

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
            user["stage"] = "choose_staff"
            user["selected_staff"] = []
            bot.send_message(chat_id, "Выберите сотрудников, которые были на смене:", reply_markup=get_staff_keyboard())
            return

    if user.get("stage") == "confirm_report":
        if text == "✅ Отправить":
            send_report(chat_id)
            user["transfers"] = []
            user["cash"] = 0
            user["terminal"] = 0
            user["selected_staff"] = []
            user["stage"] = "choose_shop"
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

    bot.send_message(chat_id, "Выберите действие:", reply_markup=get_main_menu())

def preview_report(chat_id):
    data = user_data[chat_id]
    shop = data["shop"]
    transfers = sum(data["transfers"])
    cash = data["cash"]
    terminal = data["terminal"]
    total = transfers + cash + terminal
    date = data["date"]
    staff = data.get("selected_staff", [])

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

    staff_text = "👥 Сотрудники: " + (', '.join(staff) if staff else "не выбраны")

    weather_report = get_weather_report()

    report_text = (
        f"📦 Магазин: {shop}\n"
        f"📅 Дата: {date}\n"
        f"💳 Переводы: {transfers}₽\n"
        f"💵 Наличные: {cash}₽\n"
        f"🏧 Терминал: {terminal}₽\n"
        f"📊 Итого: {total}₽\n"
        f"{salary_text}\n"
        f"{staff_text}\n"
        f"{weather_report}"
    )

    bot.send_message(chat_id, report_text, reply_markup=get_confirm_menu())

def send_report(chat_id):
    data = user_data[chat_id]
    shop = data["shop"]
    transfers = sum(data["transfers"])
    cash = data["cash"]
    terminal = data["terminal"]
    date = data["date"]
    staff = ', '.join(data.get("selected_staff", []))
    weather_report = get_weather_report()

    report_text = (
        f"📦 Магазин: {shop}\n"
        f"📅 Дата: {date}\n"
        f"💳 Переводы: {transfers}₽\n"
        f"💵 Наличные: {cash}₽\n"
        f"🏧 Терминал: {terminal}₽\n"
        f"📊 Итого: {transfers + cash + terminal}₽\n"
        f"👥 Сотрудники: {staff if staff else 'не выбраны'}\n"
        f"{weather_report}"
    )

    sheet.append_row([date, shop, transfers, cash, terminal, staff, weather_report])
    bot.send_message(CHAT_ID_FOR_REPORT, report_text, message_thread_id=THREAD_ID_FOR_REPORT)

def send_order(chat_id, appended=False):
    user = user_data[chat_id]
    shop = user.get("order_shop", "Не указан")
    items = user.get("order_items", [])
    photos = user.get("order_photos", [])
    videos = user.get("order_videos", [])

    if not items:
        bot.send_message(chat_id, "⚠️ Заказ пуст, нечего отправлять.")
        return

    # При автоматическом объединении заказов удаляем предыдущее сообщение заказа
    if appended and shop in shop_order_messages:
        try:
            old_message_data = shop_order_messages[shop]
            bot.delete_message(CHAT_ID_FOR_REPORT, old_message_data["message_id"])
        except Exception as e:
            print(f"Ошибка удаления старого сообщения заказа: {e}")

    order_text = f"🛒 Заказ для магазина: <b>{shop}</b>\n"
    if appended:
        original_count = user.get("original_order_count", 0)
        new_items_count = len(items) - original_count
        order_text += f"<b>✅ Заказ автоматически объединён!</b> Добавлено позиций: {new_items_count}\n"
    order_text += "\n" + "\n".join(f"• {item}" for item in items)
    
    # Отправляем основное сообщение с заказом
    order_message = bot.send_message(CHAT_ID_FOR_REPORT, order_text, message_thread_id=THREAD_ID_FOR_ORDER)
    
    # Отправляем медиа-файлы только один раз (не сохраняем для переиспользования)
    for photo in photos:
        try:
            bot.send_photo(CHAT_ID_FOR_REPORT, photo["file_id"], caption=photo.get("caption", ""), message_thread_id=THREAD_ID_FOR_ORDER)
        except Exception as e:
            print(f"Ошибка отправки фото: {e}")

    for video in videos:
        try:
            bot.send_video(CHAT_ID_FOR_REPORT, video["file_id"], caption=video.get("caption", ""), message_thread_id=THREAD_ID_FOR_ORDER)
        except Exception as e:
            print(f"Ошибка отправки видео: {e}")

    # Сохраняем только message_id для возможного удаления при объединении заказов
    # НЕ сохраняем медиа-файлы для переиспользования
    shop_order_messages[shop] = {
        "message_id": order_message.message_id
    }

    # СОХРАНЯЕМ ЗАКАЗ В ГЛОБАЛЬНЫХ ДАННЫХ МАГАЗИНА
    shop_data[shop]["last_order"] = items.copy()
    
    # ВАЖНО: Обновляем pending_delivery только новыми позициями
    # Исключаем уже принятые товары из pending_delivery
    accepted_items = shop_data[shop]["accepted_delivery"]
    new_pending_items = [item for item in items if item not in accepted_items]
    shop_data[shop]["pending_delivery"] = new_pending_items

print("✅ Бот запущен...")
bot.infinity_polling()
