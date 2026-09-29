import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from ui.video_preview import VideoPreviewCanvas
from core.video_processor import VideoProcessor
from utils.logger import app_logger

class TabVideo(ctk.CTkFrame):
    """
    Tab 1: Chọn video + Preview trực quan + Kéo phụ đề + Vẽ vùng mờ/Blackbox + Crop khung hình
    """
    def __init__(self, master, app_state: Dict[str, Any], on_state_updated: Callable[[], None], **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app_state = app_state
        self.on_state_updated = on_state_updated

        self._build_ui()

    def _build_ui(self):
        # 1. Top Section: Chọn file & thông tin video
        top_frame = ctk.CTkFrame(self, fg_color="#1f1f23", corner_radius=8)
        top_frame.pack(fill="x", padx=10, pady=(10, 5))

        btn_select = ctk.CTkButton(
            top_frame,
            text="📂 Chọn Video Local",
            font=ctk.CTkFont(size=13, weight="bold"),
            width=160,
            command=self._select_video
        )
        btn_select.pack(side="left", padx=10, pady=10)

        self.lbl_video_info = ctk.CTkLabel(
            top_frame,
            text="Chưa có video nào được chọn",
            font=ctk.CTkFont(size=12),
            text_color="#a1a1aa",
            anchor="w"
        )
        self.lbl_video_info.pack(side="left", fill="x", expand=True, padx=10)

        # 2. Main Center: Khung xem trước VideoPreviewCanvas
        preview_container = ctk.CTkFrame(self, fg_color="#18181b", corner_radius=8)
        preview_container.pack(fill="both", expand=True, padx=10, pady=5)

        self.preview = VideoPreviewCanvas(
            preview_container,
            width=680,
            height=380,
            on_sub_pos_changed=self._on_sub_pos_changed,
            on_boxes_changed=self._on_boxes_changed,
            on_crop_changed=self._on_crop_changed
        )
        self.preview.pack(fill="both", expand=True, padx=8, pady=8)

        # 3. Thanh điều khiển phát video (Playback Controls)
        playback_frame = ctk.CTkFrame(self, fg_color="#1f1f23", height=42, corner_radius=8)
        playback_frame.pack(fill="x", padx=10, pady=5)

        self.btn_play = ctk.CTkButton(
            playback_frame,
            text="▶ Phát",
            width=70,
            command=self._toggle_playback
        )
        self.btn_play.pack(side="left", padx=8, pady=5)

        btn_step_back = ctk.CTkButton(
            playback_frame,
            text="◀ -1s",
            width=60,
            command=lambda: self._seek_offset(-1.0)
        )
        btn_step_back.pack(side="left", padx=4, pady=5)

        btn_step_fwd = ctk.CTkButton(
            playback_frame,
            text="+1s ▶",
            width=60,
            command=lambda: self._seek_offset(1.0)
        )
        btn_step_fwd.pack(side="left", padx=4, pady=5)

        self.slider_time = ctk.CTkSlider(
            playback_frame,
            from_=0.0,
            to=100.0,
            command=self._on_slider_moved
        )
        self.slider_time.pack(side="left", fill="x", expand=True, padx=10, pady=5)
        self.slider_time.set(0)

        self.lbl_time = ctk.CTkLabel(
            playback_frame,
            text="00:00 / 00:00",
            font=ctk.CTkFont(size=11),
            width=85
        )
        self.lbl_time.pack(side="left", padx=(0, 10), pady=5)

        # 4. Bottom Toolbar: Chọn chế độ tương tác & Quản lý vùng che
        tools_frame = ctk.CTkFrame(self, fg_color="#1f1f23", corner_radius=8)
        tools_frame.pack(fill="x", padx=10, pady=(5, 10))

        lbl_mode = ctk.CTkLabel(
            tools_frame,
            text="Chế độ chuột:",
            font=ctk.CTkFont(size=12, weight="bold")
        )
        lbl_mode.pack(side="left", padx=(10, 5), pady=8)

        self.seg_mode = ctk.CTkSegmentedButton(
            tools_frame,
            values=["✥ Kéo phụ đề", "🟦 Vẽ vùng mờ (Blur)", "⬛ Vẽ hộp đen (Blackbox)", "✂ Chọn vùng Crop"],
            command=self._on_mode_changed
        )
        self.seg_mode.pack(side="left", padx=5, pady=8)
        self.seg_mode.set("✥ Kéo phụ đề")

        # Nút quản lý vùng che
        self.btn_clear_masks = ctk.CTkButton(
            tools_frame,
            text="Xóa tất cả vùng che",
            fg_color="#ef4444",
            hover_color="#dc2626",
            width=130,
            command=self._clear_masks
        )
        self.btn_clear_masks.pack(side="right", padx=(5, 10), pady=8)

        self.btn_reset_crop = ctk.CTkButton(
            tools_frame,
            text="Hủy Crop",
            fg_color="#4b5563",
            hover_color="#374151",
            width=90,
            command=self._reset_crop
        )
        self.btn_reset_crop.pack(side="right", padx=5, pady=8)

        # Timer cập nhật timecode định kỳ
        self._schedule_time_update()

    def _select_video(self):
        file_path = filedialog.askopenfilename(
            title="Chọn file video",
            filetypes=[
                ("Video Files", "*.mp4 *.mov *.mkv *.avi *.webm *.flv"),
                ("All Files", "*.*")
            ]
        )
        if not file_path:
            return

        p = Path(file_path)
        try:
            info = VideoProcessor.get_video_info(p)
            self.app_state["video_path"] = str(p)
            self.app_state["video_info"] = info

            # Đặt output mặc định
            out_name = f"{p.stem}_vietsub.mp4"
            self.app_state["output_path"] = str(p.parent / out_name)

            dur_sec = info["duration"]
            dur_str = f"{int(dur_sec//60):02d}:{int(dur_sec%60):02d}"
            txt = f"Video: {p.name} | {info['width']}x{info['height']} | {info['fps']:.1f} FPS | {dur_str} | Audio: {'Có' if info['has_audio'] else 'Không'}"
            self.lbl_video_info.configure(text=txt)

            self.slider_time.configure(to=max(1.0, dur_sec))
            self.slider_time.set(0)

            # Nạp vào Canvas
            self.preview.load_video(str(p))
            app_logger.info(f"Đã mở video: {p.name}")
            self.on_state_updated()
        except Exception as e:
            app_logger.error(f"Lỗi khi đọc file video: {e}")

    def _toggle_playback(self):
        if self.preview.is_playing:
            self.preview.pause()
            self.btn_play.configure(text="▶ Phát")
        else:
            self.preview.play()
            self.btn_play.configure(text="⏸ Tạm dừng")

    def _seek_offset(self, offset_sec: float):
        curr = self.preview.get_current_time()
        new_time = max(0.0, curr + offset_sec)
        self.preview.seek_seconds(new_time)
        self.slider_time.set(new_time)

    def _on_slider_moved(self, value):
        self.preview.seek_seconds(float(value))

    def _schedule_time_update(self):
        if self.preview.cap and self.preview.is_playing:
            curr = self.preview.get_current_time()
            total = self.app_state.get("video_info", {}).get("duration", 0.0)
            self.slider_time.set(curr)
            curr_str = f"{int(curr//60):02d}:{int(curr%60):02d}"
            tot_str = f"{int(total//60):02d}:{int(total%60):02d}"
            self.lbl_time.configure(text=f"{curr_str} / {tot_str}")
        self.after(300, self._schedule_time_update)

    def _on_mode_changed(self, value):
        if "Kéo phụ đề" in value:
            self.preview.interaction_mode = "sub"
        elif "vùng mờ" in value:
            self.preview.interaction_mode = "blur"
        elif "hộp đen" in value:
            self.preview.interaction_mode = "black"
        elif "Crop" in value:
            self.preview.interaction_mode = "crop"

    def _on_sub_pos_changed(self, x_ratio: float, y_ratio: float):
        self.app_state["subtitle_style"]["sub_pos_x"] = x_ratio
        self.app_state["subtitle_style"]["sub_pos_y"] = y_ratio
        self.on_state_updated()

    def _on_boxes_changed(self, boxes: List[Dict[str, Any]]):
        self.app_state["mask_boxes"] = boxes
        app_logger.info(f"Đã cập nhật danh sách vùng che ({len(boxes)} vùng).")
        self.on_state_updated()

    def _on_crop_changed(self, crop: Optional[Dict[str, Any]]):
        self.app_state["crop_box"] = crop
        if crop:
            app_logger.info(f"Đã chọn vùng Crop: ({crop['x']}, {crop['y']}, {crop['w']}, {crop['h']})")
        else:
            app_logger.info("Đã hủy vùng Crop.")
        self.on_state_updated()

    def _clear_masks(self):
        self.preview.clear_all_mask_boxes()
        self.app_state["mask_boxes"] = []
        self.on_state_updated()

    def _reset_crop(self):
        self.preview.reset_crop()
        self.app_state["crop_box"] = None
        self.on_state_updated()
