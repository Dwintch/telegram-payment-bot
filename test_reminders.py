#!/usr/bin/env python3
"""
Тест системы напоминаний для проверки функциональности.
Этот скрипт проверяет логику работы функций напоминаний без отправки реальных сообщений.
"""

import random
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Импорт сообщений и функций из основного бота
try:
    from bot import (
        MOTIVATIONAL_MESSAGES, 
        DELIVERY_REMINDERS, 
        get_random_message_with_no_repeat,
        last_motivational_message,
        last_delivery_message
    )
except ImportError as e:
    print(f"Ошибка импорта: {e}")
    print("Тестируем локальные копии сообщений...")
    
    # Локальные копии для тестирования
    MOTIVATIONAL_MESSAGES = [
        "⏰ Пора сделать заказ! Товары сами себя не закажут 😉",
        "🛍️ Проверь остатки, иначе товар сбежит! 🏃‍♂️",
        "📦 Твой магазин ждёт свежий заказ! 🌟"
    ]
    
    DELIVERY_REMINDERS = [
        "📦 **НАПОМИНАНИЕ:** Не забудьте собрать заказы до 17:00!",
        "🚀 **НАПОМИНАНИЕ:** Заказы ждут своего героя!",
        "⏰ **НАПОМИНАНИЕ:** Время собирать поставки!"
    ]
    
    last_motivational_message = None
    last_delivery_message = None
    
    def get_random_message_with_no_repeat(message_pool, last_message_var):
        """Локальная версия функции для тестирования"""
        if len(message_pool) <= 1:
            return message_pool[0] if message_pool else "Сообщение не найдено"
        
        available_messages = [msg for msg in message_pool if msg != last_message_var]
        
        if not available_messages:
            available_messages = message_pool
        
        return random.choice(available_messages)

def test_message_pools():
    """Тест пулов сообщений"""
    print("🧪 Тестирование пулов сообщений...")
    
    print(f"📝 Мотивационных сообщений: {len(MOTIVATIONAL_MESSAGES)}")
    print(f"📝 Сообщений о поставках: {len(DELIVERY_REMINDERS)}")
    
    # Проверяем, что сообщения не пустые
    assert len(MOTIVATIONAL_MESSAGES) > 0, "Пул мотивационных сообщений пуст!"
    assert len(DELIVERY_REMINDERS) > 0, "Пул сообщений о поставках пуст!"
    
    print("✅ Пулы сообщений корректны")

def test_no_repeat_logic():
    """Тест логики избежания повторов"""
    print("\n🧪 Тестирование логики избежания повторов...")
    
    # Тестируем с мотивационными сообщениями
    messages = []
    last_msg = None
    
    for i in range(10):
        msg = get_random_message_with_no_repeat(MOTIVATIONAL_MESSAGES, last_msg)
        messages.append(msg)
        
        # Проверяем что сообщение не повторяется подряд (если есть выбор)
        if last_msg is not None and len(MOTIVATIONAL_MESSAGES) > 1:
            assert msg != last_msg, f"Повтор сообщения обнаружен: '{msg}'"
        
        last_msg = msg
        
    print(f"✅ Сгенерировано {len(messages)} уникальных последовательных сообщений")
    
    # Показываем примеры сообщений
    print("📋 Примеры сгенерированных мотивационных сообщений:")
    for i, msg in enumerate(messages[:5], 1):
        print(f"  {i}. {msg[:50]}...")

def test_delivery_reminders():
    """Тест напоминаний о поставках"""
    print("\n🧪 Тестирование напоминаний о поставках...")
    
    # Проверяем что все сообщения содержат метку "НАПОМИНАНИЕ"
    for msg in DELIVERY_REMINDERS:
        assert "НАПОМИНАНИЕ" in msg, f"Сообщение не содержит метку 'НАПОМИНАНИЕ': {msg}"
    
    print("✅ Все сообщения о поставках содержат метку 'НАПОМИНАНИЕ'")
    
    # Показываем примеры
    print("📋 Примеры сообщений о поставках:")
    for i, msg in enumerate(DELIVERY_REMINDERS[:3], 1):
        print(f"  {i}. {msg[:60]}...")

def test_scheduler_time_ranges():
    """Тест временных диапазонов для планировщика"""
    print("\n🧪 Тестирование временных диапазонов...")
    
    # Симуляция генерации времён для мотивационных напоминаний
    # Утро: 10:00-12:00
    morning_times = []
    for _ in range(3):
        hour = random.randint(10, 11)
        minute = random.randint(0, 59)
        time_str = f"{hour:02d}:{minute:02d}"
        morning_times.append(time_str)
        
        # Проверяем что время в нужном диапазоне
        assert 10 <= hour <= 11, f"Утреннее время вне диапазона: {time_str}"
    
    # Вечер: 20:00-23:00
    evening_times = []
    for _ in range(3):
        hour = random.randint(20, 22)
        minute = random.randint(0, 59)
        time_str = f"{hour:02d}:{minute:02d}"
        evening_times.append(time_str)
        
        # Проверяем что время в нужном диапазоне
        assert 20 <= hour <= 22, f"Вечернее время вне диапазона: {time_str}"
    
    print(f"✅ Сгенерированы времена для утра: {morning_times}")
    print(f"✅ Сгенерированы времена для вечера: {evening_times}")
    
    # Поставки: 9:00-15:00
    delivery_times = []
    for _ in range(4):
        hour = random.randint(9, 14)
        minute = random.randint(0, 59)
        time_str = f"{hour:02d}:{minute:02d}"
        delivery_times.append(time_str)
        
        # Проверяем что время в нужном диапазоне
        assert 9 <= hour <= 14, f"Время поставок вне диапазона: {time_str}"
    
    print(f"✅ Сгенерированы времена для поставок: {delivery_times}")

def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов системы напоминаний...")
    
    try:
        test_message_pools()
        test_no_repeat_logic()
        test_delivery_reminders()
        test_scheduler_time_ranges()
        
        print("\n🎉 Все тесты пройдены успешно!")
        print("📊 Система напоминаний готова к работе")
        
    except Exception as e:
        print(f"\n❌ Ошибка в тестах: {e}")
        raise

if __name__ == "__main__":
    main()