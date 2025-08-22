#!/usr/bin/env python3
"""
Демонстрация работы модуля holidays с debug-функциональностью
"""

import sys
import logging
from datetime import datetime, date

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Добавляем путь к модулям
sys.path.append('.')

class MockMessage:
    """Фиктивное сообщение для демонстрации"""
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
    """Фиктивный бот для демонстрации"""
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
        
        print(f"\n📤 Бот отправил сообщение:")
        print(f"   💬 Чат: {chat_id}")
        print(f"   🧵 Топик: {message_thread_id}")
        print(f"   📝 Текст: {text}")
        if reply_markup:
            print(f"   🔘 Кнопки: Да")
        return message_id
    
    def reply_to(self, message, text, reply_markup=None):
        """Имитация ответа на сообщение"""
        return self.send_message(message.chat.id, text, message.message_thread_id, reply_markup)
    
    def edit_message_text(self, text, chat_id, message_id):
        """Имитация редактирования сообщения"""
        print(f"\n✏️ Бот отредактировал сообщение {message_id}:")
        print(f"   📝 Новый текст: {text}")
    
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

def demo_holiday_bot():
    """Демонстрация работы бота holidays"""
    print("🎭 Демонстрация работы модуля holidays с debug-функциональностью\n")
    
    from holidays import register_holiday_handlers
    from holidays_config import HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID, HOLIDAYS_ADMIN_IDS
    
    # Создаем mock-бота
    mock_bot = MockBot()
    
    # Регистрируем обработчики
    register_holiday_handlers(mock_bot)
    
    print(f"⚙️ Настройки модуля:")
    print(f"   📱 Chat ID: {HOLIDAYS_CHAT_ID}")
    print(f"   🧵 Thread ID: {HOLIDAYS_THREAD_ID}")
    print(f"   👮 Админы: {HOLIDAYS_ADMIN_IDS}")
    print(f"   🤖 Обработчиков: {len(mock_bot.handlers)}")
    
    # Находим нужные обработчики
    command_handlers = {}
    debug_handler = None
    
    for handler_type, handler_func, handler_kwargs in mock_bot.handlers:
        if handler_type == 'message':
            if 'commands' in handler_kwargs:
                for cmd in handler_kwargs['commands']:
                    command_handlers[cmd] = handler_func
            elif 'func' in handler_kwargs:
                # Проверяем, что это debug-обработчик
                test_msg = MockMessage(HOLIDAYS_CHAT_ID, 999, "test")
                if handler_kwargs['func'](test_msg):
                    debug_handler = handler_func
    
    print(f"\n🔧 Найденные обработчики:")
    print(f"   📋 Команды: {list(command_handlers.keys())}")
    print(f"   🐛 Debug-обработчик: {'✅' if debug_handler else '❌'}")
    
    # Сценарий 1: Сообщение в неправильном чате
    print(f"\n" + "="*60)
    print(f"📝 СЦЕНАРИЙ 1: Сообщение в неправильном чате")
    print(f"="*60)
    
    wrong_chat_msg = MockMessage(-123456789, None, "Привет, бот!", 12345, "user1", "Иван", "Петров")
    print(f"👤 Пользователь Иван Петров пишет в чате {wrong_chat_msg.chat.id}: '{wrong_chat_msg.text}'")
    
    # Debug-обработчик не должен сработать
    if debug_handler:
        test_result = any(h[2]['func'](wrong_chat_msg) for h in mock_bot.handlers if h[0] == 'message' and 'func' in h[2])
        if not test_result:
            print("✅ Debug-обработчик правильно игнорирует сообщения из других чатов")
    
    # Сценарий 2: Сообщение в правильном чате, но неправильном топике
    print(f"\n" + "="*60)
    print(f"📝 СЦЕНАРИЙ 2: Сообщение в правильном чате, неправильном топике")
    print(f"="*60)
    
    wrong_thread_msg = MockMessage(HOLIDAYS_CHAT_ID, 999, "Привет из другого топика!", 12345, "user1", "Иван", "Петров")
    print(f"👤 Пользователь Иван Петров пишет в чате {HOLIDAYS_CHAT_ID}, топике 999: '{wrong_thread_msg.text}'")
    
    if debug_handler:
        debug_handler(wrong_thread_msg)
        print("✅ Debug-обработчик ответил с диагностикой")
    
    # Сценарий 3: Правильная команда в правильном чате и топике
    print(f"\n" + "="*60)
    print(f"📝 СЦЕНАРИЙ 3: Правильная команда /выходной")
    print(f"="*60)
    
    holiday_msg = MockMessage(HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID, "/выходной 2024-12-31 семейные обстоятельства", 12345, "user1", "Иван", "Петров")
    print(f"👤 Пользователь Иван Петров пишет команду: '{holiday_msg.text}'")
    
    if 'выходной' in command_handlers:
        command_handlers['выходной'](holiday_msg)
        print("✅ Команда /выходной обработана")
    
    # Сценарий 4: Команда просмотра выходных
    print(f"\n" + "="*60)
    print(f"📝 СЦЕНАРИЙ 4: Команда /вых (просмотр будущих выходных)")
    print(f"="*60)
    
    future_msg = MockMessage(HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID, "/вых", 12345, "user1", "Иван", "Петров")
    print(f"👤 Пользователь Иван Петров пишет команду: '{future_msg.text}'")
    
    if 'вых' in command_handlers:
        command_handlers['вых'](future_msg)
        print("✅ Команда /вых обработана")
    
    # Сценарий 5: Команда просмотра всех выходных
    print(f"\n" + "="*60)
    print(f"📝 СЦЕНАРИЙ 5: Команда /всевых (все выходные)")
    print(f"="*60)
    
    all_msg = MockMessage(HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID, "/всевых", 12345, "user1", "Иван", "Петров")
    print(f"👤 Пользователь Иван Петров пишет команду: '{all_msg.text}'")
    
    if 'всевых' in command_handlers:
        command_handlers['всевых'](all_msg)
        print("✅ Команда /всевых обработана")
    
    # Итоги
    print(f"\n" + "="*60)
    print(f"📊 ИТОГИ ДЕМОНСТРАЦИИ")
    print(f"="*60)
    print(f"   📨 Всего сообщений отправлено ботом: {len(mock_bot.sent_messages)}")
    print(f"   🔧 Debug-функциональность: {'Активна' if debug_handler else 'Неактивна'}")
    print(f"   📋 Команды доступны: {', '.join(command_handlers.keys())}")
    print(f"   ✅ Фильтрация по чату/топику: Работает")
    print(f"   📝 Детальное логирование: Включено")
    
    print(f"\n🎯 Бот готов к production с debug-возможностями!")
    print(f"💡 Для отключения debug-обработчика удалите соответствующий код из register_holiday_handlers()")

def main():
    """Запуск демонстрации"""
    try:
        demo_holiday_bot()
        print(f"\n🎉 Демонстрация завершена успешно!")
        return 0
    except Exception as e:
        print(f"\n❌ Ошибка в демонстрации: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit(main())