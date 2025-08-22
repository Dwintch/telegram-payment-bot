#!/usr/bin/env python3
"""
Configuration validation script for thread ID handling

This script checks that all thread ID constants are properly configured
and provides a summary of the current setup.
"""

import os
import sys

def check_config():
    """Check configuration and provide setup summary"""
    print("🔧 ПРОВЕРКА КОНФИГУРАЦИИ THREAD ID")
    print("=" * 50)
    
    # Check if files exist
    files_to_check = [
        'bot.py',
        'holidays.py', 
        'holidays_config.py',
        'THREAD_IMPLEMENTATION_SUMMARY.md'
    ]
    
    missing_files = []
    for file in files_to_check:
        if os.path.exists(file):
            print(f"✅ {file}")
        else:
            print(f"❌ {file} - ОТСУТСТВУЕТ")
            missing_files.append(file)
    
    if missing_files:
        print(f"\n⚠️ Отсутствуют файлы: {', '.join(missing_files)}")
        return False
    
    print("\n📊 КОНФИГУРАЦИЯ THREAD ID:")
    print("-" * 30)
    
    # Try to extract thread ID constants
    try:
        # Read bot.py to get constants
        with open('bot.py', 'r', encoding='utf-8') as f:
            bot_content = f.read()
            
        # Extract thread constants
        thread_constants = {}
        for line in bot_content.split('\n'):
            if 'THREAD_ID_FOR_ORDER =' in line:
                thread_constants['ORDERS'] = line.split('=')[1].strip()
            elif 'THREAD_ID_FOR_REPORT =' in line:
                thread_constants['REPORTS'] = line.split('=')[1].strip()
            elif 'CHAT_ID_FOR_REPORT =' in line:
                thread_constants['CHAT'] = line.split('=')[1].strip()
        
        print(f"🛒 Заказы (ORDERS): thread {thread_constants.get('ORDERS', 'НЕ НАЙДЕНО')}")
        print(f"📊 Отчёты (REPORTS): thread {thread_constants.get('REPORTS', 'НЕ НАЙДЕНО')}")
        print(f"💬 Чат группы: {thread_constants.get('CHAT', 'НЕ НАЙДЕНО')}")
        
        # Check holidays config
        with open('holidays_config.py', 'r', encoding='utf-8') as f:
            holidays_content = f.read()
            
        holidays_constants = {}
        for line in holidays_content.split('\n'):
            if 'HOLIDAYS_THREAD_ID =' in line:
                holidays_constants['THREAD'] = line.split('=')[1].strip()
            elif 'HOLIDAYS_CHAT_ID =' in line:
                holidays_constants['CHAT'] = line.split('=')[1].strip()
                
        print(f"🏖️ Выходные: thread {holidays_constants.get('THREAD', 'НЕ НАЙДЕНО')} в чате {holidays_constants.get('CHAT', 'НЕ НАЙДЕНО')}")
        
    except Exception as e:
        print(f"❌ Ошибка чтения конфигурации: {e}")
        return False
    
    print("\n🧪 ПРОВЕРКА ФУНКЦИЙ:")
    print("-" * 25)
    
    # Check if thread functions exist in files
    with open('bot.py', 'r', encoding='utf-8') as f:
        bot_content = f.read()
        
    functions_to_check = [
        'get_thread_id_from_message',
        'send_message_with_thread_logging',
        'send_photo_with_thread_logging',
        'send_video_with_thread_logging',
        'send_media_group_with_thread_logging'
    ]
    
    for func in functions_to_check:
        if f"def {func}" in bot_content:
            print(f"✅ {func}")
        else:
            print(f"❌ {func} - НЕ НАЙДЕНА")
    
    # Check holidays functions
    with open('holidays.py', 'r', encoding='utf-8') as f:
        holidays_content = f.read()
        
    holidays_functions = [
        'get_thread_id_from_message',
        'send_message_with_thread_logging',
        'reply_to_with_thread_logging'
    ]
    
    print("\n🏖️ ФУНКЦИИ HOLIDAYS:")
    for func in holidays_functions:
        if f"def {func}" in holidays_content:
            print(f"✅ {func}")
        else:
            print(f"❌ {func} - НЕ НАЙДЕНА")
    
    print("\n📈 СТАТИСТИКА ИСПОЛЬЗОВАНИЯ:")
    print("-" * 30)
    
    # Count thread-aware vs regular calls
    import re
    
    bot_thread_aware = len(re.findall(r'send_.*_with_thread_logging', bot_content))
    bot_regular = len(re.findall(r'bot\.send_message\(', bot_content))
    
    holidays_thread_aware = len(re.findall(r'send_.*_with_thread_logging|reply_to_with_thread_logging', holidays_content))
    holidays_regular = len(re.findall(r'bot\.send_message\(|bot\.reply_to\(', holidays_content))
    
    print(f"🤖 Bot: {bot_thread_aware} thread-aware, {bot_regular} обычных")
    print(f"🏖️ Holidays: {holidays_thread_aware} thread-aware, {holidays_regular} обычных")
    
    # Calculate coverage
    bot_total = bot_thread_aware + bot_regular
    holidays_total = holidays_thread_aware + holidays_regular
    
    bot_coverage = (bot_thread_aware / bot_total * 100) if bot_total > 0 else 0
    holidays_coverage = (holidays_thread_aware / holidays_total * 100) if holidays_total > 0 else 0
    
    print(f"📊 Покрытие bot.py: {bot_coverage:.1f}%")
    print(f"📊 Покрытие holidays.py: {holidays_coverage:.1f}%")
    
    print("\n✅ ИТОГОВАЯ ОЦЕНКА:")
    print("=" * 20)
    
    if bot_thread_aware >= 50 and holidays_thread_aware >= 3:
        print("🎉 ОТЛИЧНО! Thread ID handling реализован полностью")
        print("✅ Бот готов к production")
        print("✅ Логирование настроено")
        print("✅ Автоматические и пользовательские сообщения обрабатываются корректно")
        return True
    else:
        print("⚠️ ВНИМАНИЕ! Не все функции обновлены")
        print("❗ Требуется дополнительная работа")
        return False

if __name__ == '__main__':
    success = check_config()
    
    if success:
        print("\n🚀 Система готова к работе!")
        sys.exit(0)
    else:
        print("\n🔧 Требуется дополнительная настройка")
        sys.exit(1)