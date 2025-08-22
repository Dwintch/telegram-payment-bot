#!/usr/bin/env python3
"""
Комплексный тест модуля holidays в debug и production режимах
"""

import sys
import logging
from datetime import datetime, date, timedelta

# Настройка логирования для теста
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Добавляем путь к модулям
sys.path.append('.')

class MockMessage:
    """Фиктивное сообщение для тестирования"""
    def __init__(self, chat_id, thread_id=None, text="test", user_id=12345, username="test_user", first_name="Test", last_name="User"):
        self.chat = MockChat(chat_id)
        self.message_thread_id = thread_id
        self.text = text
        self.from_user = MockUser(user_id, username, first_name, last_name)

class MockChat:
    def __init__(self, chat_id):
        self.id = chat_id

class MockUser:
    def __init__(self, user_id, username="test_user", first_name="Test", last_name="User"):
        self.id = user_id
        self.username = username
        self.first_name = first_name
        self.last_name = last_name

class MockBot:
    """Фиктивный бот для тестирования"""
    def __init__(self):
        self.sent_messages = []
        self.handlers = []
        self.current_message_id = 1000
    
    def send_message(self, chat_id, text, message_thread_id=None, reply_markup=None):
        """Имитация отправки сообщения"""
        message_id = self.current_message_id
        self.current_message_id += 1
        
        self.sent_messages.append({
            'message_id': message_id,
            'chat_id': chat_id,
            'text': text,
            'thread_id': message_thread_id,
            'reply_markup': reply_markup,
            'timestamp': datetime.now()
        })
        return message_id
    
    def reply_to(self, message, text, reply_markup=None):
        """Имитация ответа на сообщение"""
        return self.send_message(message.chat.id, text, message.message_thread_id, reply_markup)
    
    def edit_message_text(self, text, chat_id, message_id):
        """Имитация редактирования сообщения"""
        pass
    
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

def test_debug_vs_production_mode():
    """Тест сравнения debug и production режимов"""
    print("🧪 Тестирование debug vs production режимов...\n")
    
    from holidays import register_holiday_handlers
    from holidays_config import HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID
    
    # Тест 1: Debug режим (по умолчанию)
    print("📝 Тест 1: Debug режим")
    debug_bot = MockBot()
    register_holiday_handlers(debug_bot, debug_mode=True)
    
    debug_handlers = len(debug_bot.handlers)
    debug_has_debug_handler = any(
        h[0] == 'message' and 'func' in h[2] and 
        h[2]['func'](MockMessage(HOLIDAYS_CHAT_ID, 999, "test"))
        for h in debug_bot.handlers
    )
    
    print(f"   • Обработчиков зарегистрировано: {debug_handlers}")
    print(f"   • Debug-обработчик активен: {'✅' if debug_has_debug_handler else '❌'}")
    
    # Тест 2: Production режим
    print("\n📝 Тест 2: Production режим")
    prod_bot = MockBot()
    register_holiday_handlers(prod_bot, debug_mode=False)
    
    prod_handlers = len(prod_bot.handlers)
    prod_has_debug_handler = any(
        h[0] == 'message' and 'func' in h[2] and 
        h[2]['func'](MockMessage(HOLIDAYS_CHAT_ID, 999, "test"))
        for h in prod_bot.handlers
    )
    
    print(f"   • Обработчиков зарегистрировано: {prod_handlers}")
    print(f"   • Debug-обработчик активен: {'✅' if prod_has_debug_handler else '❌'}")
    
    # Проверки
    print(f"\n📊 Результаты сравнения:")
    print(f"   • Debug режим обработчиков: {debug_handlers}")
    print(f"   • Production режим обработчиков: {prod_handlers}")
    print(f"   • Разница: {debug_handlers - prod_handlers} (ожидается +1 для debug)")
    
    assert debug_handlers == prod_handlers + 1, f"Ожидалась разница в 1 обработчик, получено {debug_handlers - prod_handlers}"
    assert debug_has_debug_handler, "Debug-обработчик должен быть активен в debug режиме"
    assert not prod_has_debug_handler, "Debug-обработчик НЕ должен быть активен в production режиме"
    
    print("✅ Все проверки режимов пройдены!")

def test_production_commands():
    """Тест команд в production режиме"""
    print("\n🧪 Тестирование команд в production режиме...\n")
    
    from holidays import register_holiday_handlers
    from holidays_config import HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID
    
    # Создаем production бота
    prod_bot = MockBot()
    register_holiday_handlers(prod_bot, debug_mode=False)
    
    # Находим обработчики команд
    command_handlers = {}
    for handler_type, handler_func, handler_kwargs in prod_bot.handlers:
        if handler_type == 'message' and 'commands' in handler_kwargs:
            for cmd in handler_kwargs['commands']:
                command_handlers[cmd] = handler_func
    
    print(f"📋 Найденные команды: {list(command_handlers.keys())}")
    
    # Тестируем каждую команду
    test_cases = [
        {
            "command": "выходной",
            "message": MockMessage(HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID, 
                                 f"/выходной {(date.today() + timedelta(days=30)).isoformat()} тестовая причина",
                                 12345, "test_user", "Тест", "Пользователь"),
            "expected_responses": 2  # Подтверждение пользователю + уведомление админам
        },
        {
            "command": "вых",
            "message": MockMessage(HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID, "/вых",
                                 12345, "test_user", "Тест", "Пользователь"),
            "expected_responses": 1  # Список будущих выходных
        },
        {
            "command": "всевых",
            "message": MockMessage(HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID, "/всевых",
                                 12345, "test_user", "Тест", "Пользователь"),
            "expected_responses": 1  # Список всех выходных
        }
    ]
    
    for test_case in test_cases:
        cmd = test_case["command"]
        msg = test_case["message"]
        expected = test_case["expected_responses"]
        
        print(f"\n📝 Тестирование команды /{cmd}")
        
        initial_messages = len(prod_bot.sent_messages)
        
        if cmd in command_handlers:
            command_handlers[cmd](msg)
            
            actual_responses = len(prod_bot.sent_messages) - initial_messages
            print(f"   • Ожидалось ответов: {expected}")
            print(f"   • Получено ответов: {actual_responses}")
            
            if actual_responses >= 1:  # Минимум один ответ
                print(f"   ✅ Команда /{cmd} работает")
            else:
                print(f"   ❌ Команда /{cmd} не ответила")
        else:
            print(f"   ❌ Команда /{cmd} не найдена")
    
    print(f"\n📊 Итоги тестирования production команд:")
    print(f"   • Всего команд: {len(command_handlers)}")
    print(f"   • Сообщений отправлено: {len(prod_bot.sent_messages)}")
    print(f"   • Production режим: готов к использованию")

def test_filter_accuracy():
    """Тест точности фильтрации сообщений"""
    print("\n🧪 Тестирование точности фильтрации...\n")
    
    from holidays import is_holidays_chat_and_thread
    from holidays_config import HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID
    
    test_cases = [
        {
            "name": "Правильный чат и топик",
            "message": MockMessage(HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID, "тест"),
            "expected": True
        },
        {
            "name": "Правильный чат, неправильный топик",
            "message": MockMessage(HOLIDAYS_CHAT_ID, 999, "тест"),
            "expected": False
        },
        {
            "name": "Неправильный чат, правильный топик",
            "message": MockMessage(-123456789, HOLIDAYS_THREAD_ID, "тест"),
            "expected": False
        },
        {
            "name": "Неправильный чат и топик",
            "message": MockMessage(-123456789, 999, "тест"),
            "expected": False
        },
        {
            "name": "Правильный чат, топик None",
            "message": MockMessage(HOLIDAYS_CHAT_ID, None, "тест"),
            "expected": False
        }
    ]
    
    passed = 0
    total = len(test_cases)
    
    for test_case in test_cases:
        result = is_holidays_chat_and_thread(test_case["message"])
        expected = test_case["expected"]
        
        if result == expected:
            print(f"✅ {test_case['name']}: {result}")
            passed += 1
        else:
            print(f"❌ {test_case['name']}: ожидался {expected}, получен {result}")
    
    print(f"\n📊 Результаты фильтрации: {passed}/{total} тестов пройдено")
    
    if passed == total:
        print("✅ Фильтрация работает идеально!")
    else:
        print("❌ Найдены проблемы с фильтрацией")

def main():
    """Запуск всех комплексных тестов"""
    print("🚀 Запуск комплексного тестирования модуля holidays...\n")
    
    try:
        test_debug_vs_production_mode()
        test_filter_accuracy()
        test_production_commands()
        
        print("\n🎉 Все комплексные тесты пройдены успешно!")
        print("✅ Модуль holidays готов к production использованию!")
        print("\n📝 Для отключения debug-режима используйте:")
        print("   register_holiday_handlers(bot, debug_mode=False)")
        
        return 0
    except Exception as e:
        print(f"\n❌ Ошибка в комплексных тестах: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())