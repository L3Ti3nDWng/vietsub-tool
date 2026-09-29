import os
import time
import subprocess
from pathlib import Path
from typing import Dict, Any, Callable, Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox

class ExportDialog(ctk.CTkToplevel):
    """
    Bảng Pop-up Xuất Video chuyên nghiệp chuẩn giao diện CapCut Desktop:
    1. View 1: Cấu hình thông số chi tiết (Tên file, thư mục lưu, Resolution, Bitrate, FPS, Codec, Định dạng, Ước tính dung lượng).
    2. View 2: Trạng thái đang kết xuất (Render Progress) với số % lớn, thời gian đã trôi qua, bước xử lý chi tiết, nhật ký mini.
    3. View 3: Hoàn tất xuất với nút mở nhanh video, mở thư mục chứa.
    """
    def __init__(
        self,
        master,
        app_state: Dict[str, Any],
        on_start_export: Callable[[Dict[str, Any], Path, "ExportDialog"], None],
        on_cancel_export: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)
        self.app_state = app_state
        self.on_start_export = on_start_export
        self.on_cancel_export = on_cancel_export

        self.video_info = self.app_state.get("video_info") or {}
        self.total_duration = float(self.video_info.get("duration", 0.0))
        self.orig_w = int(self.video_info.get("width", 1920))
        self.orig_h = int(self.video_info.get("height", 1080))
        self.orig_fps = float(self.video_info.get("fps", 30.0))

        self.title("Xuất Video - Douyin Translator Pro")
        self.geometry("580x700")
        self.minsize(540, 640)
        self.configure(fg_color="#141416")

        # Căn giữa cửa sổ so với cửa sổ chính
        self.after(10, self._center_window)
        self.transient(master)
        self.grab_set()

        self.start_time = 0.0
        self.timer_running = False
        self.final_output_file: Optional[Path] = None

        self._build_ui()
        self._update_estimation()

    def _center_window(self):
        try:
            self.update_idletasks()
            pw = self.master.winfo_width()
            ph = self.master.winfo_height()
            px = self.master.winfo_rootx()
            py = self.master.winfo_rooty()
            w = self.winfo_width()
            h = self.winfo_height()
            cx = px + (pw - w) // 2
            cy = py + (ph - h) // 2
            self.geometry(f"+{max(20, cx)}+{max(20, cy)}")
        except Exception:
            pass

    def _build_ui(self):
        # 1. Top Header
        header = ctk.CTkFrame(self, fg_color="#1c1c20", height=50, corner_radius=0)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="🎬  XUẤT VIDEO (CAPCUT STYLE)",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#38bdf8"
        ).pack(side="left", padx=18)

        btn_close_top = ctk.CTkButton(
            header,
            text="✕",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=32,
            height=32,
            fg_color="transparent",
            hover_color="#27272a",
            text_color="#9ca3af",
            command=self._on_close
        )
        btn_close_top.pack(side="right", padx=12)

        # 2. Main Container
        self.container = ctk.CTkFrame(self, fg_color="transparent")
        self.container.pack(fill="both", expand=True, padx=16, pady=12)

        # Tạo sẵn các View
        self._build_settings_view()
        self._build_rendering_view()
        self._build_finished_view()

        # Hiển thị View 1 (Settings)
        self._show_view("settings")

    # ==========================
    # VIEW 1: CÀI ĐẶT THÔNG SỐ XUẤT
    # ==========================
    def _build_settings_view(self):
        self.view_settings = ctk.CTkScrollableFrame(self.container, fg_color="transparent")

        # 1. Tên tệp xuất
        ctk.CTkLabel(self.view_settings, text="Tên file video xuất ra:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(4, 2))
        
        default_name = "video_vietsub"
        cur_out = self.app_state.get("output_path", "")
        if cur_out:
            default_name = Path(cur_out).stem
        elif self.app_state.get("video_path"):
            default_name = f"{Path(self.app_state['video_path']).stem}_vietsub"

        self.ent_filename = ctk.CTkEntry(self.view_settings, height=36, font=ctk.CTkFont(size=13))
        self.ent_filename.insert(0, default_name)
        self.ent_filename.pack(fill="x", pady=(0, 10))

        # 2. Thư mục lưu
        ctk.CTkLabel(self.view_settings, text="Thư mục lưu video:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 2))
        folder_row = ctk.CTkFrame(self.view_settings, fg_color="transparent")
        folder_row.pack(fill="x", pady=(0, 12))

        default_folder = str(Path.home() / "Videos")
        if cur_out:
            default_folder = str(Path(cur_out).parent)
        elif self.app_state.get("video_path"):
            default_folder = str(Path(self.app_state["video_path"]).parent)

        self.ent_folder = ctk.CTkEntry(folder_row, height=36)
        self.ent_folder.insert(0, default_folder)
        self.ent_folder.pack(side="left", fill="x", expand=True, padx=(0, 8))

        btn_browse = ctk.CTkButton(
            folder_row,
            text="📁 Duyệt...",
            width=90,
            height=36,
            fg_color="#27272a",
            hover_color="#3f3f46",
            command=self._browse_folder
        )
        btn_browse.pack(side="right")

        # Divider
        ctk.CTkFrame(self.view_settings, height=1, fg_color="#27272a").pack(fill="x", pady=6)

        # 3. Độ phân giải (Resolution)
        ctk.CTkLabel(self.view_settings, text="Độ phân giải (Resolution):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(4, 4))
        self.seg_res = ctk.CTkSegmentedButton(
            self.view_settings,
            values=["720p", "1080p (Chuẩn)", "2K", "4K", "Gốc"],
            height=34,
            command=lambda v: self._update_estimation()
        )
        self.seg_res.pack(fill="x", pady=(0, 12))
        self.seg_res.set("1080p (Chuẩn)")

        # 4. Tốc độ bit (Bitrate)
        ctk.CTkLabel(self.view_settings, text="Tốc độ bit (Bitrate):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 4))
        self.bitrate_options = [
            "Tiêu chuẩn (6000 kbps - Khuyên dùng)",
            "Cao hơn (10000 kbps - Nét căng)",
            "Cực cao (16000 kbps - Sắc nét tối đa)",
            "Tiết kiệm (3500 kbps - Dung lượng nhẹ)",
            "Tùy chỉnh (Custom kbps)"
        ]
        self.cbo_bitrate = ctk.CTkComboBox(
            self.view_settings,
            values=self.bitrate_options,
            height=34,
            command=self._on_bitrate_changed
        )
        self.cbo_bitrate.pack(fill="x", pady=(0, 6))
        self.cbo_bitrate.set(self.bitrate_options[0])

        self.custom_bitrate_frame = ctk.CTkFrame(self.view_settings, fg_color="transparent")
        ctk.CTkLabel(self.custom_bitrate_frame, text="Nhập số kbps tùy chỉnh:").pack(side="left")
        self.ent_custom_bitrate = ctk.CTkEntry(self.custom_bitrate_frame, width=120, height=32)
        self.ent_custom_bitrate.insert(0, "8000")
        self.ent_custom_bitrate.pack(side="left", padx=8)
        self.ent_custom_bitrate.bind("<KeyRelease>", lambda e: self._update_estimation())

        # 5. Tốc độ khung hình (FPS) & Bộ mã hóa (Codec)
        two_col = ctk.CTkFrame(self.view_settings, fg_color="transparent")
        two_col.pack(fill="x", pady=(6, 12))
        two_col.grid_columnconfigure((0, 1), weight=1, uniform="subcol")

        # Cột trái: FPS
        c_left = ctk.CTkFrame(two_col, fg_color="transparent")
        c_left.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        ctk.CTkLabel(c_left, text="Tốc độ khung hình (FPS):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 4))
        self.cbo_fps = ctk.CTkComboBox(
            c_left,
            values=["30 fps (Chuẩn)", "60 fps (Mượt mà)", "24 fps (Điện ảnh)", "Gốc (Theo video)"],
            height=34,
            command=lambda v: self._update_estimation()
        )
        self.cbo_fps.pack(fill="x")
        self.cbo_fps.set("30 fps (Chuẩn)")

        # Cột phải: Codec
        c_right = ctk.CTkFrame(two_col, fg_color="transparent")
        c_right.grid(row=0, column=1, sticky="ew", padx=(6, 0))
        ctk.CTkLabel(c_right, text="Bộ mã hóa (Codec):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", pady=(0, 4))
        self.cbo_codec = ctk.CTkComboBox(
            c_right,
            values=["H.264 (Khuyên dùng - Phổ biến)", "H.265 / HEVC (Nén dung lượng nhỏ)"],
            height=34,
            command=lambda v: self._update_estimation()
        )
        self.cbo_codec.pack(fill="x")
        self.cbo_codec.set("H.264 (Khuyên dùng - Phổ biến)")

        # 6. Định dạng tệp (Format)
        fmt_row = ctk.CTkFrame(self.view_settings, fg_color="transparent")
        fmt_row.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(fmt_row, text="Định dạng xuất:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.seg_format = ctk.CTkSegmentedButton(fmt_row, values=["MP4", "MOV"], height=32)
        self.seg_format.pack(side="left", padx=8)
        self.seg_format.set("MP4")

        # 7. Card Tóm tắt & Ước tính dung lượng (CapCut Style Info Card)
        self.card_info = ctk.CTkFrame(self.view_settings, fg_color="#1e1e24", corner_radius=8, border_width=1, border_color="#2c2c34")
        self.card_info.pack(fill="x", pady=(4, 16))

        card_pad = ctk.CTkFrame(self.card_info, fg_color="transparent")
        card_pad.pack(fill="x", padx=14, pady=12)

        self.lbl_card_duration = ctk.CTkLabel(card_pad, text="⏱ Thời lượng: 00:00", font=ctk.CTkFont(size=12))
        self.lbl_card_duration.pack(anchor="w")

        self.lbl_card_resolution = ctk.CTkLabel(card_pad, text="📐 Độ phân giải: 1920x1080 • 30 fps", font=ctk.CTkFont(size=12))
        self.lbl_card_resolution.pack(anchor="w", pady=2)

        self.lbl_card_size = ctk.CTkLabel(
            card_pad,
            text="💾 Dung lượng ước tính: ~0 MB",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#10b981"
        )
        self.lbl_card_size.pack(anchor="w", pady=(2, 0))

        # Bottom Button Bar
        btn_bar = ctk.CTkFrame(self.view_settings, fg_color="transparent")
        btn_bar.pack(fill="x", side="bottom", pady=(8, 4))

        btn_cancel = ctk.CTkButton(
            btn_bar,
            text="Hủy bỏ",
            width=110,
            height=42,
            fg_color="#27272a",
            hover_color="#3f3f46",
            font=ctk.CTkFont(weight="bold"),
            command=self._on_close
        )
        btn_cancel.pack(side="left")

        self.btn_export = ctk.CTkButton(
            btn_bar,
            text="🚀  XUẤT VIDEO NGAY",
            height=42,
            fg_color="#10b981",
            hover_color="#059669",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_start_clicked
        )
        self.btn_export.pack(side="right", fill="x", expand=True, padx=(10, 0))

    # ==========================
    # VIEW 2: TIẾN ĐỘ RENDER (RENDERING PROGRESS)
    # ==========================
    def _build_rendering_view(self):
        self.view_rendering = ctk.CTkFrame(self.container, fg_color="transparent")

        ctk.CTkLabel(
            self.view_rendering,
            text="ĐANG KẾT XUẤT VIDEO...",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#38bdf8"
        ).pack(pady=(16, 2))

        self.lbl_render_target_name = ctk.CTkLabel(
            self.view_rendering,
            text="video_vietsub.mp4",
            font=ctk.CTkFont(size=12),
            text_color="#9ca3af"
        )
        self.lbl_render_target_name.pack(pady=(0, 20))

        # Khối hiển thị % cực lớn
        self.lbl_big_percent = ctk.CTkLabel(
            self.view_rendering,
            text="0%",
            font=ctk.CTkFont(size=52, weight="bold"),
            text_color="#10b981"
        )
        self.lbl_big_percent.pack(pady=(4, 8))

        # Progress bar lớn
        self.render_progress_bar = ctk.CTkProgressBar(self.view_rendering, height=14, corner_radius=7)
        self.render_progress_bar.pack(fill="x", padx=20, pady=(0, 14))
        self.render_progress_bar.configure(progress_color="#10b981")
        self.render_progress_bar.set(0.0)

        # Dòng trạng thái chi tiết
        self.lbl_status_desc = ctk.CTkLabel(
            self.view_rendering,
            text="Đang chuẩn bị quy trình xử lý...",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#f4f4f5"
        )
        self.lbl_status_desc.pack(padx=20, pady=(0, 10))

        # Thông số thời gian & specs
        spec_box = ctk.CTkFrame(self.view_rendering, fg_color="#1c1c20", corner_radius=6)
        spec_box.pack(fill="x", padx=20, pady=(0, 12))
        
        self.lbl_elapsed_time = ctk.CTkLabel(
            spec_box,
            text="⏱ Thời gian đã chạy: 00:00",
            font=ctk.CTkFont(size=11)
        )
        self.lbl_elapsed_time.pack(side="left", padx=12, pady=6)

        self.lbl_render_specs = ctk.CTkLabel(
            spec_box,
            text="1080p @ 6000 kbps • H.264",
            font=ctk.CTkFont(size=11),
            text_color="#38bdf8"
        )
        self.lbl_render_specs.pack(side="right", padx=12, pady=6)

        # Mini Log box để quan sát FFmpeg và AI
        ctk.CTkLabel(self.view_rendering, text="Nhật ký xử lý (Log):", font=ctk.CTkFont(size=11), text_color="#71717a").pack(anchor="w", padx=20, pady=(4, 2))
        self.txt_mini_log = ctk.CTkTextbox(
            self.view_rendering,
            height=130,
            fg_color="#0d0d10",
            font=ctk.CTkFont(family="Consolas", size=10),
            corner_radius=6
        )
        self.txt_mini_log.pack(fill="both", expand=True, padx=20, pady=(0, 14))

        # Nút hủy xuất
        self.btn_cancel_render = ctk.CTkButton(
            self.view_rendering,
            text="🛑  HỦY XUẤT VIDEO",
            height=40,
            fg_color="#ef4444",
            hover_color="#dc2626",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_cancel_clicked
        )
        self.btn_cancel_render.pack(fill="x", padx=20, pady=(0, 10))

    # ==========================
    # VIEW 3: XUẤT THÀNH CÔNG (SUCCESS)
    # ==========================
    def _build_finished_view(self):
        self.view_finished = ctk.CTkFrame(self.container, fg_color="transparent")

        ctk.CTkLabel(
            self.view_finished,
            text="🎉",
            font=ctk.CTkFont(size=56)
        ).pack(pady=(28, 4))

        ctk.CTkLabel(
            self.view_finished,
            text="XUẤT VIDEO THÀNH CÔNG!",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color="#10b981"
        ).pack(pady=(0, 16))

        # Khối thông tin kết quả
        self.succ_info_box = ctk.CTkFrame(self.view_finished, fg_color="#1e1e24", corner_radius=8, border_width=1, border_color="#2c2c34")
        self.succ_info_box.pack(fill="x", padx=20, pady=(0, 24))

        p_inner = ctk.CTkFrame(self.succ_info_box, fg_color="transparent")
        p_inner.pack(fill="x", padx=16, pady=16)

        self.lbl_succ_file = ctk.CTkLabel(p_inner, text="📁 File: ...", font=ctk.CTkFont(size=12, weight="bold"), anchor="w", justify="left")
        self.lbl_succ_file.pack(fill="x", pady=2)

        self.lbl_succ_size = ctk.CTkLabel(p_inner, text="💾 Dung lượng thực tế: ...", font=ctk.CTkFont(size=12), anchor="w")
        self.lbl_succ_size.pack(fill="x", pady=2)

        self.lbl_succ_duration = ctk.CTkLabel(p_inner, text="⏱ Tổng thời gian kết xuất: ...", font=ctk.CTkFont(size=12), anchor="w")
        self.lbl_succ_duration.pack(fill="x", pady=2)

        # 3 Nút thao tác nhanh
        btn_grid = ctk.CTkFrame(self.view_finished, fg_color="transparent")
        btn_grid.pack(fill="x", padx=20, pady=(0, 12))

        btn_play = ctk.CTkButton(
            btn_grid,
            text="🎬  Xem video ngay",
            height=44,
            fg_color="#10b981",
            hover_color="#059669",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._open_rendered_video
        )
        btn_play.pack(fill="x", pady=4)

        btn_open_folder = ctk.CTkButton(
            btn_grid,
            text="📂  Mở thư mục chứa video",
            height=40,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._open_output_folder
        )
        btn_open_folder.pack(fill="x", pady=4)

        btn_done = ctk.CTkButton(
            btn_grid,
            text="Đóng cửa sổ",
            height=36,
            fg_color="#27272a",
            hover_color="#3f3f46",
            command=self._on_close
        )
        btn_done.pack(fill="x", pady=4)

    # ==========================
    # LOGIC CHUYỂN ĐỔI VIEW & TÍNH TOÁN
    # ==========================
    def _show_view(self, view_name: str):
        self.view_settings.pack_forget()
        self.view_rendering.pack_forget()
        self.view_finished.pack_forget()

        if view_name == "settings":
            self.view_settings.pack(fill="both", expand=True)
        elif view_name == "rendering":
            self.view_rendering.pack(fill="both", expand=True)
        elif view_name == "finished":
            self.view_finished.pack(fill="both", expand=True)

    def _browse_folder(self):
        cur = self.ent_folder.get().strip()
        f = filedialog.askdirectory(title="Chọn thư mục lưu video", initialdir=cur or None)
        if f:
            self.ent_folder.delete(0, "end")
            self.ent_folder.insert(0, f)

    def _on_bitrate_changed(self, choice: str):
        if "Tùy chỉnh" in choice:
            self.custom_bitrate_frame.pack(fill="x", pady=(0, 6))
        else:
            self.custom_bitrate_frame.pack_forget()
        self._update_estimation()

    def _get_target_resolution(self) -> tuple[int, int]:
        choice = self.seg_res.get()
        is_vert = self.orig_h > self.orig_w

        if "720" in choice:
            return (720, 1280) if is_vert else (1280, 720)
        elif "2K" in choice:
            return (1440, 2560) if is_vert else (2560, 1440)
        elif "4K" in choice:
            return (2160, 3840) if is_vert else (3840, 2160)
        elif "Gốc" in choice:
            return (self.orig_w, self.orig_h)
        else: # 1080p
            return (1080, 1920) if is_vert else (1920, 1080)

    def _get_bitrate_kbps(self) -> int:
        choice = self.cbo_bitrate.get()
        if "16000" in choice:
            return 16000
        elif "10000" in choice:
            return 10000
        elif "3500" in choice:
            return 3500
        elif "Tùy chỉnh" in choice:
            try:
                val = int(self.ent_custom_bitrate.get().strip())
                return max(500, val)
            except Exception:
                return 6000
        return 6000 # Tiêu chuẩn

    def _update_estimation(self):
        # 1. Thời lượng
        m = int(self.total_duration // 60)
        s = int(self.total_duration % 60)
        dur_str = f"{m:02d}:{s:02d}"
        self.lbl_card_duration.configure(text=f"⏱ Thời lượng video: {dur_str}")

        # 2. Độ phân giải & FPS
        tw, th = self._get_target_resolution()
        fps_choice = self.cbo_fps.get().split(" ")[0]
        codec_choice = "H.264" if "H.264" in self.cbo_codec.get() else "H.265"
        self.lbl_card_resolution.configure(text=f"📐 Định dạng xuất: {tw}x{th} • {fps_choice} • {codec_choice}")

        # 3. Ước tính dung lượng
        bitrate_kbps = self._get_bitrate_kbps()
        # Audio aac 192 kbps
        total_bitrate_bps = (bitrate_kbps + 192) * 1000
        est_bytes = (total_bitrate_bps / 8.0) * max(1.0, self.total_duration)
        est_mb = est_bytes / (1024 * 1024)

        if est_mb >= 1024:
            size_str = f"~{est_mb / 1024:.2f} GB"
        else:
            size_str = f"~{est_mb:.1f} MB"

        self.lbl_card_size.configure(text=f"💾 Dung lượng ước tính: {size_str}")

    def _on_start_clicked(self):
        filename = self.ent_filename.get().strip()
        folder = self.ent_folder.get().strip()

        if not filename:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập tên file video!")
            return
        if not folder or not Path(folder).exists():
            messagebox.showwarning("Cảnh báo", "Thư mục lưu video không tồn tại! Vui lòng chọn lại.")
            return

        fmt = self.seg_format.get().lower()
        if not filename.endswith(f".{fmt}"):
            filename = f"{filename}.{fmt}"

        output_path = Path(folder) / filename
        self.final_output_file = output_path

        # Lấy thông số export
        tw, th = self._get_target_resolution()
        bitrate_kbps = self._get_bitrate_kbps()
        fps_opt = self.cbo_fps.get().split(" ")[0]
        codec = "H.264" if "H.264" in self.cbo_codec.get() else "H.265"

        export_settings = {
            "resolution": self.seg_res.get(),
            "target_width": tw,
            "target_height": th,
            "bitrate_kbps": bitrate_kbps,
            "fps": fps_opt,
            "codec": codec,
            "format": fmt,
            "audio_bitrate": "192k"
        }

        # Chuyển sang View 2 (Rendering)
        self.lbl_render_target_name.configure(text=f"{filename}")
        self.lbl_render_specs.configure(text=f"{tw}x{th} • {bitrate_kbps} kbps • {codec}")
        self.render_progress_bar.set(0.0)
        self.lbl_big_percent.configure(text="0%")
        self.lbl_status_desc.configure(text="Đang khởi tạo các tác vụ AI & FFmpeg...")
        self.txt_mini_log.delete("1.0", "end")
        
        self.start_time = time.time()
        self.timer_running = True
        self._timer_loop()

        self._show_view("rendering")

        # Kích hoạt pipeline
        self.on_start_export(export_settings, output_path, self)

    def _timer_loop(self):
        if not self.timer_running:
            return
        elapsed = int(time.time() - self.start_time)
        m = elapsed // 60
        s = elapsed % 60
        self.lbl_elapsed_time.configure(text=f"⏱ Thời gian đã chạy: {m:02d}:{s:02d}")
        self.after(1000, self._timer_loop)

    def update_progress(self, ratio: float, status_msg: str):
        """Cập nhật thanh tiến trình render từ ngoài pipeline gọi vào."""
        def upd():
            pct = int(min(1.0, max(0.0, ratio)) * 100)
            self.render_progress_bar.set(ratio)
            self.lbl_big_percent.configure(text=f"{pct}%")
            self.lbl_status_desc.configure(text=status_msg)
        self.after(0, upd)

    def append_log(self, log_line: str):
        """Thêm 1 dòng log vào mini log box."""
        def app():
            self.txt_mini_log.insert("end", log_line + "\n")
            self.txt_mini_log.see("end")
        self.after(0, app)

    def show_success(self, final_video: Path):
        """Hiển thị màn hình hoàn tất thành công."""
        self.timer_running = False
        self.final_output_file = final_video

        elapsed = int(time.time() - self.start_time)
        m = elapsed // 60
        s = elapsed % 60
        dur_str = f"{m} phút {s} giây" if m > 0 else f"{s} giây"

        size_mb = 0.0
        try:
            size_mb = final_video.stat().st_size / (1024 * 1024)
        except Exception:
            pass

        def finish():
            self.lbl_succ_file.configure(text=f"📁 File: {final_video.name}")
            self.lbl_succ_size.configure(text=f"💾 Dung lượng: {size_mb:.1f} MB ({final_video.stat().st_size:,} bytes)")
            self.lbl_succ_duration.configure(text=f"⏱ Tổng thời gian kết xuất: {dur_str}")
            self._show_view("finished")

        self.after(0, finish)

    def show_error(self, err_msg: str):
        """Hiển thị thông báo lỗi khi render thất bại."""
        self.timer_running = False
        def err():
            self.btn_cancel_render.configure(text="Đóng cửa sổ", fg_color="#3f3f46", command=self._on_close)
            self.lbl_status_desc.configure(text=f"Lỗi: {err_msg}", text_color="#ef4444")
            messagebox.showerror("Lỗi kết xuất", f"Quá trình xuất video gặp sự cố:\n{err_msg}")
        self.after(0, err)

    def _on_cancel_clicked(self):
        if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn hủy quá trình xuất video này?"):
            self.timer_running = False
            if self.on_cancel_export:
                self.on_cancel_export()
            self.lbl_status_desc.configure(text="Đã dừng tiến trình theo lệnh người dùng.", text_color="#f59e0b")
            self.btn_cancel_render.configure(text="Đóng", fg_color="#3f3f46", command=self._on_close)

    def _open_rendered_video(self):
        if self.final_output_file and self.final_output_file.exists():
            try:
                os.startfile(str(self.final_output_file))
            except Exception as e:
                messagebox.showerror("Lỗi", f"Không thể mở file video: {e}")

    def _open_output_folder(self):
        if self.final_output_file and self.final_output_file.exists():
            try:
                subprocess.Popen(f'explorer /select,"{str(self.final_output_file)}"')
            except Exception:
                try:
                    os.startfile(str(self.final_output_file.parent))
                except Exception as e:
                    messagebox.showerror("Lỗi", f"Không thể mở thư mục: {e}")

    def _on_close(self):
        if self.timer_running:
            if not messagebox.askyesno("Cảnh báo", "Video đang được kết xuất. Bạn có chắc muốn đóng và hủy bỏ?"):
                return
            if self.on_cancel_export:
                self.on_cancel_export()
        self.timer_running = False
        self.grab_release()
        self.destroy()
