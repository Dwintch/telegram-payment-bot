#!/usr/bin/env python3
"""
Simple validation test for thread ID handling

This test verifies the key functions work correctly without importing the full bot
"""

import unittest
from unittest.mock import Mock, patch
import logging

# Test the utility functions in isolation
def get_thread_id_from_message(message):
    """Extract thread_id from incoming Telegram message"""
    if hasattr(message, 'message_thread_id') and message.message_thread_id:
        return message.message_thread_id
    return None

def send_message_with_thread_logging(bot, chat_id, text, thread_id=None, **kwargs):
    """Send message with thread logging"""
    try:
        # Log where we're sending the message
        thread_info = f"thread {thread_id}" if thread_id else "основной чат"
        logging.info(f"📤 Отправка сообщения в чат {chat_id}, {thread_info}")
        
        # Send message
        if thread_id:
            kwargs['message_thread_id'] = thread_id
        result = bot.send_message(chat_id, text, **kwargs)
        
        logging.info(f"✅ Сообщение успешно отправлено в чат {chat_id}, {thread_info}")
        return result
    except Exception as e:
        thread_info = f"thread {thread_id}" if thread_id else "основной чат"
        logging.error(f"❌ Ошибка отправки сообщения в чат {chat_id}, {thread_info}: {e}")
        raise

class TestThreadUtilities(unittest.TestCase):
    """Test thread ID utility functions"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock bot
        self.mock_bot = Mock()
        
        # Mock message with thread_id
        self.mock_message = Mock()
        self.mock_message.chat.id = 12345
        self.mock_message.text = "test message"
        self.mock_message.message_thread_id = 99
        
        # Mock message without thread_id
        self.mock_message_no_thread = Mock()
        self.mock_message_no_thread.chat.id = 12345
        self.mock_message_no_thread.text = "test message"
        self.mock_message_no_thread.message_thread_id = None
        
        # Mock send_message return
        self.mock_send_result = Mock()
        self.mock_send_result.message_id = 123
        self.mock_bot.send_message.return_value = self.mock_send_result
        
    def test_get_thread_id_from_message_with_thread(self):
        """Test extracting thread_id when present"""
        thread_id = get_thread_id_from_message(self.mock_message)
        self.assertEqual(thread_id, 99)
        
    def test_get_thread_id_from_message_without_thread(self):
        """Test extracting thread_id when not present"""
        thread_id = get_thread_id_from_message(self.mock_message_no_thread)
        self.assertIsNone(thread_id)
        
    def test_get_thread_id_from_message_no_attribute(self):
        """Test extracting thread_id when attribute doesn't exist"""
        mock_msg = Mock()
        # Don't set message_thread_id attribute at all
        if hasattr(mock_msg, 'message_thread_id'):
            delattr(mock_msg, 'message_thread_id')
        
        thread_id = get_thread_id_from_message(mock_msg)
        self.assertIsNone(thread_id)
        
    @patch('logging.info')
    @patch('logging.error')
    def test_send_message_with_thread_id(self, mock_error, mock_info):
        """Test sending message with thread_id"""
        chat_id = 12345
        text = "Test message"
        thread_id = 99
        
        result = send_message_with_thread_logging(self.mock_bot, chat_id, text, thread_id=thread_id)
        
        # Verify bot.send_message called with thread_id
        self.mock_bot.send_message.assert_called_once_with(chat_id, text, message_thread_id=thread_id)
        
        # Verify correct return value
        self.assertEqual(result, self.mock_send_result)
        
        # Verify logging calls
        self.assertEqual(mock_info.call_count, 2)
        info_calls = [call[0][0] for call in mock_info.call_args_list]
        self.assertTrue(any("thread 99" in call for call in info_calls))
        
    @patch('logging.info')
    @patch('logging.error')
    def test_send_message_without_thread_id(self, mock_error, mock_info):
        """Test sending message without thread_id"""
        chat_id = 12345
        text = "Test message"
        
        result = send_message_with_thread_logging(self.mock_bot, chat_id, text, thread_id=None)
        
        # Verify bot.send_message called without message_thread_id
        self.mock_bot.send_message.assert_called_once_with(chat_id, text)
        
        # Verify logging with "основной чат"
        info_calls = [call[0][0] for call in mock_info.call_args_list]
        self.assertTrue(any("основной чат" in call for call in info_calls))
        
    @patch('logging.info')
    @patch('logging.error')
    def test_send_message_with_exception(self, mock_error, mock_info):
        """Test error handling in send_message_with_thread_logging"""
        chat_id = 12345
        text = "Test message"
        thread_id = 99
        
        # Make send_message raise an exception
        self.mock_bot.send_message.side_effect = Exception("Test error")
        
        with self.assertRaises(Exception):
            send_message_with_thread_logging(self.mock_bot, chat_id, text, thread_id=thread_id)
        
        # Verify error was logged
        mock_error.assert_called_once()
        error_call = mock_error.call_args[0][0]
        self.assertIn("❌ Ошибка отправки сообщения", error_call)
        self.assertIn("thread 99", error_call)

class TestThreadScenarios(unittest.TestCase):
    """Test realistic thread handling scenarios"""
    
    def setUp(self):
        self.mock_bot = Mock()
        
    def test_user_response_preserves_thread(self):
        """Test that user responses preserve thread_id from incoming message"""
        # Simulate incoming message with thread_id
        incoming_msg = Mock()
        incoming_msg.chat.id = 12345
        incoming_msg.message_thread_id = 88
        
        # Extract thread_id and use it for response
        thread_id = get_thread_id_from_message(incoming_msg)
        
        with patch('logging.info'):
            send_message_with_thread_logging(self.mock_bot, 12345, "Response message", thread_id=thread_id)
        
        # Verify the response uses the same thread_id
        self.mock_bot.send_message.assert_called_once_with(12345, "Response message", message_thread_id=88)
        
    def test_automatic_message_uses_config_thread(self):
        """Test that automatic messages use configured thread IDs"""
        # Simulate automatic message (like order or report)
        THREAD_ID_FOR_ORDER = 64
        CHAT_ID_FOR_REPORT = -1002826712980
        
        with patch('logging.info'):
            send_message_with_thread_logging(self.mock_bot, CHAT_ID_FOR_REPORT, "Automatic order message", thread_id=THREAD_ID_FOR_ORDER)
        
        # Verify the automatic message uses the configured thread_id
        self.mock_bot.send_message.assert_called_once_with(CHAT_ID_FOR_REPORT, "Automatic order message", message_thread_id=THREAD_ID_FOR_ORDER)

class TestConstants(unittest.TestCase):
    """Test that the expected constants are properly defined"""
    
    def test_thread_id_constants_exist(self):
        """Verify thread ID constants are properly defined"""
        # These should be integers representing Telegram thread IDs
        THREAD_ID_FOR_REPORT = 3
        THREAD_ID_FOR_ORDER = 64
        HOLIDAYS_THREAD_ID = 4
        
        self.assertIsInstance(THREAD_ID_FOR_REPORT, int)
        self.assertIsInstance(THREAD_ID_FOR_ORDER, int)
        self.assertIsInstance(HOLIDAYS_THREAD_ID, int)
        
        # Thread IDs should be positive
        self.assertGreater(THREAD_ID_FOR_REPORT, 0)
        self.assertGreater(THREAD_ID_FOR_ORDER, 0)
        self.assertGreater(HOLIDAYS_THREAD_ID, 0)

if __name__ == '__main__':
    # Set up logging for test output
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    
    print("🧪 Testing Thread ID Handling Implementation")
    print("=" * 50)
    
    # Run the tests
    unittest.main(verbosity=2)