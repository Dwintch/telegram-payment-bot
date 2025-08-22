#!/usr/bin/env python3
"""
Тест модуля учёта выходных
"""

import sys
import os
import json
import tempfile
from datetime import datetime, date

# Добавляем путь к модулям
sys.path.append('.')

def test_database_operations():
    """Тест операций с базой данных"""
    print("🧪 Тестирование операций с базой данных...")
    
    # Создаем временный файл для тестов
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        json.dump({"requests": {}, "users": {}, "next_id": 1}, tmp_file)
        tmp_db_path = tmp_file.name
    
    try:
        from holidays import HolidayDatabase
        
        # Создаем экземпляр базы данных
        db = HolidayDatabase(tmp_db_path)
        
        # Тест добавления пользователя
        user_data = {
            "username": "test_user",
            "first_name": "Тест",
            "last_name": "Пользователь"
        }
        db.add_user(12345, user_data)
        
        # Тест создания заявки
        request_id = db.create_request(12345, "2024-12-31", "семейные обстоятельства")
        assert request_id == 1, f"Ожидался ID 1, получен {request_id}"
        
        # Тест получения заявки
        request = db.get_request(request_id)
        assert request is not None, "Заявка не найдена"
        assert request["user_id"] == 12345, "Неверный user_id"
        assert request["date"] == "2024-12-31", "Неверная дата"
        assert request["reason"] == "семейные обстоятельства", "Неверная причина"
        assert request["status"] == "pending", "Неверный статус"
        
        # Тест обновления статуса
        success = db.update_request_status(request_id, "approved", 566901876)
        assert success, "Не удалось обновить статус"
        
        # Проверяем обновление
        updated_request = db.get_request(request_id)
        assert updated_request["status"] == "approved", "Статус не обновился"
        assert updated_request["processed_by"] == 566901876, "Неверный обработчик"
        
        # Тест получения заявок пользователя
        user_requests = db.get_user_requests(12345)
        assert len(user_requests) == 1, f"Ожидалась 1 заявка, получено {len(user_requests)}"
        
        # Тест получения одобренных заявок
        approved_requests = db.get_all_approved_requests(12345)
        assert len(approved_requests) == 1, f"Ожидалась 1 одобренная заявка, получено {len(approved_requests)}"
        
        print("✅ Все тесты базы данных прошли успешно!")
        
    finally:
        # Удаляем временный файл
        os.unlink(tmp_db_path)

def test_config():
    """Тест конфигурации"""
    print("🧪 Тестирование конфигурации...")
    
    from holidays_config import (
        HOLIDAYS_CHAT_ID,
        HOLIDAYS_THREAD_ID,
        HOLIDAYS_ADMIN_IDS,
        HOLIDAYS_DB_PATH
    )
    
    assert HOLIDAYS_CHAT_ID == -1001956037680, f"Неверный CHAT_ID: {HOLIDAYS_CHAT_ID}"
    assert HOLIDAYS_THREAD_ID == 4, f"Неверный THREAD_ID: {HOLIDAYS_THREAD_ID}"
    assert 566901876 in HOLIDAYS_ADMIN_IDS, f"Admin ID не найден в {HOLIDAYS_ADMIN_IDS}"
    assert HOLIDAYS_DB_PATH.endswith("holidays_db.json"), f"Неверный путь к БД: {HOLIDAYS_DB_PATH}"
    
    print("✅ Конфигурация корректна!")

def test_helper_functions():
    """Тест вспомогательных функций"""
    print("🧪 Тестирование вспомогательных функций...")
    
    from holidays import format_date, format_datetime, get_user_display_name, is_admin
    
    # Тест форматирования даты
    formatted_date = format_date("2024-12-31")
    assert formatted_date == "31.12.2024", f"Неверное форматирование даты: {formatted_date}"
    
    # Тест форматирования даты и времени
    test_datetime = "2024-12-31T15:30:00"
    formatted_datetime = format_datetime(test_datetime)
    assert "31.12.2024 15:30" in formatted_datetime, f"Неверное форматирование времени: {formatted_datetime}"
    
    # Тест получения имени пользователя
    user_data = {"first_name": "Иван", "last_name": "Петров"}
    display_name = get_user_display_name(user_data)
    assert display_name == "Иван Петров", f"Неверное имя: {display_name}"
    
    # Тест проверки администратора
    assert is_admin(566901876), "Admin должен быть распознан"
    assert not is_admin(123456), "Обычный пользователь не должен быть admin"
    
    print("✅ Все вспомогательные функции работают корректно!")

def test_integration():
    """Тест интеграции с ботом"""
    print("🧪 Тестирование интеграции...")
    
    # Создаем фиктивный объект бота для тестирования
    class MockBot:
        def __init__(self):
            self.handlers = []
        
        def message_handler(self, **kwargs):
            def decorator(func):
                self.handlers.append(('message', func, kwargs))
                return func
            return decorator
        
        def callback_query_handler(self, **kwargs):
            def decorator(func):
                self.handlers.append(('callback', func, kwargs))
                return func
            return decorator
    
    mock_bot = MockBot()
    
    from holidays import register_holiday_handlers
    register_holiday_handlers(mock_bot)
    
    # Проверяем, что обработчики зарегистрированы
    assert len(mock_bot.handlers) >= 4, f"Ожидалось минимум 4 обработчика, получено {len(mock_bot.handlers)}"
    
    # Проверяем наличие обработчиков команд
    command_handlers = [h for h in mock_bot.handlers if h[0] == 'message' and 'commands' in h[2]]
    callback_handlers = [h for h in mock_bot.handlers if h[0] == 'callback']
    
    assert len(command_handlers) >= 3, f"Ожидалось минимум 3 команды, получено {len(command_handlers)}"
    assert len(callback_handlers) >= 1, f"Ожидался минимум 1 callback обработчик, получено {len(callback_handlers)}"
    
    print("✅ Интеграция с ботом работает корректно!")

def main():
    """Запуск всех тестов"""
    print("🚀 Запуск тестов модуля учёта выходных...\n")
    
    try:
        test_config()
        test_database_operations()
        test_helper_functions()
        test_integration()
        
        print("\n🎉 Все тесты пройдены успешно!")
        print("✅ Модуль учёта выходных готов к работе!")
        
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())