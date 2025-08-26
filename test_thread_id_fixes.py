#!/usr/bin/env python3
"""
Test script to validate that reports use THREAD_ID_FOR_REPORT 
and orders use THREAD_ID_FOR_ORDER
"""

import re
import unittest


class TestThreadIdFixes(unittest.TestCase):
    """Test that the thread ID fixes are correctly implemented"""
    
    def setUp(self):
        """Read the bot.py file for analysis"""
        with open('/home/runner/work/telegram-payment-bot/telegram-payment-bot/bot.py', 'r', encoding='utf-8') as f:
            self.bot_content = f.read()
    
    def test_thread_id_constants_defined(self):
        """Test that both thread ID constants are defined"""
        self.assertIn('THREAD_ID_FOR_REPORT = 3', self.bot_content)
        self.assertIn('THREAD_ID_FOR_ORDER = 64', self.bot_content)
    
    def test_delivery_reminder_uses_report_thread(self):
        """Test that send_delivery_reminder uses THREAD_ID_FOR_REPORT"""
        # Find the send_delivery_reminder function
        pattern = r'def send_delivery_reminder\(\):.*?(?=def|\Z)'
        match = re.search(pattern, self.bot_content, re.DOTALL)
        self.assertIsNotNone(match, "send_delivery_reminder function not found")
        
        function_content = match.group(0)
        
        # Should use THREAD_ID_FOR_REPORT
        self.assertIn('thread_id=THREAD_ID_FOR_REPORT', function_content)
        # Should NOT use THREAD_ID_FOR_ORDER
        self.assertNotIn('thread_id=THREAD_ID_FOR_ORDER', function_content)
    
    def test_delivery_completion_report_uses_report_thread(self):
        """Test that delivery completion report uses THREAD_ID_FOR_REPORT"""
        # Find the handle_delivery_callback function
        pattern = r'def handle_delivery_callback\(call\):.*?(?=def|\Z)'
        match = re.search(pattern, self.bot_content, re.DOTALL)
        self.assertIsNotNone(match, "handle_delivery_callback function not found")
        
        function_content = match.group(0)
        
        # Look for the final_report sending line - should use THREAD_ID_FOR_REPORT
        self.assertIn('send_message_with_thread_logging(CHAT_ID_FOR_REPORT, final_report, thread_id=THREAD_ID_FOR_REPORT)', function_content)
    
    def test_send_report_uses_report_thread(self):
        """Test that send_report uses THREAD_ID_FOR_REPORT"""
        # Find the send_report function
        pattern = r'def send_report\(chat_id\):.*?(?=def|\Z)'
        match = re.search(pattern, self.bot_content, re.DOTALL)
        self.assertIsNotNone(match, "send_report function not found")
        
        function_content = match.group(0)
        
        # Should use THREAD_ID_FOR_REPORT
        self.assertIn('thread_id=THREAD_ID_FOR_REPORT', function_content)
        # Should NOT use THREAD_ID_FOR_ORDER
        self.assertNotIn('thread_id=THREAD_ID_FOR_ORDER', function_content)
    
    def test_send_order_still_uses_order_thread(self):
        """Test that send_order function still uses THREAD_ID_FOR_ORDER"""
        # Find the send_order function
        pattern = r'def send_order\(chat_id, appended=False\):.*?(?=def|\Z)'
        match = re.search(pattern, self.bot_content, re.DOTALL)
        self.assertIsNotNone(match, "send_order function not found")
        
        function_content = match.group(0)
        
        # Should still use THREAD_ID_FOR_ORDER for actual orders
        self.assertIn('thread_id=THREAD_ID_FOR_ORDER', function_content)
        # Count should be multiple occurrences (for orders, photos, videos)
        order_count = function_content.count('thread_id=THREAD_ID_FOR_ORDER')
        self.assertGreater(order_count, 3, "send_order should use THREAD_ID_FOR_ORDER multiple times")
    
    def test_correct_thread_id_distribution(self):
        """Test overall distribution of thread IDs is correct"""
        # Count usages of each thread ID
        report_usages = self.bot_content.count('thread_id=THREAD_ID_FOR_REPORT')
        order_usages = self.bot_content.count('thread_id=THREAD_ID_FOR_ORDER')
        
        # Should have exactly 3 report usages after our fixes
        self.assertEqual(report_usages, 3, f"Expected 3 THREAD_ID_FOR_REPORT usages, found {report_usages}")
        
        # Should have multiple order usages (for the send_order function and related)
        self.assertGreater(order_usages, 5, f"Expected multiple THREAD_ID_FOR_ORDER usages, found {order_usages}")
        
        print(f"✅ THREAD_ID_FOR_REPORT usages: {report_usages}")
        print(f"✅ THREAD_ID_FOR_ORDER usages: {order_usages}")
    
    def test_specific_functions_identified(self):
        """Test that the specific functions we identified are correctly fixed"""
        expected_report_functions = [
            'send_delivery_reminder',  # Delivery reminders
            'handle_delivery_callback',  # Delivery completion reports  
            'send_report'  # Daily/shift reports
        ]
        
        for func_name in expected_report_functions:
            # Find function and check it uses THREAD_ID_FOR_REPORT
            pattern = rf'def {func_name}\([^)]*\):.*?(?=def|\Z)'
            match = re.search(pattern, self.bot_content, re.DOTALL)
            self.assertIsNotNone(match, f"Function {func_name} not found")
            
            function_content = match.group(0)
            self.assertIn('THREAD_ID_FOR_REPORT', function_content, 
                         f"Function {func_name} should use THREAD_ID_FOR_REPORT")


if __name__ == '__main__':
    unittest.main(verbosity=2)