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

# === СТАТИСТИКА ПОПУЛЯРНЫХ ТОВАРОВ ===
# Хранилище статистики заказанных товаров {item_name: [timestamps]}
item_statistics = {}

# === СПИСОК СОТРУДНИКОВ ===
STAFF_LIST = ["Данил", "Даниз", "Даша", "Соня", "Оксана", "Лиза"]

# === СПИСОК ПРОДАВЦОВ ===
SELLER_LIST = ["Данил", "Даниз", "Даша", "Соня", "Оксана", "Лиза"]

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

def get_weather_condition_emoji(weather_main, weather_desc):
    """Get weather emoji based on weather condition"""
    weather_main_lower = weather_main.lower()
    weather_desc_lower = weather_desc.lower()
    
    if "rain" in weather_main_lower or "дождь" in weather_desc_lower:
        return "🌧️ Дождь"
    elif "cloud" in weather_main_lower or "облач" in weather_desc_lower or "пасмурн" in weather_desc_lower:
        return "🌥️ Пасмурно"
    elif "clear" in weather_main_lower or "ясн" in weather_desc_lower:
        return "☀️ Ясно"
    elif "snow" in weather_main_lower or "снег" in weather_desc_lower:
        return "❄️ Снег"
    elif "fog" in weather_main_lower or "mist" in weather_main_lower or "туман" in weather_desc_lower:
        return "🌫️ Туман"
    else:
        return f"🌤️ {weather_desc.capitalize()}"

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
    
    # Get weather condition with emoji from the latest entry
    latest_entry = today_log[-1]
    weather_condition = get_weather_condition_emoji(latest_entry["weather"], latest_entry["weather_desc"])
    
    report = (
        f"<b>Погодный отчёт за сегодня:</b>\n"
        f"{weather_condition}\n"
        f"Пиковая температура: <b>{max_temp}°C</b>\n"
    )
    
    # Only show rain information if there was rain
    if rain_total > 0:
        rain_was = "да"
        report += (
            f"Дождь был: <b>{rain_was}</b>\n"
            f"Дождь (время): <b>{rain_hours:.2f} ч</b>, всего выпало <b>{rain_total:.2f} мм</b>\n"
        )
    
    report += f"Средний ветер: <b>{avg_wind} м/с</b>"
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
    markup.add("✅ Отправить заказ", "🗑 Удалить из заказа")
    markup.add("⭐ Популярные товары", "💾 Сохранить заказ (не отправлять)")
    markup.add("❌ Отмена")
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

def get_seller_keyboard(selected_sellers=None):
    selected_sellers = selected_sellers or []
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    for seller in SELLER_LIST:
        text = f"✅ {seller}" if seller in selected_sellers else seller
        callback_data = f"seller_{seller}"
        buttons.append(types.InlineKeyboardButton(text, callback_data=callback_data))
    markup.add(*buttons)
    markup.add(types.InlineKeyboardButton("✅ Отправить заказ", callback_data="sellers_done"))
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

def get_order_removal_keyboard(order_items, selected_for_removal=None):
    """Создать инлайн-клавиатуру для удаления позиций из заказа"""
    selected_for_removal = selected_for_removal or []
    markup = types.InlineKeyboardMarkup(row_width=1)
    
    for i, item in enumerate(order_items):
        status = "🗑" if item in selected_for_removal else "📦"
        text = f"{status} {item}"
        callback_data = f"remove_toggle_{i}"
        markup.add(types.InlineKeyboardButton(text, callback_data=callback_data))
    
    # Кнопки управления
    control_row = []
    control_row.append(types.InlineKeyboardButton("✅ Принять", callback_data="remove_accept"))
    control_row.append(types.InlineKeyboardButton("🗑 Удалить все", callback_data="remove_all"))
    markup.add(*control_row)
    markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="remove_back"))
    
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

def is_photo_related_item(item):
    """Check if item contains photo-related keywords that should not go to delivery"""
    item_lower = item.lower().strip()
    photo_keywords = ["фото", "прикрепил фото", "видео", "картинка", "изображение", "снимок"]
    return any(keyword in item_lower for keyword in photo_keywords)

def filter_photo_items(items):
    """Filter out photo-related items from list"""
    return [item for item in items if not is_photo_related_item(item)]

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

def format_order_with_attention(all_order_items, carried_items):
    """
    Форматирует заказ с выделением перенесённых позиций.
    
    Args:
        all_order_items: Полный список позиций заказа
        carried_items: Список перенесённых позиций из прошлого заказа
    
    Returns:
        str: Форматированный текст заказа
    """
    if not all_order_items:
        return "📋 Заказ пуст."
    
    # Разделяем позиции на перенесённые и новые
    carried_set = set(carried_items) if carried_items else set()
    
    carried_order_items = []
    new_order_items = []
    
    for item in all_order_items:
        if item in carried_set:
            carried_order_items.append(item)
        else:
            new_order_items.append(item)
    
    # Сортируем обе группы по алфавиту
    carried_order_items.sort()
    new_order_items.sort()
    
    # Формируем результат
    result = "📦 Заказ:\n"
    counter = 1
    
    # Сначала перенесённые позиции с красным восклицательным смайликом
    for item in carried_order_items:
        result += f"{counter}. 🔴❗ {item}\n"
        counter += 1
    
    # Затем новые позиции с обычной маркировкой
    for item in new_order_items:
        result += f"{counter}. {item}\n"
        counter += 1
    
    return result

def round_to_50(value):
    remainder = value % 50
    if remainder < 25:
        return int(value - remainder)
    else:
        return int(value + (50 - remainder))

def track_order_item(item):
    """Добавить товар в статистику заказов"""
    current_time = datetime.now().isoformat()
    item_clean = item.strip().lower()
    if item_clean not in item_statistics:
        item_statistics[item_clean] = []
    item_statistics[item_clean].append(current_time)

def get_popular_items(limit=15):
    """Получить топ популярных товаров за последнюю неделю"""
    from datetime import timedelta
    
    week_ago = datetime.now() - timedelta(days=7)
    popular_items = {}
    
    for item, timestamps in item_statistics.items():
        # Считаем только заказы за последнюю неделю
        recent_orders = [
            t for t in timestamps 
            if datetime.fromisoformat(t) >= week_ago
        ]
        if recent_orders:
            popular_items[item] = len(recent_orders)
    
    # Сортируем по популярности и берем топ-15
    sorted_items = sorted(popular_items.items(), key=lambda x: x[1], reverse=True)
    return [item[0] for item in sorted_items[:limit]]

def get_popular_items_keyboard():
    """Создать инлайн-клавиатуру с популярными товарами"""
    popular_items = get_popular_items()
    if not popular_items:
        return None
    
    markup = types.InlineKeyboardMarkup(row_width=2)
    buttons = []
    
    for i, item in enumerate(popular_items):
        # Ограничиваем длину текста кнопки для лучшего отображения
        button_text = item[:25] + "..." if len(item) > 25 else item
        callback_data = f"popular_{i}"
        buttons.append(types.InlineKeyboardButton(button_text, callback_data=callback_data))
    
    # Добавляем кнопки по 2 в ряд
    for i in range(0, len(buttons), 2):
        if i + 1 < len(buttons):
            markup.add(buttons[i], buttons[i + 1])
        else:
            markup.add(buttons[i])
    
    markup.add(types.InlineKeyboardButton("➡️ Пропустить", callback_data="popular_skip"))
    return markup, popular_items

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
        "selected_sellers": [],  # Выбранные продавцы для заказа
        "order_is_appended": False,  # Флаг объединения заказа (временный)
        "original_order_count": 0,  # Количество позиций до объединения (временно)
        "saved_order": [],  # Локально сохраненный заказ пользователя
        "selected_for_removal": [],  # Позиции выбранные для удаления
        "popular_items_list": [],  # Список популярных товаров для текущей сессии
        "temp_shop": None  # Временное хранилище магазина для популярных товаров после отправки заказа
    }
    bot.send_message(chat_id, "Привет! Выберите магазин для переводов:", reply_markup=get_shop_menu())

@bot.message_handler(func=lambda m: m.text in ["Янтарь", "Хайп", "Полка", "⬅️ Назад"])
def choose_shop(message):
    chat_id = message.chat.id
    user = user_data.get(chat_id)
    # Кнопка Назад для заказа и поставки
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
            "selected_sellers": [],
            "order_is_appended": False,
            "original_order_count": 0,
            "saved_order": [],
            "selected_for_removal": [],
            "popular_items_list": [],
            "temp_shop": None
        })
        bot.send_message(chat_id, f"Выбран магазин: <b>{message.text}</b>", reply_markup=get_main_menu())
        return

    if user.get("stage") == "choose_shop_order":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if message.text in allowed_shops:
            user["order_shop"] = message.text
            shop = message.text
            
            # Clear any previous order session state to avoid conflicts
            user["order_photos"] = []
            user["order_videos"] = []
            user["delivery_arrived"] = []
            user["delivery_message_id"] = None
            
            # Step 1: Start with pending delivery items (leftovers from previous deliveries)
            # ИСПОЛЬЗУЕМ ГЛОБАЛЬНЫЕ ДАННЫЕ МАГАЗИНА, НО ИСКЛЮЧАЕМ ФОТО-ПОЗИЦИИ
            shop_info = shop_data[shop]
            all_leftovers = shop_info["pending_delivery"].copy()
            # Filter out photo-related items from leftovers as they shouldn't be in pending_delivery anyway
            leftovers = filter_photo_items(all_leftovers) if all_leftovers else []
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
            total_combined = len(combined_items)
            
            # Step 5: Set up order state
            user["order_items"] = combined_items
            user["order_is_appended"] = len(combined_items) > 0
            user["original_order_count"] = len(combined_items)
            user["stage"] = "order_input"
            
            # Step 6: Create one consolidated message with all information
            consolidated_msg = f"🛒 Выбран магазин для заказа: «{shop}»\n"
            
            # Step 6: Add order information if there are existing items
            if leftovers or filtered_existing_items:
                consolidated_msg += "ℹ️ Информация о заказе:\n"
                consolidated_msg += "С прошлого заказа не приехали следующие позиции:\n"
                
                # List all carried over items as bullet points
                for item in combined_items:
                    consolidated_msg += f"- {item}\n"
                
                consolidated_msg += "\n"
            
            # Add information guide
            consolidated_msg += (
                "📖 Информационная справка:\n"
                "• Пишите позиции заказа через запятую или с новой строки (можно отдельными сообщениями)\n"
                "• Чтобы добавить фото — сначала текст, потом фото, потом отправка заказа\n"
                "• Фото/видео для уточнения НЕ попадут в приёмку поставки"
            )
            
            # Send the consolidated message
            bot.send_message(chat_id, consolidated_msg, reply_markup=get_order_action_menu())
            return

    if user.get("stage") == "choose_shop_order_with_saved":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if message.text in allowed_shops:
            user["order_shop"] = message.text
            shop = message.text
            
            # Clear any previous order session state to avoid conflicts
            user["order_photos"] = []
            user["order_videos"] = []
            user["delivery_arrived"] = []
            user["delivery_message_id"] = None
            
            # Step 1: Start with saved order items
            saved_items = user.get("saved_order", [])
            combined_items = saved_items.copy() if saved_items else []
            
            # Step 2: Add pending delivery items for this shop
            shop_info = shop_data[shop]
            all_leftovers = shop_info["pending_delivery"].copy()
            leftovers = filter_photo_items(all_leftovers) if all_leftovers else []
            if leftovers:
                combined_items.extend(leftovers)
            
            # Step 3: Add last order items (excluding already accepted)
            existing_order_items = shop_info["last_order"].copy()
            accepted_items = shop_info["accepted_delivery"]
            filtered_existing_items = [item for item in existing_order_items if item not in accepted_items]
            if filtered_existing_items:
                combined_items.extend(filtered_existing_items)
            
            # Step 4: Remove duplicates from combined items
            combined_items = deduplicate_order_items(combined_items)
            
            # Step 5: Set up order state
            user["order_items"] = combined_items
            user["order_is_appended"] = len(combined_items) > len(saved_items)
            user["original_order_count"] = len(combined_items)
            
            # Step 5: Set up order state
            user["order_items"] = combined_items
            user["order_is_appended"] = len(combined_items) > len(saved_items)
            user["original_order_count"] = len(combined_items)
            user["stage"] = "order_input"
            
            # Step 6: Create consolidated message
            consolidated_msg = f"🛒 Выбран магазин для заказа: «{shop}»\n"
            
            if saved_items:
                consolidated_msg += f"💾 Загружено из сохранённого заказа: {len(saved_items)} позиций\n"
            
            if leftovers or filtered_existing_items:
                auto_added = len(combined_items) - len(saved_items)
                if auto_added > 0:
                    consolidated_msg += f"➕ Автоматически добавлено неприехавших позиций: {auto_added}\n"
                consolidated_msg += "\nВсе позиции в заказе:\n"
                for item in combined_items:
                    consolidated_msg += f"- {item}\n"
                consolidated_msg += "\n"
            
            # Add information guide
            consolidated_msg += (
                "📖 Информационная справка:\n"
                "• Пишите позиции заказа через запятую или с новой строки (можно отдельными сообщениями)\n"
                "• Чтобы добавить фото — сначала текст, потом фото, потом отправка заказа\n"
                "• Фото/видео для уточнения НЕ попадут в приёмку поставки"
            )
            
            # Clear saved order since it's now loaded
            user["saved_order"] = []
            
            # Send the consolidated message
            bot.send_message(chat_id, consolidated_msg, reply_markup=get_order_action_menu())
            return

    if user.get("stage") == "choose_shop_delivery":
        allowed_shops = ["Янтарь", "Хайп", "Полка"]
        if message.text in allowed_shops:
            user["order_shop"] = message.text
            shop = message.text
            
            # Clear any previous delivery session state
            user["delivery_arrived"] = []
            user["delivery_message_id"] = None
            
            # ИСПОЛЬЗУЕМ ГЛОБАЛЬНЫЕ ДАННЫЕ МАГАЗИНА ДЛЯ ПРИЕМКИ
            shop_info = shop_data[shop]
            pending_items = shop_info["pending_delivery"].copy()
            
            if pending_items:
                # Новый интерфейс с инлайн-кнопками
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
                bot.send_message(chat_id, f"📦 <b>Магазин {shop} выбран для приёмки поставки.</b>\n\nНет отложенных товаров на поставку для этого магазина.", reply_markup=get_main_menu())
                user["stage"] = "main"
            return

    # Handle invalid shop selection based on current stage
    current_stage = user.get("stage")
    if current_stage == "choose_shop_order":
        bot.send_message(chat_id, "Пожалуйста, выберите магазин из меню.", reply_markup=get_shop_menu(include_back=True))
    elif current_stage == "choose_shop_order_with_saved":
        bot.send_message(chat_id, "Пожалуйста, выберите магазин из меню.", reply_markup=get_shop_menu(include_back=True))
    elif current_stage == "choose_shop_delivery":
        bot.send_message(chat_id, "Пожалуйста, выберите магазин из меню.", reply_markup=get_shop_menu(include_back=True))
    else:
        bot.send_message(chat_id, "Пожалуйста, выберите магазин из меню.", reply_markup=get_shop_menu())

@bot.callback_query_handler(func=lambda call: call.data.startswith('popular_'))
def handle_popular_items_callback(call):
    chat_id = call.message.chat.id
    user = user_data.get(chat_id)
    current_stage = user.get('stage') if user else None
    
    if not user or current_stage not in ['popular_items', 'popular_after_order']:
        bot.answer_callback_query(call.id, "❌ Сессия истекла")
        return

    if call.data == 'popular_skip':
        if current_stage == 'popular_after_order':
            # Пропустить популярные товары после отправки заказа - вернуться в главное меню
            user['stage'] = 'main'
            user['temp_shop'] = None
            bot.edit_message_text(
                "➡️ Популярные товары пропущены. Возвращаемся в главное меню.",
                chat_id, 
                call.message.message_id
            )
            bot.answer_callback_query(call.id)
            return
        else:
            # Обычная логика для popular_items
            user['stage'] = 'order_input'
            bot.edit_message_text(
                "➡️ Популярные товары пропущены. Продолжайте вводить позиции заказа или используйте кнопки действий:",
                chat_id, 
                call.message.message_id
            )
            bot.send_message(chat_id, 
                "📖 Информационная справка:\n"
                "• Пишите позиции заказа через запятую или с новой строки (можно отдельными сообщениями)\n"
                "• Чтобы добавить фото — сначала текст, потом фото, потом отправка заказа\n"
                "• Фото/видео для уточнения НЕ попадут в приёмку поставки",
                reply_markup=get_order_action_menu()
            )
            bot.answer_callback_query(call.id)
            return
    
    if call.data.startswith('popular_'):
        try:
            item_index = int(call.data.replace('popular_', ''))
            popular_items = user.get('popular_items_list', [])
            
            if 0 <= item_index < len(popular_items):
                selected_item = popular_items[item_index]
                
                if current_stage == 'popular_after_order':
                    # Быстрое создание нового заказа после отправки предыдущего
                    user.setdefault('order_items', []).append(selected_item)
                    user['order_shop'] = user.get('temp_shop')  # Используем сохраненный магазин
                    user['stage'] = 'order_input'
                    user['temp_shop'] = None  # Очищаем временный магазин
                    
                    bot.answer_callback_query(call.id, f"✅ Создан новый заказ с товаром: {selected_item}")
                    
                    order_text = format_order_list(user['order_items'])
                    bot.edit_message_text(
                        f"🆕 Создан новый заказ для магазина «{user['order_shop']}»!\n\n"
                        f"{order_text}\n\n"
                        f"Продолжайте добавлять товары или отправляйте заказ:",
                        chat_id,
                        call.message.message_id
                    )
                    
                    # Показываем меню действий с заказом
                    bot.send_message(chat_id, "Выберите действие:", reply_markup=get_order_action_menu())
                    return
                    
                else:
                    # Обычная логика добавления товара в существующий заказ
                    if selected_item not in user.get('order_items', []):
                        user.setdefault('order_items', []).append(selected_item)
                        
                        bot.answer_callback_query(call.id, f"✅ Добавлено: {selected_item}")
                        
                        # Обновляем сообщение с информацией о добавлении
                        order_text = format_order_list(user['order_items'])
                        bot.edit_message_text(
                            f"✅ Товар «{selected_item}» добавлен в заказ!\n\n{order_text}\n\n"
                            "Выберите еще товары или пропустите и переходите к действиям с заказом:",
                            chat_id,
                            call.message.message_id,
                            reply_markup=call.message.reply_markup
                        )
                    else:
                        bot.answer_callback_query(call.id, f"⚠️ {selected_item} уже в заказе")
                    
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "❌ Ошибка выбора товара")

@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_'))
def handle_order_removal_callback(call):
    chat_id = call.message.chat.id
    user = user_data.get(chat_id)
    if not user or user.get('stage') != 'order_removal':
        bot.answer_callback_query(call.id, "❌ Сессия истекла")
        return

    order_items = user.get('order_items', [])
    selected_for_removal = user.get('selected_for_removal', [])

    if call.data == 'remove_accept':
        # Принять изменения - удалить выбранные товары
        remaining_items = [item for item in order_items if item not in selected_for_removal]
        user['order_items'] = remaining_items
        user['selected_for_removal'] = []
        user['stage'] = 'order_input'
        
        removed_count = len(order_items) - len(remaining_items)
        if removed_count > 0:
            success_msg = f"✅ Удалено позиций: {removed_count}\n\n"
        else:
            success_msg = "ℹ️ Позиции для удаления не были выбраны.\n\n"
            
        order_text = format_order_list(remaining_items)
        bot.edit_message_text(
            success_msg + order_text,
            chat_id,
            call.message.message_id
        )
        bot.send_message(chat_id, "Выберите действие:", reply_markup=get_order_action_menu())
        bot.answer_callback_query(call.id, "✅ Изменения приняты")
        return

    elif call.data == 'remove_all':
        # Удалить все товары из заказа
        user['order_items'] = []
        user['selected_for_removal'] = []
        user['stage'] = 'order_input'
        
        bot.edit_message_text(
            "🗑️ Заказ полностью очищен.\n\n📋 Заказ пуст.",
            chat_id,
            call.message.message_id
        )
        bot.send_message(chat_id, "Выберите действие:", reply_markup=get_order_action_menu())
        bot.answer_callback_query(call.id, "🗑️ Заказ очищен")
        return

    elif call.data == 'remove_back':
        # Назад без изменений
        user['selected_for_removal'] = []
        user['stage'] = 'order_input'
        
        order_text = format_order_list(order_items)
        bot.edit_message_text(
            f"⬅️ Возврат без изменений.\n\n{order_text}",
            chat_id,
            call.message.message_id
        )
        bot.send_message(chat_id, "Выберите действие:", reply_markup=get_order_action_menu())
        bot.answer_callback_query(call.id, "⬅️ Возврат")
        return

    elif call.data.startswith('remove_toggle_'):
        # Переключить выбор товара для удаления
        try:
            item_index = int(call.data.replace('remove_toggle_', ''))
            if 0 <= item_index < len(order_items):
                item = order_items[item_index]
                
                if item in selected_for_removal:
                    selected_for_removal.remove(item)
                else:
                    selected_for_removal.append(item)
                
                user['selected_for_removal'] = selected_for_removal
                
                # Обновляем клавиатуру
                new_markup = get_order_removal_keyboard(order_items, selected_for_removal)
                
                # Обновляем текст сообщения
                selected_count = len(selected_for_removal)
                message_text = (
                    f"🗑 Удаление из заказа\n\n"
                    f"Выбрано для удаления: {selected_count} позиций\n"
                    f"📦 = оставить, 🗑 = удалить\n\n"
                    f"Нажмите на позиции, которые хотите удалить:"
                )
                
                bot.edit_message_text(
                    message_text,
                    chat_id,
                    call.message.message_id,
                    reply_markup=new_markup
                )
                
        except (ValueError, IndexError):
            bot.answer_callback_query(call.id, "❌ Ошибка")
            return
        
        bot.answer_callback_query(call.id)
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

@bot.callback_query_handler(func=lambda call: call.data.startswith('seller_'))
def handle_seller_callback(call):
    chat_id = call.message.chat.id
    user = user_data.get(chat_id)
    if not user or user.get('stage') != 'choose_sellers':
        bot.answer_callback_query(call.id, "❌ Сессия истекла")
        return

    seller_name = call.data.replace('seller_', '')
    if seller_name == 'done':
        # Actually send the order now
        try:
            bot.set_message_reaction(chat_id, call.message.message_id, [types.ReactionTypeEmoji("✅")])
        except Exception as e:
            print(f"Не удалось добавить реакцию: {e}")
        
        # Мгновенная обратная связь - подтверждение принятия заказа
        is_appended = user.get("order_is_appended", False)
        shop_for_popular = user["order_shop"]
        order_count = len(user["order_items"])
        selected_sellers = user.get("selected_sellers", [])
        
        instant_confirmation = (
            f"✅ **Заказ принят!**\n\n"
            f"🏪 Магазин: **{shop_for_popular}**\n"
            f"📦 Позиций в заказе: **{order_count}**\n"
            f"👥 Продавцы: **{', '.join(selected_sellers) if selected_sellers else 'не выбраны'}**\n"
            f"🚀 Заказ {'дополнен и ' if is_appended else ''}отправляется..."
        )
        bot.edit_message_text(instant_confirmation, chat_id, call.message.message_id, parse_mode='Markdown')
        
        # Трекинг популярности товаров при отправке заказа
        for item in user["order_items"]:
            track_order_item(item)
        
        # Отправляем заказ в группу
        send_order(chat_id, appended=is_appended)
        
        # Reset order state
        user["saved_order"] = []
        user["order_items"] = []
        user["order_shop"] = None
        user["order_photos"] = []
        user["order_videos"] = []
        user["order_is_appended"] = False
        user["original_order_count"] = 0
        user["selected_sellers"] = []
        user["stage"] = "main"
        
        success_msg = "✅ Заказ успешно отправлен в группу!" if is_appended else "✅ Заказ успешно отправлен!"
        bot.send_message(chat_id, success_msg, reply_markup=get_main_menu())
        
        bot.answer_callback_query(call.id, "✅ Заказ отправлен!")
        return

    selected = user.setdefault('selected_sellers', [])
    if seller_name in selected:
        selected.remove(seller_name)
    else:
        selected.append(seller_name)

    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=get_seller_keyboard(selected))
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
        try:
            shop_info["accepted_delivery"].extend(arrived_items)
            shop_info["pending_delivery"] = not_arrived.copy()
        except Exception as e:
            bot.answer_callback_query(call.id, "❌ Ошибка обновления данных")
            logging.error(f"Ошибка обновления данных магазина {shop}: {e}")
            return
        
        # Create final report with enhanced notifications
        report_lines = [f"📦 <b>Итоговый отчёт по поставке для {shop}:</b>"]
        
        # Add delivery summary statistics
        total_items = len(pending_items)
        arrived_count = len(arrived_items)
        not_arrived_count = len(not_arrived)
        report_lines.append(f"📊 <b>Статистика:</b> {arrived_count}/{total_items} позиций приехало ({round(arrived_count/total_items*100) if total_items > 0 else 0}%)")
        
        if arrived_items:
            report_lines.append("\n<b>✅ Приехало:</b>")
            for item in arrived_items:
                report_lines.append(f"✅ {item}")
        
        if not_arrived:
            report_lines.append("\n<b>❌ НЕ ПРИЕХАЛО:</b>")
            for item in not_arrived:
                report_lines.append(f"❌ {item}")
            report_lines.append("\n⚠️ <b>Не приехавшие товары будут автоматически добавлены в следующий заказ.</b>")
            
            # Send additional notification for incomplete deliveries
            if not_arrived_count > total_items * 0.3:  # If more than 30% didn't arrive
                report_lines.append(f"\n🚨 <b>ВНИМАНИЕ:</b> Большое количество товаров не приехало ({not_arrived_count} из {total_items})")
        else:
            report_lines.append("\n✅ <b>Всё приехало в полном объёме.</b>")
        
        final_report = "\n".join(report_lines)
        bot.send_message(CHAT_ID_FOR_REPORT, final_report, message_thread_id=THREAD_ID_FOR_ORDER)
        
        # Delete old order message after delivery acceptance is completed
        if shop in shop_order_messages:
            try:
                old_message_data = shop_order_messages[shop]
                bot.delete_message(CHAT_ID_FOR_REPORT, old_message_data["message_id"])
                del shop_order_messages[shop]  # Remove from tracking
            except Exception as e:
                print(f"Ошибка удаления старого сообщения заказа после приемки: {e}")
        
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
            # Load saved order, but still allow user to choose shop for potential auto-fill merge
            user["stage"] = "choose_shop_order_with_saved"
            saved_items = user["saved_order"]
            saved_text = ", ".join(saved_items)
            bot.send_message(chat_id, f"💾 У вас есть сохранённый заказ: {saved_text}\n\nВыберите магазин для заказа (сохранённый заказ будет объединён с неприехавшими товарами):", reply_markup=get_shop_menu(include_back=True))
        else:
            user["stage"] = "choose_shop_order"
            bot.send_message(chat_id, "Выберите магазин для заказа:", reply_markup=get_shop_menu(include_back=True))
        return

    # Order handling
    if user["stage"] == "order_input":
        if text in ["✅ Отправить заказ", "🗑 Удалить из заказа", "⭐ Популярные товары", "💾 Сохранить заказ (не отправлять)", "❌ Отмена"]:
            if text == "✅ Отправить заказ":
                if not user["order_items"]:
                    bot.send_message(chat_id, "⚠️ Заказ пуст, нечего отправлять.")
                    return
                
                # Отправляем заказ сразу без выбора продавцов
                is_appended = user.get("order_is_appended", False)
                shop_for_popular = user["order_shop"]
                order_count = len(user["order_items"])
                
                # Мгновенная обратная связь - подтверждение принятия заказа
                instant_confirmation = (
                    f"✅ **Заказ принят!**\n\n"
                    f"🏪 Магазин: **{shop_for_popular}**\n"
                    f"📦 Позиций в заказе: **{order_count}**\n"
                    f"👥 Продавцы: **не выбраны**\n"
                    f"🚀 Заказ {'дополнен и ' if is_appended else ''}отправляется..."
                )
                confirmation_msg = bot.send_message(chat_id, instant_confirmation, parse_mode='Markdown')
                
                # Трекинг популярности товаров при отправке заказа
                for item in user["order_items"]:
                    track_order_item(item)
                
                # Отправляем заказ в группу
                send_order(chat_id, appended=is_appended)
                
                # Reset order state
                user["saved_order"] = []
                user["order_items"] = []
                user["order_shop"] = None
                user["order_photos"] = []
                user["order_videos"] = []
                user["order_is_appended"] = False
                user["original_order_count"] = 0
                user["selected_sellers"] = []
                user["stage"] = "main"
                
                success_msg = "✅ Заказ успешно отправлен в группу!" if is_appended else "✅ Заказ успешно отправлен!"
                bot.send_message(chat_id, success_msg, reply_markup=get_main_menu())
                return

            elif text == "⭐ Популярные товары":
                # Show popular items when explicitly requested
                popular_keyboard_data = get_popular_items_keyboard()
                if popular_keyboard_data:
                    markup, popular_items = popular_keyboard_data
                    user["popular_items_list"] = popular_items
                    user["stage"] = "popular_items"
                    
                    popular_msg = (
                        f"⭐ Топ-15 популярных позиций за неделю:\n"
                        f"Выберите товары для быстрого добавления в заказ:"
                    )
                    
                    bot.send_message(chat_id, popular_msg, reply_markup=markup)
                else:
                    bot.send_message(chat_id, "📊 Пока нет статистики по популярным товарам. После нескольких заказов здесь будут отображаться наиболее часто заказываемые позиции.", reply_markup=get_order_action_menu())
                return

            elif text == "🗑 Удалить из заказа":
                if not user["order_items"]:
                    bot.send_message(chat_id, "⚠️ Заказ пуст, нечего удалять.")
                    return
                
                # Переход в режим интерактивного удаления
                user["stage"] = "order_removal"
                user["selected_for_removal"] = []
                
                removal_msg = (
                    f"🗑 Удаление из заказа\n\n"
                    f"Выбрано для удаления: 0 позиций\n"
                    f"📦 = оставить, 🗑 = удалить\n\n"
                    f"Нажмите на позиции, которые хотите удалить:"
                )
                
                removal_keyboard = get_order_removal_keyboard(user["order_items"])
                bot.send_message(chat_id, removal_msg, reply_markup=removal_keyboard)
                return

            elif text == "💾 Сохранить заказ (не отправлять)":
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
                user["selected_sellers"] = []
                user["stage"] = "main"
                bot.send_message(chat_id, "💾 Заказ сохранён. Чтобы отправить — зайдите в заказ и нажмите «✅ Отправить заказ»", reply_markup=get_main_menu())
                return

            elif text == "❌ Отмена":
                user["order_items"] = []
                user["order_shop"] = None
                user["order_photos"] = []
                user["order_videos"] = []
                user["order_is_appended"] = False
                user["original_order_count"] = 0
                user["selected_sellers"] = []
                user["stage"] = "main"
                bot.send_message(chat_id, "❌ Действие отменено.", reply_markup=get_main_menu())
                return
        else:
            # Handle text input as order items
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

    # Обработка ввода товаров когда пользователь находится в стадии популярных товаров  
    if user["stage"] == "popular_items":
        # Если пользователь ввел текст во время выбора популярных товаров,
        # переходим к обычному вводу заказа
        items = sanitize_input(text)
        if items:
            user["order_items"].extend(items)
            user["order_items"] = deduplicate_order_items(user["order_items"])
            user["stage"] = "order_input"
            
            order_text = format_order_list(user["order_items"])
            bot.send_message(chat_id, f"✅ Товары добавлены к заказу!\n\n{order_text}")
            bot.send_message(chat_id, "Выберите действие:", reply_markup=get_order_action_menu())
        return

    if text == "📦 Прием поставки":
        user["stage"] = "choose_shop_delivery"
        bot.send_message(chat_id, "Выберите магазин для приемки поставки:", reply_markup=get_shop_menu(include_back=True))
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

    # Создаем новый структурированный формат сообщения заказа
    order_text = f"🛒 Заказ для магазина: <b>{shop}</b>\n"
    
    # Информация о выбранных продавцах
    selected_sellers = user.get("selected_sellers", [])
    if selected_sellers:
        order_text += f"👥 Продавцы: <b>{', '.join(selected_sellers)}</b>\n"
    else:
        order_text += f"👥 Продавцы: <b>не выбраны</b>\n"
    
    # Информация о переносе позиций
    if appended:
        original_count = user.get("original_order_count", 0)
        new_items_count = len(items) - original_count
        order_text += f"➕ Перенесено из прошлого заказа: {original_count} позиций\n"
        if new_items_count > 0:
            order_text += f"🆕 Добавлено новых позиций: {new_items_count}\n"
    
    # Получаем перенесённые позиции для данного магазина
    carried_items = shop_data.get(shop, {}).get("pending_delivery", [])
    
    # Используем новую функцию форматирования заказа с выделением перенесённых позиций
    formatted_order = format_order_with_attention(items, carried_items)
    order_text += formatted_order
    
    # Определяем какие позиции имеют фото/видео для уточнения и добавляем пометки
    items_with_media = set()
    for photo in photos:
        # Ищем позиции, которые могут быть связаны с этим фото
        for item in items:
            if "фото" in item.lower():
                items_with_media.add(item)
    for video in videos:
        # Ищем позиции, которые могут быть связаны с этим видео
        for item in items:
            if "фото" in item.lower() or "видео" in item.lower():
                items_with_media.add(item)
    
    # Если есть медиа-позиции, добавляем информацию о них
    if items_with_media:
        order_text += "\n📸 Позиции с медиа для уточнения:\n"
        for item in items_with_media:
            order_text += f"• {item}\n"
    
    # Добавляем информацию о вложениях, если есть медиа
    if photos or videos:
        media_count = len(photos) + len(videos)
        order_text += f"\n📎 Вложения: {media_count} файл(ов) одним альбомом"
    
    # Отправляем основное сообщение с заказом
    order_message = bot.send_message(CHAT_ID_FOR_REPORT, order_text, message_thread_id=THREAD_ID_FOR_ORDER)
    
    # Отправляем все медиа-файлы альбомами, если они есть
    if photos or videos:
        try:
            # Собираем все медиа в один список
            all_media = []
            
            # Добавляем фото в альбом
            for photo in photos:
                all_media.append(types.InputMediaPhoto(
                    media=photo["file_id"],
                    caption=photo.get("caption", "")
                ))
            
            # Добавляем видео в альбом
            for video in videos:
                all_media.append(types.InputMediaVideo(
                    media=video["file_id"],
                    caption=video.get("caption", "")
                ))
            
            # Telegram ограничение: 2-10 файлов в альбоме
            if len(all_media) == 1:
                # Один файл - отправляем отдельно
                media = all_media[0]
                if media.type == 'photo':
                    bot.send_photo(CHAT_ID_FOR_REPORT, media.media, caption=media.caption, message_thread_id=THREAD_ID_FOR_ORDER)
                else:
                    bot.send_video(CHAT_ID_FOR_REPORT, media.media, caption=media.caption, message_thread_id=THREAD_ID_FOR_ORDER)
            elif len(all_media) <= 10:
                # 2-10 файлов - отправляем одним альбомом
                bot.send_media_group(
                    chat_id=CHAT_ID_FOR_REPORT,
                    media=all_media,
                    message_thread_id=THREAD_ID_FOR_ORDER
                )
            else:
                # Больше 10 файлов - разбиваем на альбомы по 10
                for i in range(0, len(all_media), 10):
                    chunk = all_media[i:i+10]
                    if len(chunk) == 1:
                        # Один файл в чанке - отправляем отдельно
                        media = chunk[0]
                        if media.type == 'photo':
                            bot.send_photo(CHAT_ID_FOR_REPORT, media.media, caption=media.caption, message_thread_id=THREAD_ID_FOR_ORDER)
                        else:
                            bot.send_video(CHAT_ID_FOR_REPORT, media.media, caption=media.caption, message_thread_id=THREAD_ID_FOR_ORDER)
                    else:
                        # 2-10 файлов в чанке - отправляем альбомом
                        bot.send_media_group(
                            chat_id=CHAT_ID_FOR_REPORT,
                            media=chunk,
                            message_thread_id=THREAD_ID_FOR_ORDER
                        )
                
        except Exception as e:
            print(f"Ошибка отправки медиа-альбома: {e}")
            # Fallback: отправляем медиа по отдельности как раньше
            for photo in photos:
                try:
                    bot.send_photo(CHAT_ID_FOR_REPORT, photo["file_id"], caption=photo.get("caption", ""), message_thread_id=THREAD_ID_FOR_ORDER)
                except Exception as photo_error:
                    print(f"Ошибка отправки фото: {photo_error}")

            for video in videos:
                try:
                    bot.send_video(CHAT_ID_FOR_REPORT, video["file_id"], caption=video.get("caption", ""), message_thread_id=THREAD_ID_FOR_ORDER)
                except Exception as video_error:
                    print(f"Ошибка отправки видео: {video_error}")

    # Сохраняем только message_id для возможного удаления при объединении заказов
    shop_order_messages[shop] = {
        "message_id": order_message.message_id
    }

    # СОХРАНЯЕМ ЗАКАЗ В ГЛОБАЛЬНЫХ ДАННЫХ МАГАЗИНА
    try:
        shop_data[shop]["last_order"] = items.copy()
        
        # ВАЖНО: Обновляем pending_delivery только новыми позициями, ИСКЛЮЧАЯ фото-позиции
        # Исключаем уже принятые товары из pending_delivery и фото-позиции
        accepted_items = shop_data[shop]["accepted_delivery"]
        new_pending_items = [item for item in items if item not in accepted_items and not is_photo_related_item(item)]
        shop_data[shop]["pending_delivery"] = new_pending_items
    except Exception as e:
        logging.error(f"Ошибка сохранения данных заказа для магазина {shop}: {e}")
        # Continue execution as this is not critical for order delivery

print("✅ Бот запущен...")
bot.infinity_polling()
