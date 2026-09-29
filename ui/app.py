import customtkinter as ctk
import tkinter as tk
from pathlib import Path
from typing import Dict, Any, Optional

from ui.panel_left import PanelLeft
from ui.panel_center import PanelCenter
from ui.panel_right import PanelRight
from utils.config_manager import config_manager
from utils.temp_manager import temp_manager
from utils.logger import app_logger

class DouyinTranslatorApp(ctk.CTk):
    """
    Ứng dụng Douyin Translator Pro với Giao diện 3 Cột Chuyên Nghiệp (CapCut Desktop Style):
    - Cột Trái: Thuộc tính video gốc, Media, Trạng thái Crop, Danh sách vùng che & Quản lý phụ đề.
    - Cột Giữa: Khung xem trước Video Preview Canvas ở trung tâm (CROP PREVIEW REAL-TIME ngay khi kéo crop),
               kèm Toolbar thao tác chuột ở trên và Player điều khiển ở dưới.
    - Cột Phải: Các Tab thông số cài đặt (Phụ đề, Lồng tiếng, Logo, Dịch thuật, Log) ở trên,
               và NÚT BẮT ĐẦU CHẠY XUẤT VIDEO + PROGRESS BAR Ở DƯỚI CÙNG.
    """
    def __init__(self):
        super().__init__()

        # Cấu hình giao diện tối hiện đại
        ctk.set_appearance_mode("Dark")
        ctk.set_default_color_theme("blue")

        self.title("Douyin Translator Pro - Trình Biên Dịch & Lồng Tiếng Video (CapCut Style)")
        self.geometry("1340x840")
        self.minsize(1120, 720)

        # Trạng thái toàn cục của ứng dụng
        self.app_state: Dict[str, Any] = self._init_default_state()
        self._load_saved_settings()

        self._build_header()
        self._build_capcut_layout()

        # Đăng ký sự kiện tắt ứng dụng
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        # Đăng ký phím tắt Spacebar phát / tạm dừng video tiện lợi
        self.bind_all("<space>", self._on_space_pressed)

    def _on_space_pressed(self, event):
        """Phím tắt Spacebar để phát / tạm dừng video nhanh chóng như CapCut."""
        focused = self.focus_get()
        if focused is not None:
            cls_name = focused.__class__.__name__.lower()
            mod_name = str(focused.__class__).lower()
            # Cho phép gõ dấu cách bình thường khi đang trong ô nhập chữ
            if "entry" in cls_name or "text" in cls_name or "entry" in mod_name or "text" in mod_name:
                return

        if hasattr(self, "panel_center"):
            self.panel_center._toggle_play()
            return "break"

    def _init_default_state(self) -> Dict[str, Any]:
        return {
            "video_path": None,
            "video_info": None,
            "output_path": "",
            "subtitle_style": {
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
            "mask_boxes": [],
            "crop_box": None,
            "overlay_info": {
                "enabled": False,
                "path": None,
                "x": 30,
                "y": 30,
                "scale": 1.0,
                "opacity": 1.0
            },
            "voice_type": "BV074_streaming",
            "speech_rate": 1.0,
            "enable_tts": True,
            "tts_volume": 1.0,
            "original_volume": 1.0,
            "enable_ducking": True,
            "ducking_volume": 0.18,
            "enable_subtitles": True,
            "translation_engine": "chatgpt",
            "chatgpt_headless": False,
            "manual_subtitles": []
        }

    def _load_saved_settings(self):
        saved = config_manager.load_last_settings()
        if saved:
            if "subtitle_style" in saved:
                self.app_state["subtitle_style"].update(saved["subtitle_style"])
            if "voice_type" in saved:
                self.app_state["voice_type"] = saved["voice_type"]
            if "speech_rate" in saved:
                self.app_state["speech_rate"] = saved["speech_rate"]
            if "ducking_volume" in saved:
                self.app_state["ducking_volume"] = saved["ducking_volume"]
            if "translation_engine" in saved:
                self.app_state["translation_engine"] = saved["translation_engine"]

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="#18181b", height=46, corner_radius=0)
        header.pack(fill="x", padx=0, pady=0)

        title_lbl = ctk.CTkLabel(
            header,
            text="🎬 DOUYIN TRANSLATOR PRO",
            font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
            text_color="#38bdf8"
        )
        title_lbl.pack(side="left", padx=16, pady=8)

        desc_lbl = ctk.CTkLabel(
            header,
            text="|   Giao diện CapCut Studio (Local Desktop AI Engine)",
            font=ctk.CTkFont(size=12),
            text_color="#94a3b8"
        )
        desc_lbl.pack(side="left", padx=4, pady=8)

        badge_lbl = ctk.CTkLabel(
            header,
            text="PRO v2.5",
            font=ctk.CTkFont(size=10, weight="bold"),
            fg_color="#0284c7",
            text_color="#ffffff",
            corner_radius=4,
            width=65,
            height=20
        )
        badge_lbl.pack(side="right", padx=16, pady=8)

    def _build_capcut_layout(self):
        # Khung chứa chính chia 3 cột: Trái (280px), Giữa (Linh hoạt), Phải (380px)
        main_workspace = ctk.CTkFrame(self, fg_color="transparent")
        main_workspace.pack(fill="both", expand=True, padx=8, pady=(6, 8))

        # 1. KHU VỰC Ở GIỮA: PANEL CENTER (Tạo trước để có preview_canvas truyền sang 2 cột bên)
        self.panel_center = PanelCenter(
            main_workspace,
            app_state=self.app_state,
            on_sub_pos_changed=self._on_sub_pos_changed,
            on_boxes_changed=self._on_boxes_changed,
            on_crop_changed=self._on_crop_changed
        )

        # 2. CỘT BÊN TRÁI: THUỘC TÍNH VIDEO & MEDIA (PanelLeft)
        self.panel_left = PanelLeft(
            main_workspace,
            app_state=self.app_state,
            preview_canvas=self.panel_center.preview,
            on_state_updated=self._on_state_updated
        )
        self.panel_left.pack(side="left", fill="y", padx=(0, 6))

        # 3. CỘT BÊN PHẢI: THÔNG SỐ CÀI ĐẶT & NÚT BẮT ĐẦU CHẠY Ở DƯỚI (PanelRight)
        self.panel_right = PanelRight(
            main_workspace,
            app_state=self.app_state,
            preview_canvas=self.panel_center.preview,
            on_state_updated=self._on_state_updated
        )
        self.panel_right.pack(side="right", fill="y", padx=(6, 0))

        # 4. Đặt Panel Center chiếm toàn bộ diện tích còn lại ở giữa
        self.panel_center.pack(side="left", fill="both", expand=True)

        # Đồng bộ cấu hình style phụ đề ban đầu sang preview
        st = self.app_state["subtitle_style"]
        self.panel_center.preview.set_subtitle_style(
            font_family=st["font_family"],
            font_size=st["font_size"],
            text_color=st["text_color"],
            border_color=st["border_color"],
            border_width=st["border_width"]
        )

    def _on_sub_pos_changed(self, x_ratio: float, y_ratio: float):
        self.app_state["subtitle_style"]["sub_pos_x"] = x_ratio
        self.app_state["subtitle_style"]["sub_pos_y"] = y_ratio

    def _on_boxes_changed(self, boxes):
        self.app_state["mask_boxes"] = boxes
        self.panel_left.update_mask_list(boxes)

    def _on_crop_changed(self, crop):
        self.app_state["crop_box"] = crop
        self.panel_left.update_crop_status(crop)
        if crop:
            app_logger.info(f"Đã kích hoạt Crop: {crop['w']}x{crop['h']} (Preview đã tự động crop luôn khung hình).")
        else:
            app_logger.info("Đã hủy bỏ Crop, khôi phục toàn khung hình.")

    def _on_state_updated(self):
        """Đồng bộ khi có sự thay đổi giữa các Panel."""
        # Cập nhật đường dẫn xuất nếu có
        out_p = self.app_state.get("output_path")
        if out_p:
            self.panel_right.set_output_path(out_p)

        # Cập nhật thời lượng slider nếu có
        v_info = self.app_state.get("video_info")
        if v_info and "duration" in v_info:
            self.panel_center.set_duration(v_info["duration"])

        # Cập nhật danh sách mask boxes
        boxes = self.app_state.get("mask_boxes") or []
        self.panel_left.update_mask_list(boxes)

        # Cập nhật trạng thái crop
        crop = self.app_state.get("crop_box")
        self.panel_left.update_crop_status(crop)

        # Cập nhật số lượng phụ đề
        subs = self.app_state.get("manual_subtitles") or []
        self.panel_left.update_subtitle_count(len(subs))

    def _on_close(self):
        """Lưu cấu hình và dọn dẹp an toàn khi tắt app."""
        try:
            save_payload = {
                "subtitle_style": self.app_state.get("subtitle_style"),
                "voice_type": self.app_state.get("voice_type"),
                "speech_rate": self.app_state.get("speech_rate"),
                "ducking_volume": self.app_state.get("ducking_volume"),
                "translation_engine": self.app_state.get("translation_engine")
            }
            config_manager.save_last_settings(save_payload)
        except Exception:
            pass

        try:
            self.panel_center.preview.release()
        except Exception:
            pass

        try:
            temp_manager.cleanup_all()
        except Exception:
            pass

        self.destroy()
