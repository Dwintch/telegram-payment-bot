#!/usr/bin/env python3
"""
Demo script to validate the thread ID fix

This script demonstrates that:
1. Reports now use THREAD_ID_FOR_REPORT (3)
2. Orders continue to use THREAD_ID_FOR_ORDER (64)
"""

import re

def analyze_thread_usage():
    """Analyze thread ID usage in bot.py"""
    
    with open('/home/runner/work/telegram-payment-bot/telegram-payment-bot/bot.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    print("🔍 THREAD ID ANALYSIS AFTER FIX")
    print("=" * 50)
    
    # Constants
    print(f"📋 Constants defined:")
    if 'THREAD_ID_FOR_REPORT = 3' in content:
        print(f"  ✅ THREAD_ID_FOR_REPORT = 3")
    if 'THREAD_ID_FOR_ORDER = 64' in content:
        print(f"  ✅ THREAD_ID_FOR_ORDER = 64")
    
    print()
    
    # Report functions (should use THREAD_ID_FOR_REPORT)
    print("📊 REPORT FUNCTIONS (should use THREAD_ID_FOR_REPORT = 3):")
    report_functions = [
        ('send_delivery_reminder', 'Delivery reminders'),
        ('handle_delivery_callback', 'Delivery completion reports'),
        ('send_report', 'Daily/shift reports')
    ]
    
    for func_name, description in report_functions:
        # Find function content
        pattern = rf'def {func_name}\([^)]*\):.*?(?=def|\Z)'
        match = re.search(pattern, content, re.DOTALL)
        
        if match:
            func_content = match.group(0)
            uses_report_thread = 'thread_id=THREAD_ID_FOR_REPORT' in func_content
            uses_order_thread = 'thread_id=THREAD_ID_FOR_ORDER' in func_content
            
            if uses_report_thread and not uses_order_thread:
                print(f"  ✅ {func_name}(): {description} → THREAD_ID_FOR_REPORT")
            elif uses_order_thread:
                print(f"  ❌ {func_name}(): {description} → THREAD_ID_FOR_ORDER (WRONG!)")
            else:
                print(f"  ⚠️  {func_name}(): {description} → No thread ID found")
    
    print()
    
    # Order functions (should use THREAD_ID_FOR_ORDER)
    print("📦 ORDER FUNCTIONS (should use THREAD_ID_FOR_ORDER = 64):")
    
    # Find send_order function
    pattern = r'def send_order\(chat_id, appended=False\):.*?(?=def|\Z)'
    match = re.search(pattern, content, re.DOTALL)
    
    if match:
        func_content = match.group(0)
        order_count = func_content.count('thread_id=THREAD_ID_FOR_ORDER')
        report_count = func_content.count('thread_id=THREAD_ID_FOR_REPORT')
        
        if order_count > 0 and report_count == 0:
            print(f"  ✅ send_order(): Orders and media → THREAD_ID_FOR_ORDER ({order_count} usages)")
        else:
            print(f"  ⚠️  send_order(): Unexpected thread usage - order:{order_count}, report:{report_count}")
    
    print()
    
    # Overall statistics
    print("📈 OVERALL STATISTICS:")
    total_report_usages = content.count('thread_id=THREAD_ID_FOR_REPORT')
    total_order_usages = content.count('thread_id=THREAD_ID_FOR_ORDER')
    
    print(f"  📊 THREAD_ID_FOR_REPORT usages: {total_report_usages}")
    print(f"  📦 THREAD_ID_FOR_ORDER usages: {total_order_usages}")
    
    print()
    print("🎯 SUMMARY:")
    if total_report_usages == 3:
        print(f"  ✅ Reports correctly use THREAD_ID_FOR_REPORT (3 usages)")
    else:
        print(f"  ❌ Unexpected number of report thread usages: {total_report_usages}")
        
    if total_order_usages >= 10:
        print(f"  ✅ Orders correctly use THREAD_ID_FOR_ORDER ({total_order_usages} usages)")
    else:
        print(f"  ⚠️  Unexpected number of order thread usages: {total_order_usages}")
    
    print()
    print("🎉 FIX VERIFICATION:")
    if total_report_usages == 3 and total_order_usages >= 10:
        print("  ✅ Thread ID fix is SUCCESSFUL!")
        print("  ✅ Reports will go to reports topic (thread 3)")  
        print("  ✅ Orders will go to orders topic (thread 64)")
        return True
    else:
        print("  ❌ Thread ID fix needs review")
        return False

if __name__ == '__main__':
    success = analyze_thread_usage()
    exit(0 if success else 1)