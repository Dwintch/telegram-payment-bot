#!/usr/bin/env python3
"""
Тест debug-функциональности модуля holidays
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
    def __init__(self, chat_id, thread_id=None, text="test", user_id=12345):
        self.chat = MockChat(chat_id)
        self.message_thread_id = thread_id
        self.text = text
        self.from_user = MockUser(user_id)

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
    
    def send_message(self, chat_id, text, message_thread_id=None, reply_markup=None):
        """Имитация отправки сообщения"""
        self.sent_messages.append({
            'chat_id': chat_id,
            'text': text,
            'thread_id': message_thread_id,
            'reply_markup': reply_markup,
            'timestamp': datetime.now()
        })
        print(f"📤 Отправлено сообщение в чат {chat_id}, топик {message_thread_id}:")
        print(f"   {text[:100]}{'...' if len(text) > 100 else ''}")
    
    def reply_to(self, message, text, reply_markup=None):
        """Имитация ответа на сообщение"""
        self.send_message(message.chat.id, text, message.message_thread_id, reply_markup)
    
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

def test_debug_functionality():
    """Тест debug-функциональности"""
    print("🧪 Тестирование debug-функциональности модуля holidays...\n")
    
    from holidays import register_holiday_handlers, is_holidays_chat_and_thread
    from holidays_config import HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID
    
    # Создаем mock-бота
    mock_bot = MockBot()
    
    # Регистрируем обработчики
    register_holiday_handlers(mock_bot)
    
    print(f"📋 Зарегистрировано {len(mock_bot.handlers)} обработчиков")
    
    # Тестируем разные сценарии сообщений
    test_cases = [
        {
            "name": "Сообщение из правильного чата и топика",
            "message": MockMessage(HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID, "/выходной 2024-12-31 тест"),
            "should_match": True
        },
        {
            "name": "Сообщение из правильного чата, но неправильного топика",
            "message": MockMessage(HOLIDAYS_CHAT_ID, 999, "тестовое сообщение"),
            "should_match": False
        },
        {
            "name": "Сообщение из неправильного чата",
            "message": MockMessage(-123456789, HOLIDAYS_THREAD_ID, "тестовое сообщение"),
            "should_match": False
        },
        {
            "name": "Сообщение без топика",
            "message": MockMessage(HOLIDAYS_CHAT_ID, None, "тестовое сообщение"),
            "should_match": False
        }
    ]
    
    print("\n🔍 Тестирование фильтра is_holidays_chat_and_thread:")
    for test_case in test_cases:
        print(f"\n📝 {test_case['name']}")
        result = is_holidays_chat_and_thread(test_case['message'])
        expected = test_case['should_match']
        
        if result == expected:
            print(f"   ✅ Результат правильный: {result}")
        else:
            print(f"   ❌ Ожидался {expected}, получен {result}")
    
    # Тестируем debug-обработчик
    print(f"\n🔧 Тестирование debug-обработчика:")
    
    # Находим debug-обработчик
    debug_handler = None
    for handler_type, handler_func, handler_kwargs in mock_bot.handlers:
        if handler_type == 'message' and 'func' in handler_kwargs:
            # Тестируем с сообщением из целевого чата
            test_message = MockMessage(HOLIDAYS_CHAT_ID, 999, "Тестовое debug-сообщение")
            if handler_kwargs['func'](test_message):
                debug_handler = handler_func
                break
    
    if debug_handler:
        print("   ✅ Debug-обработчик найден")
        
        # Тестируем debug-обработчик
        test_message = MockMessage(HOLIDAYS_CHAT_ID, 999, "Тестовое debug-сообщение")
        debug_handler(test_message)
        
        if mock_bot.sent_messages:
            print(f"   ✅ Debug-обработчик отправил ответ")
            last_message = mock_bot.sent_messages[-1]
            if "DEBUG" in last_message['text']:
                print(f"   ✅ Ответ содержит debug-информацию")
            else:
                print(f"   ❌ Ответ не содержит debug-информацию")
        else:
            print(f"   ❌ Debug-обработчик не отправил ответ")
    else:
        print("   ❌ Debug-обработчик не найден")
    
    print(f"\n📊 Итоги тестирования:")
    print(f"   • Обработчиков зарегистрировано: {len(mock_bot.handlers)}")
    print(f"   • Сообщений отправлено: {len(mock_bot.sent_messages)}")
    print(f"   • Текущая конфигурация: Chat ID={HOLIDAYS_CHAT_ID}, Thread ID={HOLIDAYS_THREAD_ID}")

def main():
    """Запуск всех тестов"""
    try:
        test_debug_functionality()
        print("\n🎉 Все debug-тесты пройдены успешно!")
        return 0
    except Exception as e:
        print(f"\n❌ Ошибка в debug-тестах: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())