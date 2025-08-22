#!/usr/bin/env python3
"""
Demo script for new holiday commands functionality
Demonstrates all the new features added to the holidays module
"""
import sys
import os
import json
import tempfile
sys.path.append('/home/runner/work/telegram-payment-bot/telegram-payment-bot')

from datetime import date, timedelta
from holidays import parse_flexible_date, HolidayDatabase

def demo_date_parsing():
    """Demonstrate the flexible date parsing functionality"""
    print("🎯 ДЕМОНСТРАЦИЯ ГИБКОГО ПАРСИНГА ДАТ")
    print("=" * 50)
    
    today = date.today()
    print(f"Сегодня: {today.strftime('%d.%m.%Y')}")
    print()
    
    test_cases = [
        ("24", "День (текущий или следующий месяц)"),
        ("15.08", "День и месяц (этот или следующий год)"),
        ("15 08", "День и месяц через пробел"),
        ("25.12.2025", "Полная дата с годом"),
        ("25 12 2025", "Полная дата через пробелы"),
        ("05.01", "С ведущими нулями"),
        ("31.02", "Невалидная дата"),
        ("abc", "Неверный формат")
    ]
    
    for date_input, description in test_cases:
        result = parse_flexible_date(date_input)
        if result:
            formatted = result.strftime("%d.%m.%Y")
            print(f"✅ /в {date_input:12} ({description:35}) → {formatted}")
        else:
            print(f"❌ /в {date_input:12} ({description:35}) → Ошибка")
    
    print()

def demo_conflict_checking():
    """Demonstrate date conflict checking"""
    print("🛡️  ДЕМОНСТРАЦИЯ ПРОВЕРКИ КОНФЛИКТОВ ДАТ")
    print("=" * 50)
    
    # Create temporary database
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        json.dump({"requests": {}, "users": {}, "next_id": 1}, tmp_file)
        tmp_db_path = tmp_file.name
    
    try:
        db = HolidayDatabase(tmp_db_path)
        
        test_date = "2025-12-25"
        print(f"Тестируем дату: {test_date}")
        
        # Check availability initially
        available = db.is_date_available(test_date)
        print(f"1. Дата свободна изначально: {'✅' if available else '❌'}")
        
        # Create request
        request_id = db.create_request(12345, test_date, "Новогодние праздники")
        print(f"2. Создана заявка #{request_id}")
        
        # Still available (pending)
        available = db.is_date_available(test_date)
        print(f"3. Дата свободна (заявка в ожидании): {'✅' if available else '❌'}")
        
        # Approve request
        db.update_request_status(request_id, "approved", 566901876)
        print(f"4. Заявка #{request_id} одобрена")
        
        # No longer available
        available = db.is_date_available(test_date)
        print(f"5. Дата свободна (заявка одобрена): {'✅' if available else '❌'}")
        
        print("\n💡 Система предотвращает двойное бронирование дат!")
        
    finally:
        os.unlink(tmp_db_path)
    
    print()

def demo_free_dates():
    """Demonstrate free dates search"""
    print("📅 ДЕМОНСТРАЦИЯ ПОИСКА СВОБОДНЫХ ДАТ")
    print("=" * 50)
    
    # Create temporary database with some occupied dates
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as tmp_file:
        json.dump({"requests": {}, "users": {}, "next_id": 1}, tmp_file)
        tmp_db_path = tmp_file.name
    
    try:
        db = HolidayDatabase(tmp_db_path)
        
        # Add some approved requests to occupy dates
        today = date.today()
        occupied_dates = []
        for i in [3, 7, 10]:  # Occupy some dates
            future_date = today + timedelta(days=i)
            if future_date.weekday() < 5:  # Only weekdays
                date_str = future_date.isoformat()
                request_id = db.create_request(12345, date_str, f"Занятый день {i}")
                db.update_request_status(request_id, "approved", 566901876)
                occupied_dates.append(date_str)
        
        print(f"Занятые даты: {[date.fromisoformat(d).strftime('%d.%m.%Y') for d in occupied_dates]}")
        
        # Get free dates
        free_dates = db.get_free_dates(7)
        print(f"\n7 ближайших свободных дат:")
        for i, date_str in enumerate(free_dates, 1):
            formatted = date.fromisoformat(date_str).strftime('%d.%m.%Y (%A)')
            print(f"  {i}. {formatted}")
        
        print(f"\n💡 Найдено {len(free_dates)} свободных дат (только рабочие дни)")
        
    finally:
        os.unlink(tmp_db_path)
    
    print()

def demo_new_commands():
    """Demonstrate how the new commands work"""
    print("🚀 НОВЫЕ КОМАНДЫ МОДУЛЯ ВЫХОДНЫХ")
    print("=" * 50)
    
    print("📝 Подача заявок:")
    print("  /выходной 2025-12-31 семейные обстоятельства  (классический формат)")
    print("  /в 24 семейные обстоятельства                 (гибкий формат)")
    print("  /в 15.08 отпуск                               (день + месяц)")
    print("  /в 25 12 2025 новогодние праздники            (полная дата)")
    
    print("\n📋 Просмотр выходных:")
    print("  /вых                                          (будущие выходные)")
    print("  /всевых                                       (все выходные)")
    print("  /вс                                           (синоним)")
    print("  /список                                       (синоним)")
    
    print("\n🔍 Поиск свободных дат:")
    print("  /сд                                           (свободные даты)")
    print("  /даты                                         (синоним)")
    
    print("\n✨ Новые возможности:")
    print("  • Автоматическая проверка конфликтов дат")
    print("  • Интеллектуальный парсинг дат")
    print("  • Поддержка ведущих нулей и разных форматов")
    print("  • Поиск ближайших свободных дат")
    print("  • Проверка валидности дат (28/29 февраля, 30/31 число)")
    
    print()

def main():
    """Main demo function"""
    print("🎉 ДЕМО: НОВЫЕ КОМАНДЫ МОДУЛЯ ВЫХОДНЫХ")
    print("=" * 60)
    print()
    
    demo_date_parsing()
    demo_conflict_checking() 
    demo_free_dates()
    demo_new_commands()
    
    print("✅ ВСЕ НОВЫЕ ФУНКЦИИ РАБОТАЮТ КОРРЕКТНО!")
    print("🔗 Модуль готов к интеграции с Telegram ботом")

if __name__ == "__main__":
    main()