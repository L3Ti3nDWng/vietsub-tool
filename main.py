import sys
import os
import shutil
from pathlib import Path

# Đảm bảo mã hóa UTF-8 toàn diện trên môi trường Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Thêm thư mục hiện tại vào sys.path
BASE_DIR = Path(__file__).parent.resolve()
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Tự động ưu tiên thư mục bin nội bộ của project (chứa ffmpeg, ffprobe) - không can thiệp hệ thống
LOCAL_BIN_DIR = BASE_DIR / "bin"
if LOCAL_BIN_DIR.exists():
    bin_str = str(LOCAL_BIN_DIR)
    current_path = os.environ.get("PATH", "")
    if bin_str not in current_path:
        os.environ["PATH"] = bin_str + os.pathsep + current_path

from ui.app import DouyinTranslatorApp
from utils.logger import app_logger

def verify_system_requirements():
    """Kiểm tra FFmpeg đã được cài đặt và có sẵn trong PATH chưa."""
    ffmpeg_path = shutil.which("ffmpeg")
    if not ffmpeg_path:
        app_logger.warning("CẢNH BÁO: Không tìm thấy 'ffmpeg' trong hệ thống PATH! Quá trình render video có thể bị lỗi.")
    else:
        app_logger.info(f"Đã phát hiện FFmpeg: {ffmpeg_path}")

def main():
    app_logger.info("Đang khởi động ứng dụng Douyin Translator Pro...")
    verify_system_requirements()
    
    app = DouyinTranslatorApp()
    app.mainloop()

if __name__ == "__main__":
    main()
