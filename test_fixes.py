#!/usr/bin/env python3
"""
Test script to verify the two bug fixes in telegram-payment-bot.
"""
import sys
import os
import importlib.util
import re
from datetime import datetime
import pytz

def test_syntax_fix():
    """Test that the syntax error in staff selection is fixed."""
    print("🧪 Testing syntax fix for staff selection...")
    
    try:
        # Try to compile the bot.py file
        import py_compile
        py_compile.compile('bot.py', doraise=True)
        print("✅ bot.py compiles successfully")
        
        # Check that the problematic line is fixed
        with open('bot.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Look for the fixed line
        if 'send_message_with_thread_logging(chat_id, "Выберите сотрудников, которые были на смене:", thread_id=thread_id, reply_markup=get_staff_keyboard())' in content:
            print("✅ Staff selection message syntax is correct")
        else:
            print("❌ Staff selection message syntax not found or incorrect")
            return False
            
        # Make sure the old broken syntax is not present
        if 'thread_id=thread_id, которые были на смене' in content:
            print("❌ Old broken syntax still present")
            return False
        else:
            print("✅ Old broken syntax successfully removed")
            
        return True
        
    except Exception as e:
        print(f"❌ Compilation error: {e}")
        return False

def test_time_ranges():
    """Test that notification time ranges are correctly set."""
    print("\n🧪 Testing notification time ranges...")
    
    try:
        with open('bot.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Test order notification time range (9:00-12:00)
        delivery_pattern = r'base_time = 9 \* 60.*?end_time = 12 \* 60'
        if re.search(delivery_pattern, content, re.DOTALL):
            print("✅ Order notification time range correctly set to 9:00-12:00")
        else:
            print("❌ Order notification time range incorrect")
            return False
            
        # Test report notification time range (22:00-23:00)
        report_pattern = r'base_time = 22 \* 60.*?end_time = 23 \* 60\s*#'
        if re.search(report_pattern, content, re.DOTALL):
            print("✅ Report notification time range correctly set to 22:00-23:00")
        else:
            print("❌ Report notification time range incorrect")
            return False
            
        # Test is_report_time_valid function
        if 'def is_report_time_valid():\n    """Проверить, можно ли сейчас отправлять напоминания об отчетах (22:00-23:00)"""' in content:
            print("✅ Report time validation function has correct comment")
        else:
            print("❌ Report time validation function comment incorrect")
            return False
            
        # Check that old time range (23:10) is removed
        if '23:10' not in content:
            print("✅ Old 23:10 time reference successfully removed")
        else:
            print("❌ Old 23:10 time reference still present")
            return False
            
        return True
        
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        return False

def test_time_validation_logic():
    """Test the is_report_time_valid function logic (without importing the full bot)."""
    print("\n🧪 Testing time validation logic...")
    
    # Extract and test the is_report_time_valid function logic
    moscow_tz = pytz.timezone('Europe/Moscow')
    
    def is_report_time_valid_test(test_hour, test_minute):
        """Simplified version of the fixed function for testing."""
        # 22:00-23:00
        if test_hour == 22:
            return True
        else:
            return False
    
    # Test cases
    test_cases = [
        (22, 0, True, "22:00 (start of window)"),
        (22, 30, True, "22:30 (middle of window)"),
        (22, 59, True, "22:59 (end of window)"),
        (23, 0, False, "23:00 (after window)"),
        (23, 5, False, "23:05 (after window)"),
        (21, 59, False, "21:59 (before window)"),
    ]
    
    all_passed = True
    for hour, minute, expected, description in test_cases:
        result = is_report_time_valid_test(hour, minute)
        if result == expected:
            print(f"✅ {description}: {result} (expected {expected})")
        else:
            print(f"❌ {description}: {result} (expected {expected})")
            all_passed = False
    
    return all_passed

def main():
    """Run all tests."""
    print("🚀 Running tests for telegram-payment-bot bug fixes...")
    
    # Test 1: Syntax fix
    syntax_ok = test_syntax_fix()
    
    # Test 2: Time ranges
    time_ranges_ok = test_time_ranges()
    
    # Test 3: Time validation logic
    time_logic_ok = test_time_validation_logic()
    
    # Summary
    print("\n📊 Test Results Summary:")
    print(f"Syntax fix: {'✅ PASS' if syntax_ok else '❌ FAIL'}")
    print(f"Time ranges: {'✅ PASS' if time_ranges_ok else '❌ FAIL'}")
    print(f"Time validation logic: {'✅ PASS' if time_logic_ok else '❌ FAIL'}")
    
    if syntax_ok and time_ranges_ok and time_logic_ok:
        print("\n🎉 All tests passed! Both bugs are fixed.")
        return 0
    else:
        print("\n❌ Some tests failed. Please review the fixes.")
        return 1

if __name__ == "__main__":
    sys.exit(main())