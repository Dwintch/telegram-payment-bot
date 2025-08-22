#!/usr/bin/env python3
"""
Test thread ID handling in the telegram bot

This test verifies that:
1. User response messages preserve thread_id from incoming messages
2. Automatic messages use configured thread_ids
3. Logging works correctly for all message types
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
import logging
import sys
import os

# Add the current directory to path so we can import bot modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Mock the required external dependencies before importing
sys.modules['telebot'] = Mock()
sys.modules['gspread'] = Mock()
sys.modules['oauth2client.service_account'] = Mock()
sys.modules['requests'] = Mock()
sys.modules['apscheduler.schedulers.background'] = Mock()
sys.modules['apscheduler.triggers.cron'] = Mock()
sys.modules['pytz'] = Mock()

# Mock the environment and credentials
with patch.dict('os.environ', {'BOT_TOKEN': 'test_token'}):
    # Mock the credentials file check
    with patch('os.path.exists', return_value=False):
        # Import after mocking
        import bot
        import holidays

class TestThreadHandling(unittest.TestCase):
    """Test thread ID handling functionality"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock the telebot instance
        self.mock_bot = Mock()
        
        # Create mock message with thread_id
        self.mock_message = Mock()
        self.mock_message.chat.id = 12345
        self.mock_message.text = "test message"
        self.mock_message.message_thread_id = 99
        
        # Create mock message without thread_id
        self.mock_message_no_thread = Mock()
        self.mock_message_no_thread.chat.id = 12345
        self.mock_message_no_thread.text = "test message"
        self.mock_message_no_thread.message_thread_id = None
        
        # Mock the send_message return value
        self.mock_send_result = Mock()
        self.mock_send_result.message_id = 123
        self.mock_bot.send_message.return_value = self.mock_send_result
        
    def test_get_thread_id_from_message(self):
        """Test thread ID extraction from messages"""
        # Test with thread_id
        thread_id = bot.get_thread_id_from_message(self.mock_message)
        self.assertEqual(thread_id, 99)
        
        # Test without thread_id
        thread_id = bot.get_thread_id_from_message(self.mock_message_no_thread)
        self.assertIsNone(thread_id)
        
    @patch('bot.logging')
    def test_send_message_with_thread_logging(self, mock_logging):
        """Test thread-aware message sending with logging"""
        chat_id = 12345
        text = "Test message"
        thread_id = 99
        
        # Call the function
        result = bot.send_message_with_thread_logging(chat_id, text, thread_id=thread_id)
        
        # Verify bot.send_message was called with correct parameters
        self.mock_bot.send_message.assert_called_once_with(chat_id, text, message_thread_id=thread_id)
        
        # Verify logging occurred
        mock_logging.info.assert_called()
        log_calls = [call[0][0] for call in mock_logging.info.call_args_list]
        self.assertTrue(any("thread 99" in call for call in log_calls))
        
    @patch('bot.logging')
    def test_send_message_without_thread_id(self, mock_logging):
        """Test message sending without thread_id"""
        chat_id = 12345
        text = "Test message"
        
        # Call the function without thread_id
        result = bot.send_message_with_thread_logging(chat_id, text, thread_id=None)
        
        # Verify bot.send_message was called without message_thread_id
        self.mock_bot.send_message.assert_called_once_with(chat_id, text)
        
        # Verify logging occurred with "основной чат"
        mock_logging.info.assert_called()
        log_calls = [call[0][0] for call in mock_logging.info.call_args_list]
        self.assertTrue(any("основной чат" in call for call in log_calls))
        
    def test_holidays_get_thread_id_from_message(self):
        """Test thread ID extraction in holidays module"""
        # Test with thread_id
        thread_id = holidays.get_thread_id_from_message(self.mock_message)
        self.assertEqual(thread_id, 99)
        
        # Test without thread_id
        thread_id = holidays.get_thread_id_from_message(self.mock_message_no_thread)
        self.assertIsNone(thread_id)
        
    @patch('holidays.logging')
    def test_holidays_send_message_with_thread_logging(self, mock_logging):
        """Test holidays module thread-aware message sending"""
        chat_id = 12345
        text = "Holiday message"
        thread_id = 4  # HOLIDAYS_THREAD_ID
        
        # Call the function
        result = holidays.send_message_with_thread_logging(self.mock_bot, chat_id, text, thread_id=thread_id)
        
        # Verify bot.send_message was called with correct parameters
        self.mock_bot.send_message.assert_called_once_with(chat_id, text, message_thread_id=thread_id)
        
        # Verify logging with [HOLIDAYS] prefix
        mock_logging.info.assert_called()
        log_calls = [call[0][0] for call in mock_logging.info.call_args_list]
        self.assertTrue(any("[HOLIDAYS]" in call and "thread 4" in call for call in log_calls))
        
    @patch('holidays.logging')
    def test_holidays_reply_to_with_thread_logging(self, mock_logging):
        """Test holidays module reply with thread logging"""
        text = "Reply message"
        
        # Call the function
        result = holidays.reply_to_with_thread_logging(self.mock_bot, self.mock_message, text)
        
        # Verify bot.reply_to was called
        self.mock_bot.reply_to.assert_called_once_with(self.mock_message, text)
        
        # Verify logging with thread info
        mock_logging.info.assert_called()
        log_calls = [call[0][0] for call in mock_logging.info.call_args_list]
        self.assertTrue(any("[HOLIDAYS]" in call and "thread 99" in call for call in log_calls))

class TestConfigConstants(unittest.TestCase):
    """Test that configuration constants are properly defined"""
    
    def test_thread_id_constants(self):
        """Test that thread ID constants exist"""
        self.assertIsNotNone(bot.THREAD_ID_FOR_ORDER)
        self.assertIsNotNone(bot.THREAD_ID_FOR_REPORT)
        self.assertIsNotNone(bot.CHAT_ID_FOR_REPORT)
        
    def test_holidays_constants(self):
        """Test that holidays constants exist"""
        self.assertIsNotNone(holidays.HOLIDAYS_THREAD_ID)
        self.assertIsNotNone(holidays.HOLIDAYS_CHAT_ID)

if __name__ == '__main__':
    # Set up logging to capture test output
    logging.basicConfig(level=logging.INFO)
    
    # Patch the bot instance in our modules for testing
    with patch('bot.bot', new=Mock()) as mock_bot_instance:
        with patch('holidays.bot', new=mock_bot_instance):
            # Run the tests
            unittest.main(verbosity=2)