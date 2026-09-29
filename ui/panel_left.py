import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from typing import Dict, Any, Callable, Optional, List

from core.video_processor import VideoProcessor
from ui.subtitle_dialog import SubtitleEditorDialog
from utils.logger import app_logger

class PanelLeft(ctk.CTkFrame):
    """
    Cột bên trái (CapCut Style):
    - Quản lý Media & Thuộc tính chi tiết của video gốc.
    - Trạng thái Crop & Nút hủy / vẽ lại crop.
    - Quản lý danh sách các vùng che (Blur & Blackbox) với nút xóa từng vùng.
    - Thống kê phụ đề & Nút mở modal chỉnh sửa chi tiết.
    """
    def __init__(
        self,
        master,
        app_state: Dict[str, Any],
        preview_canvas,
        on_state_updated: Callable[[], None],
        **kwargs
    ):
        super().__init__(master, fg_color="#18181b", width=290, corner_radius=8, **kwargs)
        self.app_state = app_state
        self.preview_canvas = preview_canvas
        self.on_state_updated = on_state_updated

        self.pack_propagate(False)
        self._build_ui()

    def _build_ui(self):
        container = ctk.CTkScrollableFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=8, pady=8)

        # Header cột
        lbl_head = ctk.CTkLabel(
            container,
            text="THUỘC TÍNH & MEDIA",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38bdf8"
        )
        lbl_head.pack(anchor="w", padx=6, pady=(4, 10))

        # 1. Nút Chọn Video
        self.btn_select_video = ctk.CTkButton(
            container,
            text="📂 Chọn Video Local",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#0284c7",
            hover_color="#0369a1",
            height=36,
            command=self._select_video
        )
        self.btn_select_video.pack(fill="x", padx=6, pady=(0, 10))

        # 2. Khung Thuộc tính Video
        info_card = ctk.CTkFrame(container, fg_color="#202024", corner_radius=6)
        info_card.pack(fill="x", padx=6, pady=5)

        ctk.CTkLabel(
            info_card,
            text="Thông số Video",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e4e4e7"
        ).pack(anchor="w", padx=10, pady=(8, 4))

        self.lbl_v_name = ctk.CTkLabel(info_card, text="Tệp: (Chưa chọn)", font=ctk.CTkFont(size=11), text_color="#a1a1aa", anchor="w")
        self.lbl_v_name.pack(fill="x", padx=10, pady=1)

        self.lbl_v_res = ctk.CTkLabel(info_card, text="Độ phân giải: --", font=ctk.CTkFont(size=11), text_color="#a1a1aa", anchor="w")
        self.lbl_v_res.pack(fill="x", padx=10, pady=1)

        self.lbl_v_fps = ctk.CTkLabel(info_card, text="Tốc độ khung: --", font=ctk.CTkFont(size=11), text_color="#a1a1aa", anchor="w")
        self.lbl_v_fps.pack(fill="x", padx=10, pady=1)

        self.lbl_v_dur = ctk.CTkLabel(info_card, text="Thời lượng: --", font=ctk.CTkFont(size=11), text_color="#a1a1aa", anchor="w")
        self.lbl_v_dur.pack(fill="x", padx=10, pady=1)

        self.lbl_v_audio = ctk.CTkLabel(info_card, text="Âm thanh gốc: --", font=ctk.CTkFont(size=11), text_color="#a1a1aa", anchor="w")
        self.lbl_v_audio.pack(fill="x", padx=10, pady=(1, 8))

        # 3. Khung Trạng thái Crop
        crop_card = ctk.CTkFrame(container, fg_color="#202024", corner_radius=6)
        crop_card.pack(fill="x", padx=6, pady=8)

        ctk.CTkLabel(
            crop_card,
            text="Khung hình & Crop",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e4e4e7"
        ).pack(anchor="w", padx=10, pady=(8, 2))

        self.lbl_crop_status = ctk.CTkLabel(
            crop_card,
            text="Trạng thái: Gốc (Toàn màn hình)",
            font=ctk.CTkFont(size=11),
            text_color="#a1a1aa",
            anchor="w"
        )
        self.lbl_crop_status.pack(fill="x", padx=10, pady=2)

        crop_btn_row = ctk.CTkFrame(crop_card, fg_color="transparent")
        crop_btn_row.pack(fill="x", padx=10, pady=(4, 8))

        self.btn_recrop = ctk.CTkButton(
            crop_btn_row,
            text="✂ Vẽ Crop",
            width=85,
            height=28,
            fg_color="#374151",
            hover_color="#4b5563",
            command=self._start_crop_mode
        )
        self.btn_recrop.pack(side="left", padx=(0, 4))

        self.btn_reset_crop = ctk.CTkButton(
            crop_btn_row,
            text="Hủy Crop",
            width=85,
            height=28,
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=self._reset_crop
        )
        self.btn_reset_crop.pack(side="left")

        # 4. Khung Quản lý Vùng che (Blur & Blackbox)
        self.mask_card = ctk.CTkFrame(container, fg_color="#202024", corner_radius=6)
        self.mask_card.pack(fill="x", padx=6, pady=8)

        mask_head = ctk.CTkFrame(self.mask_card, fg_color="transparent")
        mask_head.pack(fill="x", padx=10, pady=(8, 4))

        self.lbl_mask_title = ctk.CTkLabel(
            mask_head,
            text="Vùng che gốc (0)",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e4e4e7"
        )
        self.lbl_mask_title.pack(side="left")

        btn_clear_all_masks = ctk.CTkButton(
            mask_head,
            text="Xóa hết",
            width=55,
            height=22,
            font=ctk.CTkFont(size=10),
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=self._clear_all_masks
        )
        btn_clear_all_masks.pack(side="right")

        self.mask_list_frame = ctk.CTkFrame(self.mask_card, fg_color="transparent")
        self.mask_list_frame.pack(fill="x", padx=10, pady=(0, 8))
        self.lbl_no_masks = ctk.CTkLabel(
            self.mask_list_frame,
            text="Chưa có vùng che nào.\n(Chọn vẽ Blur hoặc Blackbox trên Preview)",
            font=ctk.CTkFont(size=10),
            text_color="#71717a",
            justify="left"
        )
        self.lbl_no_masks.pack(fill="x", pady=4)

        # 5. Khung Phụ đề & Soạn thảo
        sub_card = ctk.CTkFrame(container, fg_color="#202024", corner_radius=6)
        sub_card.pack(fill="x", padx=6, pady=8)

        ctk.CTkLabel(
            sub_card,
            text="Phụ đề & Dữ liệu lời thoại",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#e4e4e7"
        ).pack(anchor="w", padx=10, pady=(8, 2))

        self.lbl_sub_count = ctk.CTkLabel(
            sub_card,
            text="Số câu phụ đề: 0 câu",
            font=ctk.CTkFont(size=11),
            text_color="#a1a1aa",
            anchor="w"
        )
        self.lbl_sub_count.pack(fill="x", padx=10, pady=2)

        self.btn_open_subs = ctk.CTkButton(
            sub_card,
            text="📝 Chỉnh sửa phụ đề chi tiết",
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            height=32,
            command=self._open_subtitle_dialog
        )
        self.btn_open_subs.pack(fill="x", padx=10, pady=(6, 10))

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

            out_name = f"{p.stem}_vietsub.mp4"
            self.app_state["output_path"] = str(p.parent / out_name)

            dur_sec = info["duration"]
            dur_str = f"{int(dur_sec//60):02d}:{int(dur_sec%60):02d}"

            # Cập nhật UI cột trái
            self.lbl_v_name.configure(text=f"Tệp: {p.name}")
            self.lbl_v_res.configure(text=f"Độ phân giải: {info['width']} x {info['height']}")
            self.lbl_v_fps.configure(text=f"Tốc độ khung: {info['fps']:.1f} FPS")
            self.lbl_v_dur.configure(text=f"Thời lượng: {dur_str} ({dur_sec:.1f}s)")
            self.lbl_v_audio.configure(text=f"Âm thanh: {'Có track tiếng' if info['has_audio'] else 'Không có audio'}")

            # Nạp vào Preview
            self.preview_canvas.load_video(str(p))
            app_logger.info(f"Đã nạp video: {p.name} ({info['width']}x{info['height']})")
            self.on_state_updated()
        except Exception as e:
            app_logger.error(f"Lỗi khi đọc file video: {e}")

    def update_crop_status(self, crop: Optional[Dict[str, Any]]):
        if crop and crop.get("enabled"):
            w = crop.get("w", 0)
            h = crop.get("h", 0)
            self.lbl_crop_status.configure(
                text=f"Đã Crop: {w}x{h}\nKhung 16:9 không méo hình",
                text_color="#10b981"
            )
        else:
            self.lbl_crop_status.configure(
                text="Trạng thái: Gốc (Toàn cảnh)\nKhung 16:9 (1920x1080)",
                text_color="#a1a1aa"
            )

    def update_mask_list(self, boxes: List[Dict[str, Any]]):
        self.lbl_mask_title.configure(text=f"Vùng che gốc ({len(boxes)})")
        
        # Xóa các dòng cũ
        for widget in self.mask_list_frame.winfo_children():
            widget.destroy()

        if not boxes:
            self.lbl_no_masks = ctk.CTkLabel(
                self.mask_list_frame,
                text="Chưa có vùng che nào.\n(Chọn vẽ Blur hoặc Blackbox trên Preview)",
                font=ctk.CTkFont(size=10),
                text_color="#71717a",
                justify="left"
            )
            self.lbl_no_masks.pack(fill="x", pady=4)
            return

        for idx, box in enumerate(boxes):
            row = ctk.CTkFrame(self.mask_list_frame, fg_color="#18181b", height=28)
            row.pack(fill="x", pady=2)

            btype = box.get("type", "blur").upper()
            badge_color = "#3b82f6" if btype == "BLUR" else "#ef4444"

            badge = ctk.CTkLabel(
                row,
                text=btype,
                font=ctk.CTkFont(size=9, weight="bold"),
                text_color=badge_color,
                width=45
            )
            badge.pack(side="left", padx=4)

            desc = f"#{idx+1}: {box.get('w')}x{box.get('h')}"
            lbl_desc = ctk.CTkLabel(row, text=desc, font=ctk.CTkFont(size=10), text_color="#d4d4d8")
            lbl_desc.pack(side="left", padx=2)

            btn_del = ctk.CTkButton(
                row,
                text="✕",
                width=22,
                height=20,
                font=ctk.CTkFont(size=10),
                fg_color="#374151",
                hover_color="#ef4444",
                command=lambda i=idx: self._delete_mask(i)
            )
            btn_del.pack(side="right", padx=4)

    def update_subtitle_count(self, count: int):
        self.lbl_sub_count.configure(text=f"Số câu phụ đề: {count} câu")

    def _start_crop_mode(self):
        self.preview_canvas.interaction_mode = "crop"
        self.preview_canvas.crop_view_mode = "full" # Hiển thị full frame để vẽ lại
        if not self.preview_canvas.is_playing:
            self.preview_canvas.seek_frame(self.preview_canvas.current_frame_idx)
        app_logger.info("Chế độ: Hãy kéo chuột trên màn hình Preview để chọn vùng Crop mới.")

    def _reset_crop(self):
        self.preview_canvas.reset_crop()
        self.app_state["crop_box"] = None
        self.update_crop_status(None)
        self.on_state_updated()

    def _delete_mask(self, index: int):
        self.preview_canvas.remove_mask_box(index)

    def _clear_all_masks(self):
        self.preview_canvas.clear_all_mask_boxes()

    def _open_subtitle_dialog(self):
        subs = self.app_state.get("manual_subtitles") or []
        if not subs:
            subs = [
                {"index": 1, "start_time": 0.5, "end_time": 3.0, "text": "你好，欢迎大家", "translation": "Xin chào, chào mừng các bạn!"}
            ]

        def on_saved(updated_subs):
            self.app_state["manual_subtitles"] = updated_subs
            self.update_subtitle_count(len(updated_subs))
            app_logger.info(f"Đã lưu danh sách {len(updated_subs)} câu phụ đề.")
            self.on_state_updated()

        SubtitleEditorDialog(
            master=self.winfo_toplevel(),
            subtitles=subs,
            on_save_callback=on_saved
        )
