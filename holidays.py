#!/usr/bin/env python3
"""
Модуль учёта выходных для Telegram бота
Полностью изолированный модуль с поддержкой заявок, подтверждения/отклонения
"""

import json
import os
import logging
from datetime import datetime, date
from typing import Dict, List, Optional
from telebot import types

from holidays_config import (
    HOLIDAYS_CHAT_ID,
    HOLIDAYS_THREAD_ID, 
    HOLIDAYS_ADMIN_IDS,
    HOLIDAYS_DB_PATH
)

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

# Глобальная база данных
db = HolidayDatabase(HOLIDAYS_DB_PATH)

def is_holidays_chat_and_thread(message) -> bool:
    """Проверить, что сообщение из нужного чата и топика"""
    return (message.chat.id == HOLIDAYS_CHAT_ID and 
            getattr(message, 'message_thread_id', None) == HOLIDAYS_THREAD_ID)

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

def handle_holiday_request(bot, message):
    """Обработчик команды подачи заявки на выходной"""
    if not is_holidays_chat_and_thread(message):
        return
    
    try:
        # Добавляем пользователя в базу
        user_data = {
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name
        }
        db.add_user(message.from_user.id, user_data)
        
        # Парсим текст сообщения
        text = message.text.strip()
        parts = text.split(None, 2)  # Разделяем на максимум 3 части
        
        if len(parts) < 3:
            bot.reply_to(message, 
                "❌ Неправильный формат команды!\n\n"
                "Используйте: /выходной ГГГГ-ММ-ДД причина\n"
                "Пример: /выходной 2024-12-31 семейные обстоятельства")
            return
        
        command, date_str, reason = parts
        
        # Проверяем формат даты
        try:
            holiday_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            bot.reply_to(message, 
                "❌ Неправильный формат даты!\n\n"
                "Используйте формат ГГГГ-ММ-ДД\n"
                "Пример: 2024-12-31")
            return
        
        # Проверяем, что дата в будущем
        if holiday_date <= date.today():
            bot.reply_to(message, "❌ Нельзя подать заявку на прошедшую дату!")
            return
        
        # Создаем заявку
        request_id = db.create_request(message.from_user.id, date_str, reason)
        
        # Отправляем подтверждение пользователю
        user_name = get_user_display_name(user_data)
        bot.reply_to(message, 
            f"✅ Заявка на выходной подана!\n\n"
            f"📅 Дата: {format_date(date_str)}\n"
            f"📝 Причина: {reason}\n"
            f"🆔 Номер заявки: #{request_id}\n\n"
            f"Ваша заявка будет рассмотрена администратором.")
        
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
            bot.send_message(
                HOLIDAYS_CHAT_ID,
                admin_text,
                message_thread_id=HOLIDAYS_THREAD_ID,
                reply_markup=create_approval_keyboard(request_id)
            )
        except Exception as e:
            logging.error(f"Ошибка отправки уведомления администраторам: {e}")
    
    except Exception as e:
        logging.error(f"Ошибка обработки заявки на выходной: {e}")
        bot.reply_to(message, "❌ Произошла ошибка при подаче заявки. Попробуйте позже.")

def handle_future_holidays_command(bot, message):
    """Обработчик команды /вых - показать будущие одобренные выходные"""
    if not is_holidays_chat_and_thread(message):
        return
    
    try:
        # Добавляем пользователя в базу
        user_data = {
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name
        }
        db.add_user(message.from_user.id, user_data)
        
        # Получаем будущие одобренные заявки
        requests = db.get_future_approved_requests(message.from_user.id)
        
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
    
    except Exception as e:
        logging.error(f"Ошибка получения будущих выходных: {e}")
        bot.reply_to(message, "❌ Произошла ошибка при получении данных.")

def handle_all_holidays_command(bot, message):
    """Обработчик команды /всевых - показать все одобренные выходные"""
    if not is_holidays_chat_and_thread(message):
        return
    
    try:
        # Добавляем пользователя в базу
        user_data = {
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name
        }
        db.add_user(message.from_user.id, user_data)
        
        # Получаем все одобренные заявки
        requests = db.get_all_approved_requests(message.from_user.id)
        
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
        
        bot.reply_to(message, text)
    
    except Exception as e:
        logging.error(f"Ошибка получения всех выходных: {e}")
        bot.reply_to(message, "❌ Произошла ошибка при получении данных.")

def handle_approval_callback(bot, call):
    """Обработчик коллбэков для одобрения/отклонения заявок"""
    if call.message.chat.id != HOLIDAYS_CHAT_ID:
        return
    
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ У вас нет прав для выполнения этого действия!")
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
            return
        
        # Получаем заявку
        request = db.get_request(request_id)
        if not request:
            bot.answer_callback_query(call.id, "❌ Заявка не найдена!")
            return
        
        if request["status"] != STATUS_PENDING:
            bot.answer_callback_query(call.id, "❌ Заявка уже обработана!")
            return
        
        # Обновляем статус заявки
        if not db.update_request_status(request_id, status, call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Ошибка обновления заявки!")
            return
        
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
        
        # Отправляем уведомление пользователю
        notification_text = (
            f"📝 Ваша заявка на выходной {status_text.lower()}\n\n"
            f"📅 Дата: {format_date(request['date'])}\n"
            f"📝 Причина: {request['reason']}\n"
            f"🆔 Заявка: #{request_id}"
        )
        
        try:
            bot.send_message(request["user_id"], notification_text)
        except Exception as e:
            logging.error(f"Ошибка отправки уведомления пользователю {request['user_id']}: {e}")
        
        bot.answer_callback_query(call.id, f"✅ Заявка {action_text}!")
    
    except Exception as e:
        logging.error(f"Ошибка обработки коллбэка одобрения: {e}")
        bot.answer_callback_query(call.id, "❌ Произошла ошибка!")

def register_holiday_handlers(bot):
    """Регистрация всех обработчиков модуля выходных"""
    
    # Команда подачи заявки на выходной
    @bot.message_handler(commands=['выходной'])
    def holiday_request_handler(message):
        handle_holiday_request(bot, message)
    
    # Команда просмотра будущих выходных
    @bot.message_handler(commands=['вых'])
    def future_holidays_handler(message):
        handle_future_holidays_command(bot, message)
    
    # Команда просмотра всех выходных
    @bot.message_handler(commands=['всевых'])
    def all_holidays_handler(message):
        handle_all_holidays_command(bot, message)
    
    # Обработчик коллбэков для одобрения/отклонения
    @bot.callback_query_handler(func=lambda call: call.data.startswith(('holiday_approve_', 'holiday_reject_')))
    def approval_callback_handler(call):
        handle_approval_callback(bot, call)
    
    logging.info("✅ Модуль учёта выходных успешно зарегистрирован")