#!/usr/bin/env python3
"""
Демонстрация функций модуля учёта выходных
"""

import sys
sys.path.append('.')

from holidays_config import HOLIDAYS_CHAT_ID, HOLIDAYS_THREAD_ID, HOLIDAYS_ADMIN_IDS

def print_module_info():
    """Вывод информации о модуле"""
    print("📋 МОДУЛЬ УЧЁТА ВЫХОДНЫХ")
    print("=" * 50)
    print(f"🎯 Работает только в чате: {HOLIDAYS_CHAT_ID}")
    print(f"🧵 И в топике: {HOLIDAYS_THREAD_ID}")
    print(f"👮 Администраторы: {HOLIDAYS_ADMIN_IDS}")
    print()

def print_commands():
    """Вывод доступных команд"""
    print("📝 ДОСТУПНЫЕ КОМАНДЫ:")
    print("=" * 50)
    print("/выходной ГГГГ-ММ-ДД причина - подать заявку на выходной")
    print("  Пример: /выходной 2024-12-31 семейные обстоятельства")
    print()
    print("/вых - показать будущие одобренные выходные")
    print("/всевых - показать все одобренные выходные")
    print()

def print_workflow():
    """Вывод процесса работы"""
    print("🔄 ПРОЦЕСС РАБОТЫ:")
    print("=" * 50)
    print("1. Пользователь подаёт заявку командой /выходной")
    print("2. Система отправляет уведомление администратору")
    print("3. Администратор одобряет или отклоняет заявку")
    print("4. Пользователь получает уведомление о решении")
    print("5. Одобренные заявки можно просмотреть командами /вых и /всевых")
    print()

def print_features():
    """Вывод особенностей модуля"""
    print("✨ ОСОБЕННОСТИ:")
    print("=" * 50)
    print("✅ Полностью изолированный модуль")
    print("✅ Работает только в указанном чате и топике")
    print("✅ Локальная JSON база данных")
    print("✅ Отдельная конфигурация")
    print("✅ Интерактивные кнопки для одобрения/отклонения")
    print("✅ Все сообщения на русском языке")
    print("✅ Production-ready код")
    print()

def main():
    print_module_info()
    print_commands()
    print_workflow()
    print_features()
    
    print("🚀 ИНТЕГРАЦИЯ В bot.py:")
    print("=" * 50)
    print("from holidays import register_holiday_handlers")
    print("register_holiday_handlers(bot)")
    print()
    
    print("💾 ФАЙЛЫ МОДУЛЯ:")
    print("=" * 50)
    print("- holidays_config.py (конфигурация)")
    print("- holidays.py (основная логика)")
    print("- holidays_db.json (база данных)")
    print("- test_holidays.py (тесты)")
    print()

if __name__ == "__main__":
    main()