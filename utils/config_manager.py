import json
from pathlib import Path
from typing import Dict, Any, List

DEFAULT_PRESETS: Dict[str, Dict[str, Any]] = {
    "TikTok Viral (Vàng nổi bật)": {
        "font_family": "Arial",
        "font_size": 5.5,
        "text_color": "#FFE600",
        "border_color": "#000000",
        "border_width": 3,
        "sub_pos_x": 0.5,
        "sub_pos_y": 0.85,
        "effect": "Fade In/Out",
        "single_line": True
    },
    "Douyin Modern (Trắng hiện đại)": {
        "font_family": "Segoe UI",
        "font_size": 5.2,
        "text_color": "#FFFFFF",
        "border_color": "#111111",
        "border_width": 3,
        "sub_pos_x": 0.5,
        "sub_pos_y": 0.82,
        "effect": "Slide Up",
        "single_line": True
    },
    "Neon Cyan (Công nghệ)": {
        "font_family": "Tahoma",
        "font_size": 5.2,
        "text_color": "#00F0FF",
        "border_color": "#0A1128",
        "border_width": 3,
        "sub_pos_x": 0.5,
        "sub_pos_y": 0.84,
        "effect": "Zoom In",
        "single_line": True
    },
    "Typewriter (Đánh máy)": {
        "font_family": "Arial",
        "font_size": 5.0,
        "text_color": "#FFFFFF",
        "border_color": "#000000",
        "border_width": 2,
        "sub_pos_x": 0.5,
        "sub_pos_y": 0.85,
        "effect": "Typewriter",
        "single_line": True
    },
    "Cinematic (Điện ảnh tinh tế)": {
        "font_family": "Times New Roman",
        "font_size": 4.8,
        "text_color": "#F0EFEA",
        "border_color": "#1A1A1A",
        "border_width": 2,
        "sub_pos_x": 0.5,
        "sub_pos_y": 0.88,
        "effect": "Fade In/Out",
        "single_line": True
    }
}

class ConfigManager:
    """
    Quản lý cấu hình ứng dụng và danh sách Presets giao diện phụ đề.
    """
    def __init__(self, base_dir: Path = None):
        if base_dir is None:
            self.base_dir = Path(__file__).parent.parent
        else:
            self.base_dir = Path(base_dir)
            
        self.config_file = self.base_dir / "config.json"
        self.presets_file = self.base_dir / "presets.json"
        self._ensure_files()

    def _ensure_files(self):
        if not self.presets_file.exists():
            with open(self.presets_file, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_PRESETS, f, ensure_ascii=False, indent=2)

    def load_presets(self) -> Dict[str, Dict[str, Any]]:
        try:
            with open(self.presets_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return DEFAULT_PRESETS.copy()

    def save_preset(self, name: str, style_data: Dict[str, Any]):
        presets = self.load_presets()
        presets[name] = style_data
        with open(self.presets_file, "w", encoding="utf-8") as f:
            json.dump(presets, f, ensure_ascii=False, indent=2)

    def delete_preset(self, name: str) -> bool:
        presets = self.load_presets()
        if name in presets:
            del presets[name]
            with open(self.presets_file, "w", encoding="utf-8") as f:
                json.dump(presets, f, ensure_ascii=False, indent=2)
            return True
        return False

    def load_last_settings(self) -> Dict[str, Any]:
        if not self.config_file.exists():
            return {}
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def save_last_settings(self, settings: Dict[str, Any]):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[ConfigManager] Lỗi lưu cấu hình: {e}")

config_manager = ConfigManager()
