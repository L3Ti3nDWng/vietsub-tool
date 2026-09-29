import sys
from datetime import datetime
from typing import Callable, List, Optional
import threading

class Logger:
    """
    Hệ thống Logger thread-safe hỗ trợ xuất ra console và chuyển tiếp
    real-time tới giao diện người dùng (CustomTkinter TextBox).
    """
    def __init__(self):
        self._callbacks: List[Callable[[str, str], None]] = []
        self._lock = threading.Lock()

    def register_callback(self, cb: Callable[[str, str], None]):
        """Đăng ký callback nhận tin nhắn log (message: str, level: str)"""
        with self._lock:
            if cb not in self._callbacks:
                self._callbacks.append(cb)

    def unregister_callback(self, cb: Callable[[str, str], None]):
        with self._lock:
            if cb in self._callbacks:
                self._callbacks.remove(cb)

    def _log(self, level: str, message: str):
        now_str = datetime.now().strftime("%H:%M:%S")
        formatted = f"[{now_str}] [{level}] {message}"
        
        # In ra terminal
        try:
            print(formatted)
        except Exception:
            pass

        # Chuyển tiếp tới UI callbacks
        with self._lock:
            for cb in self._callbacks:
                try:
                    cb(formatted, level)
                except Exception:
                    pass

    def info(self, msg: str):
        self._log("INFO", msg)

    def success(self, msg: str):
        self._log("SUCCESS", msg)

    def warning(self, msg: str):
        self._log("WARNING", msg)

    def error(self, msg: str):
        self._log("ERROR", msg)

    def step(self, current: int, total: int, title: str):
        self._log("PROGRESS", f"[{current}/{total}] {title}")

# Global instance
app_logger = Logger()
