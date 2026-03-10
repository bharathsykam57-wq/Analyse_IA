"""Analyse_IA backend package — Centralized logging configuration.

LOGGING ARCHITECTURE:
This module configures centralized logging for all backend modules using Python's logging framework.
All backend operations write to both console and rotating file logs for debugging and monitoring.

LOGGER HIERARCHY:
- Root logger: 'backend' (all backend modules inherit from this)
- Child loggers: 'backend.engines.analysis', 'backend.api', etc.
- Console output: INFO level and above (user-visible status messages)
- File output: DEBUG level and above (detailed diagnostic information)
- Max file size: 5MB per file with 3 backup files retained (15MB total storage)

LOG FILE LOCATION: logs/analyse_ia.log

HANDLER CONFIGURATION:
1. RotatingFileHandler: Persistent disk logging with automatic rotation to manage storage
2. StreamHandler: Real-time console logging for immediate visibility

USAGE PATTERN:
  from backend import logging
  logger = logging.getLogger('backend.engines.analysis')  # Creates child logger
  logger.info('Analysis started')
  logger.debug('Detailed debug info')

FEATURES:
- Duplicate handler prevention: Clears existing handlers on reinit to avoid duplicate messages
- Non-propagating: Prevents logs from bubbling to root logger (avoids duplication)
- UTF-8 encoding: Supports international characters and special symbols
- Consistent formatting: All messages follow same format for easy parsing and searching
"""
import logging
import os
from logging.handlers import RotatingFileHandler

os.makedirs('logs', exist_ok=True)

# FILE HANDLER — Rotating file handler for persistent audit trail
# maxBytes=5MB: Each log file is capped at 5 megabytes to prevent unbounded growth
# backupCount=3: Keep up to 3 rotated backups (analyse_ia.log.1, .log.2, .log.3)
# This strategy maintains historical logs while preventing disk space issues
file_handler = RotatingFileHandler(
    'logs/analyse_ia.log',
    maxBytes=5 * 1024 * 1024,  # 5 megabytes per file
    backupCount=3,  # 3 backup files = 15MB total capacity
    encoding='utf-8'  # Support for international characters
)
file_handler.setLevel(logging.DEBUG)  # File receives all DEBUG and above (most verbose)

# CONSOLE HANDLER — Stream handler for real-time feedback
# StreamHandler defaults to stderr (standard for logging frameworks)
# INFO level keeps console output readable while capturing important events
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)  # Console receives INFO and above (less verbose)

# LOG MESSAGE FORMATTER — Consistent format for all messages
# Shows: timestamp | severity | module_name | message
# This format enables easy grep'ing and correlation of events across logs
formatter = logging.Formatter(
    '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
)
file_handler.setFormatter(formatter)
console_handler.setFormatter(formatter)

# ROOT LOGGER CONFIGURATION
# Create a root logger for the entire 'backend' namespace
# All backend modules will inherit from this logger via getLogger('backend.module_name')
root_logger = logging.getLogger('backend')
root_logger.setLevel(logging.DEBUG)  # Accept DEBUG and above at source level
root_logger.propagate = False  # Don't propagate to parent loggers to prevent duplication

# Clear any existing handlers before adding new ones to prevent duplicates
# Critical for module reloads and package reinitialization scenarios
# Prevents the common issue of duplicate log messages appearing in output
if root_logger.handlers:
    root_logger.handlers.clear()

# Add handlers (always, not conditionally) — ensures clean state after clear()
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)