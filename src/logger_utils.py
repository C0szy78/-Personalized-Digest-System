"""Logging utilities for the digest system."""
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


class DigestLogger:
    """Simple logger for digest automation with timestamps and formatting."""

    def __init__(self, log_dir: str = "logs", enable_file_logging: bool = True):
        """
        Initialize logger.

        Args:
            log_dir: Directory to store log files
            enable_file_logging: Whether to write logs to file
        """
        self.enable_file_logging = enable_file_logging
        self.log_dir = Path(log_dir)
        self.log_file = None

        if self.enable_file_logging:
            # Create logs directory if it doesn't exist
            self.log_dir.mkdir(exist_ok=True)

            # Create log file with date
            log_filename = f"digest_{datetime.now().strftime('%Y%m%d')}.log"
            self.log_file = self.log_dir / log_filename

    def timestamp(self):
        """Get formatted timestamp."""
        return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    def _write(self, message: str):
        """Write message to both console and file."""
        # Print to console
        print(message)

        # Write to file if enabled
        if self.enable_file_logging and self.log_file:
            try:
                # Remove emoji for file logging (cleaner file logs)
                file_message = message.replace('ℹ️', 'INFO')
                file_message = file_message.replace('✅', 'SUCCESS')
                file_message = file_message.replace('⚠️', 'WARNING')
                file_message = file_message.replace('❌', 'ERROR')
                file_message = file_message.replace('🔍', 'DEBUG')
                file_message = file_message.replace('🚀', 'START')
                file_message = file_message.replace('📋', 'SECTION')

                with open(self.log_file, 'a', encoding='utf-8') as f:
                    f.write(file_message + '\n')
            except Exception as e:
                print(f"Warning: Failed to write to log file: {e}")

    def info(self, message: str, indent: int = 0):
        """Log info message."""
        prefix = "  " * indent
        self._write(f"[{self.timestamp()}] ℹ️  {prefix}{message}")

    def success(self, message: str, indent: int = 0):
        """Log success message."""
        prefix = "  " * indent
        self._write(f"[{self.timestamp()}] ✅ {prefix}{message}")

    def warning(self, message: str, indent: int = 0):
        """Log warning message."""
        prefix = "  " * indent
        self._write(f"[{self.timestamp()}] ⚠️  {prefix}{message}")

    def error(self, message: str, indent: int = 0):
        """Log error message."""
        prefix = "  " * indent
        self._write(f"[{self.timestamp()}] ❌ {prefix}{message}")

    def debug(self, message: str, indent: int = 0):
        """Log debug message."""
        prefix = "  " * indent
        self._write(f"[{self.timestamp()}] 🔍 {prefix}{message}")

    def header(self, message: str):
        """Log header with separator."""
        separator = "=" * 70
        self._write(f"\n{separator}")
        self._write(f"[{self.timestamp()}] 🚀 {message}")
        self._write(f"{separator}\n")

    def section(self, message: str):
        """Log section header."""
        self._write(f"\n[{self.timestamp()}] 📋 {message}")
        self._write("-" * 60)


# Global logger instance
log = DigestLogger()