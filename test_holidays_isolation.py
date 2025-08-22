#!/usr/bin/env python3
"""
Тест полной изоляции модуля holidays
Проверяет, что обработчики работают ТОЛЬКО в нужном чате/топике
"""

import sys
import logging
from datetime import datetime

# Настройка логирования для теста
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Добавляем путь к модулям
sys.path.append('.')

class MockMessage:
    """Фиктивное сообщение для тестирования"""
    def __init__(self, chat_id, thread_id, text, command=None):
        self.chat = MockChat(chat_id)
        self.message_thread_id = thread_id
        self.text = text
        self.from_user = MockUser(12345)
        self.message_id = 123
        # Эмулируем команду
        if command and text.startswith(f'/{command}'):
            pass  # команда уже в тексте

class MockChat:
    def __init__(self, chat_id):
        self.id = chat_id

class MockUser:
    def __init__(self, user_id):
        self.id = user_id
        self.username = "test_user"
        self.first_name = "Test"
        self.last_name = "User"

class MockBot:
    """Фиктивный бот для тестирования изоляции"""
    def __init__(self):
        self.handlers = []
        self.sent_messages = []
        self.command_handlers = {}
        self.callback_handlers = []
        self.message_handlers = []

    def message_handler(self, commands=None, func=None):
        """Декоратор для регистрации обработчиков сообщений"""
        def decorator(handler_func):
            handler_info = {
                'func': handler_func,
                'commands': commands,
                'filter_func': func,
                'type': 'message'
            }
            self.handlers.append(handler_info)
            self.message_handlers.append(handler_info)
            if commands:
                for cmd in commands:
                    if cmd not in self.command_handlers:
                        self.command_handlers[cmd] = []
                    self.command_handlers[cmd].append(handler_info)
            return handler_func
        return decorator

    def callback_query_handler(self, func=None):
        """Декоратор для регистрации обработчиков коллбэков"""
        def decorator(handler_func):
            handler_info = {
                'func': handler_func,
                'filter_func': func,
                'type': 'callback'
            }
            self.handlers.append(handler_info)
            self.callback_handlers.append(handler_info)
            return handler_func
        return decorator

    def send_message(self, chat_id, text, message_thread_id=None, reply_markup=None, parse_mode=None):
        """Эмулировать отправку сообщения"""
        message_data = {
            'chat_id': chat_id,
            'text': text,
            'message_thread_id': message_thread_id,
            'reply_markup': reply_markup,
            'parse_mode': parse_mode
        }
        self.sent_messages.append(message_data)
        return MockMessage(chat_id, message_thread_id, text)

    def test_message(self, message):
        """Тестировать обработку сообщения"""
        matched_handlers = []
        
        # Проверяем команды
        if message.text.startswith('/'):
            command = message.text.split()[0][1:]  # убираем '/'
            if command in self.command_handlers:
                for handler_info in self.command_handlers[command]:
                    # Проверяем фильтр
                    if handler_info['filter_func'] is None or handler_info['filter_func'](message):
                        matched_handlers.append(handler_info)
                        try:
                            handler_info['func'](message)
                        except Exception as e:
                            print(f"Ошибка в обработчике команды {command}: {e}")
        
        # Проверяем обычные message handlers
        for handler_info in self.message_handlers:
            if handler_info['commands'] is None:  # не командный обработчик
                if handler_info['filter_func'] is None or handler_info['filter_func'](message):
                    matched_handlers.append(handler_info)
                    try:
                        handler_info['func'](message)
                    except Exception as e:
                        print(f"Ошибка в обработчике сообщения: {e}")
        
        return matched_handlers

def test_isolation():
    """Тест изоляции holidays-обработчиков"""
    print("🧪 Тестирование ИЗОЛЯЦИИ модуля holidays...\n")
    
    from holidays import register_holiday_handlers
    from holidays_config import HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID
    
    # Создаем mock-бота
    mock_bot = MockBot()
    
    # Регистрируем обработчики с debug_mode=False (production)
    register_holiday_handlers(mock_bot, debug_mode=False)
    
    print(f"📋 Зарегистрировано {len(mock_bot.handlers)} обработчиков в production mode")
    
    # Тестовые сценарии
    test_cases = [
        {
            "name": "✅ ПРАВИЛЬНЫЙ чат и топик - команда /выходной",
            "message": MockMessage(HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID, "/выходной 2024-12-31 тест"),
            "should_be_processed": True
        },
        {
            "name": "✅ ПРАВИЛЬНЫЙ чат и топик - команда /вых",
            "message": MockMessage(HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID, "/вых"),
            "should_be_processed": True
        },
        {
            "name": "✅ ПРАВИЛЬНЫЙ чат и топик - команда /всевых",
            "message": MockMessage(HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID, "/всевых"),
            "should_be_processed": True
        },
        {
            "name": "❌ НЕПРАВИЛЬНЫЙ топик - команда /выходной",
            "message": MockMessage(HOLIDAYS_CHAT_ID, 999, "/выходной 2024-12-31 тест"),
            "should_be_processed": False
        },
        {
            "name": "❌ НЕПРАВИЛЬНЫЙ чат - команда /выходной",
            "message": MockMessage(-123456789, HOLIDAYS_THREAD_ID, "/выходной 2024-12-31 тест"),
            "should_be_processed": False
        },
        {
            "name": "❌ Личные сообщения - команда /выходной",
            "message": MockMessage(12345, None, "/выходной 2024-12-31 тест"),
            "should_be_processed": False
        },
        {
            "name": "❌ Другая группа - команда /вых",
            "message": MockMessage(-987654321, 4, "/вых"),
            "should_be_processed": False
        },
    ]
    
    # Выполняем тесты
    print("🔍 Результаты тестирования изоляции:\n")
    
    all_passed = True
    for i, test_case in enumerate(test_cases, 1):
        print(f"{i}. {test_case['name']}")
        
        # Сбрасываем счетчики
        initial_messages_count = len(mock_bot.sent_messages)
        
        # Тестируем
        matched_handlers = mock_bot.test_message(test_case['message'])
        
        # Проверяем результат
        messages_sent = len(mock_bot.sent_messages) - initial_messages_count
        handlers_matched = len(matched_handlers)
        
        expected = test_case['should_be_processed']
        actual_processed = handlers_matched > 0
        
        if expected == actual_processed:
            status = "✅ ПРОЙДЕН"
        else:
            status = "❌ ПРОВАЛЕН"
            all_passed = False
        
        print(f"   Ожидалось: {'обработка' if expected else 'игнорирование'}")
        print(f"   Получено: {handlers_matched} обработчиков сработало, {messages_sent} сообщений отправлено")
        print(f"   Статус: {status}\n")
    
    # Проверяем debug mode
    print("🔧 Тестирование debug mode...")
    mock_bot_debug = MockBot()
    register_holiday_handlers(mock_bot_debug, debug_mode=True)
    
    debug_handlers = len(mock_bot_debug.handlers)
    production_handlers = len(mock_bot.handlers)
    
    print(f"   Production mode: {production_handlers} обработчиков")
    print(f"   Debug mode: {debug_handlers} обработчиков")
    
    if debug_handlers > production_handlers:
        print("   ✅ Debug mode добавляет дополнительные обработчики")
    else:
        print("   ❌ Debug mode не отличается от production")
        all_passed = False
    
    # Итоги
    print(f"\n📊 Итоги тестирования изоляции:")
    print(f"   • Всего тестов: {len(test_cases)}")
    print(f"   • Статус: {'✅ Все тесты пройдены' if all_passed else '❌ Есть проваленные тесты'}")
    print(f"   • Production handlers: {production_handlers}")
    print(f"   • Debug handlers: {debug_handlers}")
    
    return all_passed

def main():
    """Запуск всех тестов изоляции"""
    try:
        success = test_isolation()
        
        if success:
            print("\n🎉 Все тесты изоляции пройдены успешно!")
            print("✅ Модуль holidays работает ТОЛЬКО в заданном чате/топике")
            print("✅ В других местах команды holidays полностью игнорируются")
            return 0
        else:
            print("\n❌ Некоторые тесты изоляции провалены!")
            print("⚠️ Изоляция модуля holidays работает не корректно")
            return 1
            
    except Exception as e:
        print(f"\n❌ Ошибка в тестах изоляции: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())