import os
import shutil
import tempfile
import atexit
from pathlib import Path
from typing import List, Set

class TempManager:
    """
    Quản lý vòng đời của các file tạm trong quá trình xử lý video,
    đảm bảo tự động dọn dẹp sạch sẽ khi xuất xong hoặc khi tắt ứng dụng.
    Tự động tái tạo thư mục session nếu đã bị dọn dẹp trước đó.
    """
    def __init__(self, prefix: str = "douyin_translator_"):
        self.prefix = prefix
        self.session_dir = Path(tempfile.mkdtemp(prefix=prefix))
        self._tracked_files: Set[Path] = set()
        atexit.register(self.cleanup_all)

    def _ensure_session_dir(self):
        if not self.session_dir.exists():
            self.session_dir.mkdir(parents=True, exist_ok=True)

    def get_temp_file(self, suffix: str = ".tmp", name: str = None) -> Path:
        """Tạo đường dẫn file tạm mới nằm trong session_dir."""
        self._ensure_session_dir()
        if name:
            target = self.session_dir / name
        else:
            fd, path = tempfile.mkstemp(suffix=suffix, dir=self.session_dir)
            os.close(fd)
            target = Path(path)
        self._tracked_files.add(target)
        return target

    def track(self, file_path: Path) -> Path:
        """Đưa một file đã có vào danh sách quản lý để dọn dẹp sau."""
        p = Path(file_path)
        self._tracked_files.add(p)
        return p

    def cleanup_file(self, file_path: Path):
        """Xóa 1 file tạm cụ thể."""
        p = Path(file_path)
        try:
            if p.exists():
                p.unlink(missing_ok=True)
            self._tracked_files.discard(p)
        except Exception as e:
            print(f"[TempManager] Cảnh báo không thể xóa file {p}: {e}")

    def cleanup_all(self):
        """Xóa toàn bộ file và thư mục tạm của phiên làm việc, chuẩn bị session mới."""
        try:
            if self.session_dir.exists():
                shutil.rmtree(self.session_dir, ignore_errors=True)
            self._tracked_files.clear()
            # Tái tạo session_dir mới để sẵn sàng cho lần chạy tiếp theo
            self.session_dir = Path(tempfile.mkdtemp(prefix=self.prefix))
        except Exception as e:
            print(f"[TempManager] Cảnh báo khi dọn dẹp session dir: {e}")

# Global instance dùng chung
temp_manager = TempManager()
