#!/usr/bin/env python3
"""
Конфигурация модуля учёта выходных
"""

import os

# Настройки чата и топика
HOLIDAYS_CHAT_ID = -1001956037680
HOLIDAYS_THREAD_ID = 4

# Администраторы, которые могут подтверждать/отклонять заявки
HOLIDAYS_ADMIN_IDS = [566901876]

# Путь к JSON базе данных
HOLIDAYS_DB_PATH = os.path.join(os.path.dirname(__file__), "holidays_db.json")