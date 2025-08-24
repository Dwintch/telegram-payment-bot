#!/usr/bin/env python3
"""
Модуль учёта выходных для Telegram бота
Полностью изолированный модуль с поддержкой заявок, подтверждения/отклонения
"""

import json
import os
import logging
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional
from telebot import types

from holidays_config import (
    HOLIDAYS_CHAT_ID,
    HOLIDAYS_THREAD_ID, 
    HOLIDAYS_ADMIN_IDS,
    HOLIDAYS_DB_PATH
)

# === THREAD ID UTILITY FUNCTIONS FOR HOLIDAYS ===
def get_thread_id_from_message(message):
    """Извлечь thread_id из входящего сообщения Telegram"""
    if hasattr(message, 'message_thread_id') and message.message_thread_id:
        return message.message_thread_id
    return None

def send_message_with_thread_logging(bot, chat_id, text, thread_id=None, **kwargs):
    """Отправить сообщение с логированием чата и топика (holidays module)"""
    try:
        # Логируем куда отправляем сообщение
        thread_info = f"thread {thread_id}" if thread_id else "основной чат"
        logging.info(f"📤 [HOLIDAYS] Отправка сообщения в чат {chat_id}, {thread_info}")
        
        # Отправляем сообщение
        if thread_id:
            kwargs['message_thread_id'] = thread_id
        result = bot.send_message(chat_id, text, **kwargs)
        
        logging.info(f"✅ [HOLIDAYS] Сообщение успешно отправлено в чат {chat_id}, {thread_info}")
        return result
    except Exception as e:
        thread_info = f"thread {thread_id}" if thread_id else "основной чат"
        logging.error(f"❌ [HOLIDAYS] Ошибка отправки сообщения в чат {chat_id}, {thread_info}: {e}")
        raise

def reply_to_with_thread_logging(bot, message, text, **kwargs):
    """Ответить на сообщение с логированием (holidays module)"""
    try:
        thread_id = get_thread_id_from_message(message)
        thread_info = f"thread {thread_id}" if thread_id else "основной чат"
        logging.info(f"📤 [HOLIDAYS] Ответ на сообщение в чат {message.chat.id}, {thread_info}")
        
        result = bot.reply_to(message, text, **kwargs)
        
        logging.info(f"✅ [HOLIDAYS] Ответ успешно отправлен в чат {message.chat.id}, {thread_info}")
        return result
    except Exception as e:
        thread_id = get_thread_id_from_message(message)
        thread_info = f"thread {thread_id}" if thread_id else "основной чат"
        logging.error(f"❌ [HOLIDAYS] Ошибка отправки ответа в чат {message.chat.id}, {thread_info}: {e}")
        raise

# Статусы заявок
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"

class HolidayDatabase:
    """Класс для работы с базой данных выходных"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._data = self._load_data()
    
    def _load_data(self) -> Dict:
        """Загрузить данные из JSON файла"""
        if os.path.exists(self.db_path):
            try:
                with open(self.db_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"Ошибка загрузки базы данных выходных: {e}")
        
        # Создаем пустую структуру данных
        return {
            "requests": {},  # {request_id: {user_id, date, reason, status, created_at, processed_by, processed_at}}
            "users": {},     # {user_id: {name, username, first_name, last_name}}
            "next_id": 1
        }
    
    def _save_data(self) -> bool:
        """Сохранить данные в JSON файл"""
        try:
            with open(self.db_path, 'w', encoding='utf-8') as f:
                json.dump(self._data, f, ensure_ascii=False, indent=2)
            return True
        except IOError as e:
            logging.error(f"Ошибка сохранения базы данных выходных: {e}")
            return False
    
    def add_user(self, user_id: int, user_data: Dict) -> None:
        """Добавить или обновить информацию о пользователе"""
        self._data["users"][str(user_id)] = {
            "username": user_data.get("username", ""),
            "first_name": user_data.get("first_name", ""),
            "last_name": user_data.get("last_name", ""),
            "last_update": datetime.now().isoformat()
        }
        self._save_data()
    
    def create_request(self, user_id: int, holiday_date: str, reason: str) -> int:
        """Создать новую заявку на выходной"""
        request_id = self._data["next_id"]
        self._data["next_id"] += 1
        
        self._data["requests"][str(request_id)] = {
            "user_id": user_id,
            "date": holiday_date,
            "reason": reason,
            "status": STATUS_PENDING,
            "created_at": datetime.now().isoformat(),
            "processed_by": None,
            "processed_at": None
        }
        
        self._save_data()
        return request_id
    
    def update_request_status(self, request_id: int, status: str, admin_id: int) -> bool:
        """Обновить статус заявки"""
        req_id_str = str(request_id)
        if req_id_str not in self._data["requests"]:
            return False
        
        self._data["requests"][req_id_str]["status"] = status
        self._data["requests"][req_id_str]["processed_by"] = admin_id
        self._data["requests"][req_id_str]["processed_at"] = datetime.now().isoformat()
        
        return self._save_data()
    
    def get_request(self, request_id: int) -> Optional[Dict]:
        """Получить заявку по ID"""
        return self._data["requests"].get(str(request_id))
    
    def get_user_requests(self, user_id: int, status: Optional[str] = None) -> List[Dict]:
        """Получить заявки пользователя"""
        requests = []
        for req_id, req_data in self._data["requests"].items():
            if req_data["user_id"] == user_id:
                if status is None or req_data["status"] == status:
                    req_data["id"] = int(req_id)
                    requests.append(req_data)
        
        # Сортируем по дате создания (новые сначала)
        requests.sort(key=lambda x: x["created_at"], reverse=True)
        return requests
    
    def get_future_approved_requests(self, user_id: int) -> List[Dict]:
        """Получить будущие одобренные заявки пользователя"""
        today = date.today().isoformat()
        requests = []
        
        for req_id, req_data in self._data["requests"].items():
            if (req_data["user_id"] == user_id and 
                req_data["status"] == STATUS_APPROVED and 
                req_data["date"] >= today):
                req_data["id"] = int(req_id)
                requests.append(req_data)
        
        # Сортируем по дате выходного
        requests.sort(key=lambda x: x["date"])
        return requests
    
    def get_all_approved_requests(self, user_id: int) -> List[Dict]:
        """Получить все одобренные заявки пользователя"""
        requests = []
        
        for req_id, req_data in self._data["requests"].items():
            if (req_data["user_id"] == user_id and 
                req_data["status"] == STATUS_APPROVED):
                req_data["id"] = int(req_id)
                requests.append(req_data)
        
        # Сортируем по дате выходного (новые сначала)
        requests.sort(key=lambda x: x["date"], reverse=True)
        return requests
    
    def get_user_info(self, user_id: int) -> Optional[Dict]:
        """Получить информацию о пользователе"""
        return self._data["users"].get(str(user_id))
    
    def is_date_available(self, holiday_date: str) -> bool:
        """Проверить, доступна ли дата для подачи заявки (нет одобренных заявок на эту дату)"""
        for req_data in self._data["requests"].values():
            if (req_data["date"] == holiday_date and 
                req_data["status"] == STATUS_APPROVED):
                return False
        return True
    
    def get_free_dates(self, days_count: int = 7) -> List[str]:
        """Получить список ближайших свободных дат для выходных"""
        free_dates = []
        current_date = date.today()
        days_checked = 0
        max_days_to_check = days_count * 5  # Проверяем больше дней, чтобы найти нужное количество свободных
        
        while len(free_dates) < days_count and days_checked < max_days_to_check:
            days_checked += 1
            check_date = current_date + timedelta(days=days_checked)
            date_str = check_date.isoformat()
            
            # Проверяем только будние дни (понедельник-пятница, weekday 0-4)
            if check_date.weekday() < 5 and self.is_date_available(date_str):
                free_dates.append(date_str)
        
        return free_dates

# Глобальная база данных
db = HolidayDatabase(HOLIDAYS_DB_PATH)

def is_holidays_chat_and_thread(message) -> bool:
    """Проверить, что сообщение из нужного чата и топика"""
    # Логируем все входящие сообщения для отладки
    chat_id = message.chat.id
    thread_id = getattr(message, 'message_thread_id', None)
    text = getattr(message, 'text', 'N/A')
    user_id = message.from_user.id if message.from_user else 'Unknown'
    
    logging.info(f"🔍 DEBUG: Входящее сообщение - Chat ID: {chat_id}, Thread ID: {thread_id}, User ID: {user_id}, Text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
    
    result = (chat_id == HOLIDAYS_CHAT_ID and thread_id == HOLIDAYS_THREAD_ID)
    
    if not result:
        logging.info(f"❌ Сообщение отфильтровано: ожидается Chat ID: {HOLIDAYS_CHAT_ID}, Thread ID: {HOLIDAYS_THREAD_ID}")
    else:
        logging.info(f"✅ Сообщение соответствует фильтру holidays")
    
    return result

def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    return user_id in HOLIDAYS_ADMIN_IDS

def format_date(date_str: str) -> str:
    """Форматировать дату для отображения"""
    try:
        date_obj = datetime.fromisoformat(date_str).date()
        return date_obj.strftime("%d.%m.%Y")
    except:
        return date_str

def format_datetime(datetime_str: str) -> str:
    """Форматировать дату и время для отображения"""
    try:
        dt_obj = datetime.fromisoformat(datetime_str)
        return dt_obj.strftime("%d.%m.%Y %H:%M")
    except:
        return datetime_str

def get_user_display_name(user_data: Dict) -> str:
    """Получить отображаемое имя пользователя"""
    if user_data.get("first_name") and user_data.get("last_name"):
        return f"{user_data['first_name']} {user_data['last_name']}"
    elif user_data.get("first_name"):
        return user_data["first_name"]
    elif user_data.get("username"):
        return f"@{user_data['username']}"
    else:
        return "Неизвестный пользователь"

def create_approval_keyboard(request_id: int) -> types.InlineKeyboardMarkup:
    """Создать клавиатуру для подтверждения/отклонения заявки"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("✅ Одобрить", callback_data=f"holiday_approve_{request_id}"),
        types.InlineKeyboardButton("❌ Отклонить", callback_data=f"holiday_reject_{request_id}")
    )
    return keyboard

def parse_flexible_date(date_input: str) -> Optional[date]:
    """
    Парсинг гибкого формата даты для команды /в
    
    Поддерживаемые форматы:
    - /в 24 -> если до 24 числа - текущий месяц, если >= 24 - следующий месяц
    - /в 24.08 или /в 24 08 -> 24-е указанного месяца (этот или следующий год)
    - /в 24.08.2025 или /в 24 08 2025 -> точная дата
    
    Returns:
        date объект или None при ошибке парсинга
    """
    try:
        # Нормализуем входные данные - заменяем пробелы на точки и убираем лишние пробелы
        normalized = date_input.strip().replace(' ', '.')
        
        # Убираем ведущие нули
        parts = []
        for part in normalized.split('.'):
            if part.isdigit():
                parts.append(str(int(part)))  # Убираем ведущие нули
            else:
                parts.append(part)
        
        today = date.today()
        current_year = today.year
        current_month = today.month
        current_day = today.day
        
        if len(parts) == 1:
            # Формат: /в 24
            day = int(parts[0])
            if not (1 <= day <= 31):
                return None
                
            # Логика выбора месяца
            if current_day < day:
                # До этого числа в текущем месяце - берем текущий месяц
                target_month = current_month
                target_year = current_year
            else:
                # После этого числа - берем следующий месяц
                if current_month == 12:
                    target_month = 1
                    target_year = current_year + 1
                else:
                    target_month = current_month + 1
                    target_year = current_year
            
            # Проверяем валидность даты
            try:
                return date(target_year, target_month, day)
            except ValueError:
                return None
            
        elif len(parts) == 2:
            # Формат: /в 24.08 или /в 24 08
            day = int(parts[0])
            month = int(parts[1])
            
            if not (1 <= day <= 31) or not (1 <= month <= 12):
                return None
            
            # Выбираем год - этот или следующий
            target_date_this_year = None
            try:
                target_date_this_year = date(current_year, month, day)
            except ValueError:
                # Invalid date (like Feb 31) - try next year
                try:
                    return date(current_year + 1, month, day)
                except ValueError:
                    return None
            
            if target_date_this_year and target_date_this_year > today:
                return target_date_this_year
            else:
                try:
                    return date(current_year + 1, month, day)
                except ValueError:
                    return None
            
        elif len(parts) == 3:
            # Формат: /в 24.08.2025 или /в 24 08 2025
            day = int(parts[0])
            month = int(parts[1])
            year = int(parts[2])
            
            if not (1 <= day <= 31) or not (1 <= month <= 12) or year < 2020:
                return None
            
            try:
                return date(year, month, day)
            except ValueError:
                return None
        
        else:
            return None
            
    except (ValueError, IndexError):
        return None

def handle_holiday_request(bot, message):
    """Обработчик команды подачи заявки на выходной"""
    logging.info(f"🎯 Обработка заявки на выходной от пользователя {message.from_user.id}")
    
    # Фильтрация уже выполнена на уровне регистрации обработчика
    
    try:
        # Добавляем пользователя в базу
        user_data = {
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name
        }
        db.add_user(message.from_user.id, user_data)
        logging.info(f"✅ Пользователь {message.from_user.id} добавлен в базу")
        
        # Парсим текст сообщения
        text = message.text.strip()
        parts = text.split(None, 2)  # Разделяем на максимум 3 части
        
        if len(parts) < 3:
            error_msg = (
                "❌ Неправильный формат команды!\n\n"
                "Используйте: /выходной ГГГГ-ММ-ДД причина\n"
                "Пример: /выходной 2024-12-31 семейные обстоятельства"
            )
            bot.reply_to(message, error_msg)
            logging.info(f"❌ Неправильный формат команды от пользователя {message.from_user.id}")
            return
        
        command, date_str, reason = parts
        logging.info(f"📅 Парсинг заявки: дата={date_str}, причина={reason[:30]}...")
        
        # Проверяем формат даты
        try:
            holiday_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            error_msg = (
                "❌ Неправильный формат даты!\n\n"
                "Используйте формат ГГГГ-ММ-ДД\n"
                "Пример: 2024-12-31"
            )
            bot.reply_to(message, error_msg)
            logging.error(f"❌ Неправильный формат даты '{date_str}' от пользователя {message.from_user.id}")
            return
        
        # Проверяем, что дата в будущем
        if holiday_date <= date.today():
            bot.reply_to(message, "❌ Нельзя подать заявку на прошедшую дату!")
            logging.info(f"❌ Попытка подачи заявки на прошедшую дату {date_str} от пользователя {message.from_user.id}")
            return
        
        # Проверяем, что дата свободна (нет одобренных заявок)
        if not db.is_date_available(date_str):
            bot.reply_to(message, f"❌ Дата {format_date(date_str)} уже занята! Выберите другую дату.")
            logging.info(f"❌ Попытка подачи заявки на занятую дату {date_str} от пользователя {message.from_user.id}")
            return
        
        # Создаем заявку
        request_id = db.create_request(message.from_user.id, date_str, reason)
        logging.info(f"✅ Создана заявка #{request_id} от пользователя {message.from_user.id}")
        
        # Отправляем подтверждение пользователю
        user_name = get_user_display_name(user_data)
        confirmation_msg = (
            f"✅ Заявка на выходной подана!\n\n"
            f"📅 Дата: {format_date(date_str)}\n"
            f"📝 Причина: {reason}\n"
            f"🆔 Номер заявки: #{request_id}\n\n"
            f"Ваша заявка будет рассмотрена администратором."
        )
        reply_to_with_thread_logging(bot, message, confirmation_msg)
        logging.info(f"✅ Подтверждение отправлено пользователю {message.from_user.id}")
        
        # Отправляем уведомление администраторам
        admin_text = (
            f"📝 Новая заявка на выходной\n\n"
            f"👤 От: {user_name} (ID: {message.from_user.id})\n"
            f"📅 Дата: {format_date(date_str)}\n"
            f"📝 Причина: {reason}\n"
            f"🆔 Заявка: #{request_id}\n"
            f"🕐 Подана: {format_datetime(datetime.now().isoformat())}"
        )
        
        try:
            send_message_with_thread_logging(
                bot,
                HOLIDAYS_CHAT_ID,
                admin_text,
                thread_id=HOLIDAYS_THREAD_ID,
                reply_markup=create_approval_keyboard(request_id)
            )
            logging.info(f"✅ Уведомление администраторам отправлено для заявки #{request_id}")
        except Exception as e:
            logging.error(f"❌ Ошибка отправки уведомления администраторам: {e}")
    
    except Exception as e:
        logging.error(f"❌ Ошибка обработки заявки на выходной от пользователя {message.from_user.id}: {e}")
        bot.reply_to(message, "❌ Произошла ошибка при подаче заявки. Попробуйте позже.")

def handle_flexible_holiday_request(bot, message):
    """Обработчик команды /в с гибким форматом даты"""
    logging.info(f"🎯 Обработка гибкой заявки на выходной от пользователя {message.from_user.id}")
    
    try:
        # Добавляем пользователя в базу
        user_data = {
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name
        }
        db.add_user(message.from_user.id, user_data)
        logging.info(f"✅ Пользователь {message.from_user.id} добавлен в базу")
        
        # Парсим текст сообщения
        text = message.text.strip()
        parts = text.split(None, 2)  # Разделяем на максимум 3 части
        
        if len(parts) < 3:
            error_msg = (
                "❌ Неправильный формат команды!\n\n"
                "Используйте: /в дата причина\n"
                "Примеры:\n"
                "• /в 24 семейные обстоятельства\n"
                "• /в 24.08 отпуск\n" 
                "• /в 24 08 болезнь\n"
                "• /в 24.08.2025 свадьба\n"
                "• /в 24 08 2025 командировка"
            )
            bot.reply_to(message, error_msg)
            logging.info(f"❌ Неправильный формат команды /в от пользователя {message.from_user.id}")
            return
        
        command, date_input, reason = parts
        logging.info(f"📅 Парсинг гибкой заявки: дата_ввод={date_input}, причина={reason[:30]}...")
        
        # Парсим дату с помощью нашей функции
        holiday_date = parse_flexible_date(date_input)
        if not holiday_date:
            error_msg = (
                "❌ Неправильный формат даты!\n\n"
                "Поддерживаемые форматы:\n"
                "• /в 24 (день текущего/следующего месяца)\n"
                "• /в 24.08 или /в 24 08 (день и месяц)\n"
                "• /в 24.08.2025 или /в 24 08 2025 (полная дата)"
            )
            bot.reply_to(message, error_msg)
            logging.error(f"❌ Неправильный формат даты '{date_input}' от пользователя {message.from_user.id}")
            return
        
        date_str = holiday_date.isoformat()
        logging.info(f"📅 Распознанная дата: {date_str}")
        
        # Проверяем, что дата в будущем
        if holiday_date <= date.today():
            bot.reply_to(message, "❌ Нельзя подать заявку на прошедшую дату!")
            logging.info(f"❌ Попытка подачи заявки на прошедшую дату {date_str} от пользователя {message.from_user.id}")
            return
        
        # Проверяем, что дата свободна (нет одобренных заявок)
        if not db.is_date_available(date_str):
            bot.reply_to(message, f"❌ Дата {format_date(date_str)} уже занята! Выберите другую дату.")
            logging.info(f"❌ Попытка подачи заявки на занятую дату {date_str} от пользователя {message.from_user.id}")
            return
        
        # Создаем заявку
        request_id = db.create_request(message.from_user.id, date_str, reason)
        logging.info(f"✅ Создана заявка #{request_id} от пользователя {message.from_user.id}")
        
        # Отправляем подтверждение пользователю
        user_name = get_user_display_name(user_data)
        confirmation_msg = (
            f"✅ Заявка на выходной подана!\n\n"
            f"📅 Дата: {format_date(date_str)}\n"
            f"📝 Причина: {reason}\n"
            f"🆔 Номер заявки: #{request_id}\n\n"
            f"Ваша заявка будет рассмотрена администратором."
        )
        reply_to_with_thread_logging(bot, message, confirmation_msg)
        logging.info(f"✅ Подтверждение отправлено пользователю {message.from_user.id}")
        
        # Отправляем уведомление администраторам
        admin_text = (
            f"📝 Новая заявка на выходной\n\n"
            f"👤 От: {user_name} (ID: {message.from_user.id})\n"
            f"📅 Дата: {format_date(date_str)}\n"
            f"📝 Причина: {reason}\n"
            f"🆔 Заявка: #{request_id}\n"
            f"🕐 Подана: {format_datetime(datetime.now().isoformat())}"
        )
        
        try:
            send_message_with_thread_logging(
                bot,
                HOLIDAYS_CHAT_ID,
                admin_text,
                thread_id=HOLIDAYS_THREAD_ID,
                reply_markup=create_approval_keyboard(request_id)
            )
            logging.info(f"✅ Уведомление администраторам отправлено для заявки #{request_id}")
        except Exception as e:
            logging.error(f"❌ Ошибка отправки уведомления администраторам: {e}")
    
    except Exception as e:
        logging.error(f"❌ Ошибка обработки гибкой заявки на выходной от пользователя {message.from_user.id}: {e}")
        bot.reply_to(message, "❌ Произошла ошибка при подаче заявки. Попробуйте позже.")

def handle_free_dates_command(bot, message):
    """Обработчик команд /сд, /даты - показать свободные даты"""
    logging.info(f"🎯 Обработка команды свободных дат от пользователя {message.from_user.id}")
    
    try:
        # Добавляем пользователя в базу
        user_data = {
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name
        }
        db.add_user(message.from_user.id, user_data)
        
        # Получаем свободные даты
        free_dates = db.get_free_dates(7)
        logging.info(f"📊 Найдено {len(free_dates)} свободных дат")
        
        if not free_dates:
            bot.reply_to(message, "😔 В ближайшее время свободных дат для выходных не найдено.")
            return
        
        # Формируем ответ
        text = "📅 Ближайшие свободные даты для выходных:\n\n"
        for i, date_str in enumerate(free_dates, 1):
            text += f"{i}. {format_date(date_str)}\n"
        
        text += f"\n💡 Для подачи заявки используйте команду /в"
        
        reply_to_with_thread_logging(bot, message, text)
        logging.info(f"✅ Список свободных дат отправлен пользователю {message.from_user.id}")
    
    except Exception as e:
        logging.error(f"❌ Ошибка получения свободных дат для пользователя {message.from_user.id}: {e}")
        bot.reply_to(message, "❌ Произошла ошибка при получении данных.")

def handle_future_holidays_command(bot, message):
    """Обработчик команды /вых - показать будущие одобренные выходные"""
    logging.info(f"🎯 Обработка команды /вых от пользователя {message.from_user.id}")
    
    # Фильтрация уже выполнена на уровне регистрации обработчика
    
    try:
        # Добавляем пользователя в базу
        user_data = {
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name
        }
        db.add_user(message.from_user.id, user_data)
        logging.info(f"✅ Пользователь {message.from_user.id} добавлен в базу для команды /вых")
        
        # Получаем будущие одобренные заявки
        requests = db.get_future_approved_requests(message.from_user.id)
        logging.info(f"📊 Найдено {len(requests)} будущих одобренных заявок для пользователя {message.from_user.id}")
        
        if not requests:
            bot.reply_to(message, "📅 У вас нет запланированных выходных дней.")
            return
        
        # Формируем ответ
        text = "📅 Ваши запланированные выходные:\n\n"
        for req in requests:
            text += f"📅 {format_date(req['date'])}\n"
            text += f"📝 Причина: {req['reason']}\n"
            text += f"🆔 Заявка: #{req['id']}\n\n"
        
        bot.reply_to(message, text)
        logging.info(f"✅ Список будущих выходных отправлен пользователю {message.from_user.id}")
    
    except Exception as e:
        logging.error(f"❌ Ошибка получения будущих выходных для пользователя {message.from_user.id}: {e}")
        bot.reply_to(message, "❌ Произошла ошибка при получении данных.")

def handle_all_holidays_command(bot, message):
    """Обработчик команды /всевых - показать все одобренные выходные"""
    logging.info(f"🎯 Обработка команды /всевых от пользователя {message.from_user.id}")
    
    # Фильтрация уже выполнена на уровне регистрации обработчика
    
    try:
        # Добавляем пользователя в базу
        user_data = {
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name
        }
        db.add_user(message.from_user.id, user_data)
        logging.info(f"✅ Пользователь {message.from_user.id} добавлен в базу для команды /всевых")
        
        # Получаем все одобренные заявки
        requests = db.get_all_approved_requests(message.from_user.id)
        logging.info(f"📊 Найдено {len(requests)} всех одобренных заявок для пользователя {message.from_user.id}")
        
        if not requests:
            bot.reply_to(message, "📅 У вас нет одобренных выходных дней.")
            return
        
        # Формируем ответ
        text = "📅 Все ваши одобренные выходные:\n\n"
        for req in requests:
            status_icon = "🔮" if req['date'] >= date.today().isoformat() else "📋"
            text += f"{status_icon} {format_date(req['date'])}\n"
            text += f"📝 Причина: {req['reason']}\n"
            text += f"🆔 Заявка: #{req['id']}\n\n"
        
        # Ограничиваем длину сообщения
        if len(text) > 4000:
            text = text[:3950] + "\n\n... (список обрезан)"
            logging.info(f"⚠️ Список всех выходных обрезан для пользователя {message.from_user.id}")
        
        bot.reply_to(message, text)
        logging.info(f"✅ Список всех выходных отправлен пользователю {message.from_user.id}")
    
    except Exception as e:
        logging.error(f"❌ Ошибка получения всех выходных для пользователя {message.from_user.id}: {e}")
        bot.reply_to(message, "❌ Произошла ошибка при получении данных.")

def handle_approval_callback(bot, call):
    """Обработчик коллбэков для одобрения/отклонения заявок"""
    logging.info(f"🎯 Обработка callback от администратора {call.from_user.id}: {call.data}")
    
    # Фильтрация по чату уже выполнена на уровне регистрации обработчика
    
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этого действия!")
        logging.warning(f"❌ Неавторизованная попытка callback от пользователя {call.from_user.id}")
        return
    
    try:
        callback_data = call.data
        if callback_data.startswith("holiday_approve_"):
            request_id = int(callback_data.replace("holiday_approve_", ""))
            status = STATUS_APPROVED
            status_text = "✅ ОДОБРЕНА"
            action_text = "одобрена"
        elif callback_data.startswith("holiday_reject_"):
            request_id = int(callback_data.replace("holiday_reject_", ""))
            status = STATUS_REJECTED
            status_text = "❌ ОТКЛОНЕНА"
            action_text = "отклонена"
        else:
            logging.warning(f"❌ Неизвестный callback: {callback_data}")
            return
        
        logging.info(f"📋 Обработка заявки #{request_id}: {action_text}")
        
        # Получаем заявку
        request = db.get_request(request_id)
        if not request:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена!")
            logging.error(f"❌ Заявка #{request_id} не найдена")
            return
        
        if request["status"] != STATUS_PENDING:
            bot.answer_callback_query(call.id, "❌ Заявка уже обработана!")
            logging.info(f"⚠️ Заявка #{request_id} уже обработана (статус: {request['status']})")
            return
        
        # Обновляем статус заявки
        if not db.update_request_status(request_id, status, call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Ошибка обновления заявки!")
            logging.error(f"❌ Не удалось обновить статус заявки #{request_id}")
            return
        
        logging.info(f"✅ Статус заявки #{request_id} обновлен на '{status}' администратором {call.from_user.id}")
        
        # Получаем информацию о пользователе, подавшем заявку
        user_info = db.get_user_info(request["user_id"])
        user_name = get_user_display_name(user_info) if user_info else f"ID: {request['user_id']}"
        
        # Обновляем сообщение
        updated_text = (
            f"📝 Заявка на выходной {status_text}\n\n"
            f"👤 От: {user_name} (ID: {request['user_id']})\n"
            f"📅 Дата: {format_date(request['date'])}\n"
            f"📝 Причина: {request['reason']}\n"
            f"🆔 Заявка: #{request_id}\n"
            f"🕐 Подана: {format_datetime(request['created_at'])}\n"
            f"👮 {action_text}: {get_user_display_name({'first_name': call.from_user.first_name, 'last_name': call.from_user.last_name})}\n"
            f"🕐 {format_datetime(datetime.now().isoformat())}"
        )
        
        bot.edit_message_text(
            updated_text,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id
        )
        logging.info(f"✅ Сообщение администратора обновлено для заявки #{request_id}")
        
        # Отправляем уведомление пользователю
        notification_text = (
            f"📝 Ваша заявка на выходной {status_text.lower()}\n\n"
            f"📅 Дата: {format_date(request['date'])}\n"
            f"📝 Причина: {request['reason']}\n"
            f"🆔 Заявка: #{request_id}"
        )
        
        try:
            bot.send_message(request["user_id"], notification_text)
            logging.info(f"✅ Уведомление отправлено пользователю {request['user_id']} о заявке #{request_id}")
        except Exception as e:
            logging.error(f"❌ Ошибка отправки уведомления пользователю {request['user_id']}: {e}")
        
        bot.answer_callback_query(call.id, f"✅ Заявка {action_text}!")
    
    except Exception as e:
        logging.error(f"❌ Ошибка обработки коллбэка одобрения от администратора {call.from_user.id}: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка!")

def register_holiday_handlers(bot, debug_mode=True):
    """
    Регистрация всех обработчиков модуля выходных
    
    Args:
        bot: Экземпляр Telegram бота
        debug_mode: Если True, регистрирует debug-обработчик (по умолчанию включен)
    """
    
    # Команда подачи заявки на выходной (старый формат) - ТОЛЬКО для нужного чата и топика
    @bot.message_handler(commands=['выходной'], func=lambda message: is_holidays_chat_and_thread(message))
    def holiday_request_handler(message):
        handle_holiday_request(bot, message)
    
    # Команда подачи заявки на выходной (новый гибкий формат) - ТОЛЬКО для нужного чата и топика
    @bot.message_handler(commands=['в'], func=lambda message: is_holidays_chat_and_thread(message))
    def flexible_holiday_request_handler(message):
        handle_flexible_holiday_request(bot, message)
    
    # Команда просмотра будущих выходных - ТОЛЬКО для нужного чата и топика
    @bot.message_handler(commands=['вых'], func=lambda message: is_holidays_chat_and_thread(message))
    def future_holidays_handler(message):
        handle_future_holidays_command(bot, message)
    
    # Команды просмотра всех выходных (оригинальная и синонимы) - ТОЛЬКО для нужного чата и топика
    @bot.message_handler(commands=['всевых', 'вс', 'список'], func=lambda message: is_holidays_chat_and_thread(message))
    def all_holidays_handler(message):
        handle_all_holidays_command(bot, message)
    
    # Команды для просмотра свободных дат - ТОЛЬКО для нужного чата и топика
    @bot.message_handler(commands=['сд', 'даты'], func=lambda message: is_holidays_chat_and_thread(message))
    def free_dates_handler(message):
        handle_free_dates_command(bot, message)
    
    # Обработчик коллбэков для одобрения/отклонения - ТОЛЬКО для нужного чата
    @bot.callback_query_handler(func=lambda call: call.message.chat.id == HOLIDAYS_CHAT_ID and call.data.startswith(('holiday_approve_', 'holiday_reject_')))
    def approval_callback_handler(call):
        handle_approval_callback(bot, call)
    
    # ВРЕМЕННЫЙ DEBUG-ОБРАБОТЧИК (отключается параметром debug_mode=False)
    if debug_mode:
        @bot.message_handler(func=lambda message: message.chat.id == HOLIDAYS_CHAT_ID)
        def debug_message_handler(message):
            """Временный обработчик для отладки - логирует все сообщения, отвечает только в нужном топике"""
            try:
                chat_id = message.chat.id
                thread_id = getattr(message, 'message_thread_id', None)
                text = getattr(message, 'text', 'N/A')
                user_id = message.from_user.id if message.from_user else 'Unknown'
                
                # Логируем все сообщения из группы для отладки (как требуется в задаче)
                logging.info(f"🔍 DEBUG: Сообщение в группе - Chat ID: {chat_id}, Thread ID: {thread_id}, User ID: {user_id}, Text: '{text[:50]}{'...' if len(text) > 50 else ''}'")
                
                # Отвечаем только если сообщение из нужного топика
                if is_holidays_chat_and_thread(message):
                    debug_response = (
                        f"🔧 DEBUG: Я вижу сообщение из чата {chat_id}, "
                        f"топика {thread_id}, от пользователя {user_id}.\n"
                        f"Текст: '{text[:100]}{'...' if len(text) > 100 else ''}'\n\n"
                        f"Настройки модуля:\n"
                        f"• Ожидаемый Chat ID: {HOLIDAYS_CHAT_ID}\n"
                        f"• Ожидаемый Thread ID: {HOLIDAYS_THREAD_ID}\n"
                        f"• Совпадает чат: {'✅' if chat_id == HOLIDAYS_CHAT_ID else '❌'}\n"
                        f"• Совпадает топик: {'✅' if thread_id == HOLIDAYS_THREAD_ID else '❌'}"
                    )
                    
                    logging.info(f"🔧 DEBUG Handler: отправляем отладочный ответ в чат {chat_id}, топик {thread_id}")
                    
                    # Отправляем в тот же топик, где получили сообщение
                    send_message_with_thread_logging(
                        bot,
                        chat_id=chat_id,
                        text=debug_response,
                        thread_id=thread_id
                    )
                else:
                    logging.info(f"🔧 DEBUG Handler: сообщение из неподходящего топика, не отвечаем")
                
            except Exception as e:
                logging.error(f"❌ Ошибка в debug-обработчике: {e}")
        
        logging.info(f"🔧 DEBUG: Активирован временный debug-обработчик для чата {HOLIDAYS_CHAT_ID}")
    
    logging.info("✅ Модуль учёта выходных успешно зарегистрирован")