import os
import customtkinter as ctk
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox
from pathlib import Path
from typing import Dict, Any, Callable, Optional
import threading

from utils.system_fonts import get_system_fonts
from utils.config_manager import config_manager
from core.capcut_service import capcut_service
from core.pipeline import PipelineRunner
from utils.logger import app_logger

class PanelRight(ctk.CTkFrame):
    """
    Cột bên phải (CapCut Style):
    - Khu vực trên: Các Tab cài đặt thông số chi tiết (Phụ đề, Lồng tiếng, Logo, Dịch thuật, Log).
    - Khu vực dưới cùng (Bottom Footer): Nơi lưu file, Progress Bar, và Nút Bắt đầu chạy xuất video.
    """
    def __init__(
        self,
        master,
        app_state: Dict[str, Any],
        preview_canvas,
        on_state_updated: Callable[[], None],
        **kwargs
    ):
        super().__init__(master, fg_color="#18181b", width=380, corner_radius=8, **kwargs)
        self.app_state = app_state
        self.preview_canvas = preview_canvas
        self.on_state_updated = on_state_updated

        self.fonts = get_system_fonts()
        self.presets = config_manager.load_presets()
        self.voices = capcut_service.get_vietnamese_voices()
        self.voice_map = {f"{v['display_name']} ({v['voice_type']})": v["voice_type"] for v in self.voices}

        self.active_runner: Optional[PipelineRunner] = None
        self.pack_propagate(False)

        self._build_ui()
        app_logger.register_callback(self._on_log_received)

    def _build_ui(self):
        # 1. Header & Segmented Button chọn nhóm thông số
        top_header = ctk.CTkFrame(self, fg_color="transparent")
        top_header.pack(fill="x", padx=10, pady=(8, 4))

        lbl_head = ctk.CTkLabel(
            top_header,
            text="THÔNG SỐ & CẤU HÌNH",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="#38bdf8"
        )
        lbl_head.pack(anchor="w", padx=4, pady=(2, 6))

        self.seg_tab = ctk.CTkSegmentedButton(
            self,
            values=["💬 Phụ đề", "🎙 Lồng tiếng", "🖼 Logo", "🌐 Dịch", "📋 Log"],
            command=self._on_tab_changed,
            selected_color="#0284c7"
        )
        self.seg_tab.pack(fill="x", padx=10, pady=(0, 6))
        self.seg_tab.set("💬 Phụ đề")

        # 2. Vùng nội dung cuộn linh hoạt cho các nhóm cài đặt
        self.body_container = ctk.CTkFrame(self, fg_color="transparent")
        self.body_container.pack(fill="both", expand=True, padx=8, pady=4)

        # Tạo sẵn các trang con
        self.frame_subtitles = self._create_subtitles_view()
        self.frame_tts = self._create_tts_view()
        self.frame_overlay = self._create_overlay_view()
        self.frame_translation = self._create_translation_view()
        self.frame_log = self._create_log_view()

        # Hiển thị trang mặc định
        self.frame_subtitles.pack(fill="both", expand=True)

        # 3. FOOTER DƯỚI CÙNG: Đường dẫn xuất file, Progress Bar & NÚT BẮT ĐẦU CHẠY
        self._build_bottom_footer()

    # ==========================
    # VIEW 1: CÀI ĐẶT PHỤ ĐỀ
    # ==========================
    def _create_subtitles_view(self) -> ctk.CTkScrollableFrame:
        view = ctk.CTkScrollableFrame(self.body_container, fg_color="#202024", corner_radius=6)
        
        # Font & Size
        ctk.CTkLabel(view, text="Font chữ hệ thống:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(8, 2))
        self.cbo_font = ctk.CTkComboBox(view, values=self.fonts[:50], width=260, command=self._on_font_changed)
        self.cbo_font.pack(fill="x", padx=8, pady=(0, 6))

        size_row = ctk.CTkFrame(view, fg_color="transparent")
        size_row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(size_row, text="Cỡ chữ (% màn hình):").pack(side="left")
        self.lbl_font_size = ctk.CTkLabel(size_row, text="5.5%", font=ctk.CTkFont(weight="bold"))
        self.lbl_font_size.pack(side="right")
        self.slider_font_size = ctk.CTkSlider(view, from_=2.0, to=15.0, number_of_steps=130, command=self._on_font_size_changed)
        self.slider_font_size.pack(fill="x", padx=8, pady=(0, 8))
        self.slider_font_size.set(5.5)

        # Màu chữ & Viền
        color_row = ctk.CTkFrame(view, fg_color="transparent")
        color_row.pack(fill="x", padx=8, pady=4)
        
        # Nút chọn màu chữ
        ctk.CTkLabel(color_row, text="Màu chữ:").pack(side="left")
        self.btn_txt_col = ctk.CTkButton(color_row, text="", width=30, height=24, fg_color="#FFE600", command=self._pick_text_color)
        self.btn_txt_col.pack(side="left", padx=6)

        # Nút chọn màu viền
        ctk.CTkLabel(color_row, text="Màu viền:").pack(side="left", padx=(10, 0))
        self.btn_brd_col = ctk.CTkButton(color_row, text="", width=30, height=24, fg_color="#000000", command=self._pick_border_color)
        self.btn_brd_col.pack(side="left", padx=6)

        # Độ dày viền
        bw_row = ctk.CTkFrame(view, fg_color="transparent")
        bw_row.pack(fill="x", padx=8, pady=(6, 2))
        ctk.CTkLabel(bw_row, text="Độ dày viền:").pack(side="left")
        self.lbl_bw = ctk.CTkLabel(bw_row, text="3px", font=ctk.CTkFont(weight="bold"))
        self.lbl_bw.pack(side="right")
        self.slider_bw = ctk.CTkSlider(view, from_=0, to=8, number_of_steps=8, command=self._on_bw_changed)
        self.slider_bw.pack(fill="x", padx=8, pady=(0, 8))
        self.slider_bw.set(3)

        # Hiệu ứng
        ctk.CTkLabel(view, text="Hiệu ứng động phụ đề:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(4, 2))
        self.cbo_effect = ctk.CTkComboBox(
            view,
            values=["Fade In/Out", "Typewriter", "Slide Up", "Slide Down", "Zoom In", "None"],
            command=self._on_effect_changed
        )
        self.cbo_effect.pack(fill="x", padx=8, pady=(0, 10))
        self.cbo_effect.set("Fade In/Out")

        # Căn nhanh vị trí phụ đề
        ctk.CTkLabel(view, text="Vị trí phụ đề nhanh:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(4, 2))
        pos_row = ctk.CTkFrame(view, fg_color="transparent")
        pos_row.pack(fill="x", padx=8, pady=(0, 10))
        ctk.CTkButton(pos_row, text="Đỉnh", width=70, height=26, command=lambda: self._set_quick_sub_pos(0.5, 0.15)).pack(side="left", padx=2)
        ctk.CTkButton(pos_row, text="Giữa", width=70, height=26, command=lambda: self._set_quick_sub_pos(0.5, 0.50)).pack(side="left", padx=2)
        ctk.CTkButton(pos_row, text="Đáy", width=70, height=26, command=lambda: self._set_quick_sub_pos(0.5, 0.85)).pack(side="left", padx=2)

        # Preset Style
        ctk.CTkLabel(view, text="Preset Phong cách:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(4, 2))
        self.cbo_preset = ctk.CTkComboBox(view, values=list(self.presets.keys()))
        self.cbo_preset.pack(fill="x", padx=8, pady=(0, 4))
        btn_apply_p = ctk.CTkButton(view, text="Áp dụng Preset", fg_color="#3b82f6", hover_color="#2563eb", height=28, command=self._apply_preset)
        btn_apply_p.pack(fill="x", padx=8, pady=(0, 10))

        return view

    # ==========================
    # VIEW 2: CÀI ĐẶT LỒNG TIẾNG (TTS & DUCKING)
    # ==========================
    def _create_tts_view(self) -> ctk.CTkScrollableFrame:
        view = ctk.CTkScrollableFrame(self.body_container, fg_color="#202024", corner_radius=6)

        self.sw_tts = ctk.CTkSwitch(view, text="Bật thuyết minh (TTS tiếng Việt)", font=ctk.CTkFont(weight="bold"), command=self._on_tts_switched)
        self.sw_tts.pack(anchor="w", padx=8, pady=(8, 10))
        self.sw_tts.select()

        # Giọng đọc CapCut
        ctk.CTkLabel(view, text="Giọng đọc CapCut tiếng Việt:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(4, 2))
        self.cbo_voice = ctk.CTkComboBox(view, values=list(self.voice_map.keys()) or ["Mặc định"], command=self._on_voice_changed)
        self.cbo_voice.pack(fill="x", padx=8, pady=(0, 4))

        self.btn_preview_voice = ctk.CTkButton(view, text="🔊 Nghe thử giọng", fg_color="#374151", hover_color="#4b5563", height=26, command=self._test_voice)
        self.btn_preview_voice.pack(fill="x", padx=8, pady=(0, 10))

        # Tốc độ đọc
        rate_row = ctk.CTkFrame(view, fg_color="transparent")
        rate_row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(rate_row, text="Tốc độ nói:").pack(side="left")
        self.lbl_rate = ctk.CTkLabel(rate_row, text="1.00x", font=ctk.CTkFont(weight="bold"))
        self.lbl_rate.pack(side="right")
        self.slider_rate = ctk.CTkSlider(view, from_=0.6, to=1.8, command=self._on_rate_changed)
        self.slider_rate.pack(fill="x", padx=8, pady=(0, 8))
        self.slider_rate.set(1.0)

        # Âm lượng TTS & Video gốc
        vol_row = ctk.CTkFrame(view, fg_color="transparent")
        vol_row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(vol_row, text="Âm lượng TTS:").pack(side="left")
        self.lbl_tts_v = ctk.CTkLabel(vol_row, text="100%", font=ctk.CTkFont(weight="bold"))
        self.lbl_tts_v.pack(side="right")
        self.slider_tts_v = ctk.CTkSlider(view, from_=0.0, to=2.0, command=self._on_tts_v_changed)
        self.slider_tts_v.pack(fill="x", padx=8, pady=(0, 8))
        self.slider_tts_v.set(1.0)

        # Auto Ducking
        self.sw_ducking = ctk.CTkSwitch(view, text="Bật Auto Audio Ducking", font=ctk.CTkFont(weight="bold"), command=self._on_duck_switched)
        self.sw_ducking.pack(anchor="w", padx=8, pady=(8, 4))
        self.sw_ducking.select()

        duck_row = ctk.CTkFrame(view, fg_color="transparent")
        duck_row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(duck_row, text="Mức hạ nhạc nền:").pack(side="left")
        self.lbl_duck = ctk.CTkLabel(duck_row, text="18%", font=ctk.CTkFont(weight="bold"))
        self.lbl_duck.pack(side="right")
        self.slider_duck = ctk.CTkSlider(view, from_=0.05, to=0.40, command=self._on_duck_changed)
        self.slider_duck.pack(fill="x", padx=8, pady=(0, 10))
        self.slider_duck.set(0.18)

        return view

    # ==========================
    # VIEW 3: CÀI ĐẶT WATERMARK / OVERLAY
    # ==========================
    def _create_overlay_view(self) -> ctk.CTkScrollableFrame:
        view = ctk.CTkScrollableFrame(self.body_container, fg_color="#202024", corner_radius=6)

        self.sw_ov = ctk.CTkSwitch(view, text="Bật Watermark / Logo", font=ctk.CTkFont(weight="bold"), command=self._sync_overlay)
        self.sw_ov.pack(anchor="w", padx=8, pady=(8, 10))

        btn_pick_img = ctk.CTkButton(view, text="🖼 Chọn file ảnh Logo...", height=30, command=self._pick_overlay_image)
        btn_pick_img.pack(fill="x", padx=8, pady=(0, 4))
        self.lbl_ov_name = ctk.CTkLabel(view, text="Chưa chọn ảnh", font=ctk.CTkFont(size=10), text_color="#a1a1aa")
        self.lbl_ov_name.pack(fill="x", padx=8, pady=(0, 8))

        # Scale
        sc_row = ctk.CTkFrame(view, fg_color="transparent")
        sc_row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(sc_row, text="Tỷ lệ kích thước:").pack(side="left")
        self.lbl_ov_scale = ctk.CTkLabel(sc_row, text="100%", font=ctk.CTkFont(weight="bold"))
        self.lbl_ov_scale.pack(side="right")
        self.slider_ov_scale = ctk.CTkSlider(view, from_=0.1, to=2.0, command=self._on_ov_scale_changed)
        self.slider_ov_scale.pack(fill="x", padx=8, pady=(0, 8))
        self.slider_ov_scale.set(1.0)

        # Opacity
        op_row = ctk.CTkFrame(view, fg_color="transparent")
        op_row.pack(fill="x", padx=8, pady=2)
        ctk.CTkLabel(op_row, text="Độ mờ đục:").pack(side="left")
        self.lbl_ov_op = ctk.CTkLabel(op_row, text="100%", font=ctk.CTkFont(weight="bold"))
        self.lbl_ov_op.pack(side="right")
        self.slider_ov_op = ctk.CTkSlider(view, from_=0.1, to=1.0, command=self._on_ov_op_changed)
        self.slider_ov_op.pack(fill="x", padx=8, pady=(0, 10))
        self.slider_ov_op.set(1.0)

        # Tọa độ nhanh
        ctk.CTkLabel(view, text="Vị trí đặt Logo nhanh:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(4, 2))
        q_row1 = ctk.CTkFrame(view, fg_color="transparent")
        q_row1.pack(fill="x", padx=8, pady=2)
        ctk.CTkButton(q_row1, text="Trên Trái", width=110, height=26, command=lambda: self._set_ov_pos(40, 40)).pack(side="left", padx=2)
        ctk.CTkButton(q_row1, text="Trên Phải", width=110, height=26, command=lambda: self._set_ov_pos(1650, 40)).pack(side="right", padx=2)

        q_row2 = ctk.CTkFrame(view, fg_color="transparent")
        q_row2.pack(fill="x", padx=8, pady=2)
        ctk.CTkButton(q_row2, text="Dưới Trái", width=110, height=26, command=lambda: self._set_ov_pos(40, 950)).pack(side="left", padx=2)
        ctk.CTkButton(q_row2, text="Dưới Phải", width=110, height=26, command=lambda: self._set_ov_pos(1650, 950)).pack(side="right", padx=2)

        return view

    # ==========================
    # VIEW 4: CÀI ĐẶT DỊCH THUẬT
    # ==========================
    def _create_translation_view(self) -> ctk.CTkScrollableFrame:
        view = ctk.CTkScrollableFrame(self.body_container, fg_color="#202024", corner_radius=6)

        ctk.CTkLabel(view, text="Công cụ dịch thuật:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=8, pady=(8, 2))
        self.cbo_engine = ctk.CTkComboBox(
            view,
            values=["ChatGPT Web (Playwright)", "Google Translate (Nhanh / Miễn phí)"],
            command=self._on_engine_changed
        )
        self.cbo_engine.pack(fill="x", padx=8, pady=(0, 8))

        self.chk_headless = ctk.CTkCheckBox(view, text="Chạy ẩn trình duyệt ChatGPT (Headless)", command=self._on_headless_changed)
        self.chk_headless.pack(anchor="w", padx=8, pady=6)
        self.chk_headless.deselect()

        btn_login = ctk.CTkButton(
            view,
            text="🔑 Mở trình duyệt Đăng nhập ChatGPT",
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._open_chatgpt_for_login
        )
        btn_login.pack(fill="x", padx=8, pady=(4, 8))

        lbl_desc = ctk.CTkLabel(
            view,
            text="Ghi chú: Nhấn nút trên để đăng nhập ChatGPT một lần. Trình duyệt Chrome sẽ lưu phiên đăng nhập vĩnh viễn cho tất cả các lần sau.",
            font=ctk.CTkFont(size=10),
            text_color="#a1a1aa",
            wraplength=280,
            justify="left"
        )
        lbl_desc.pack(fill="x", padx=8, pady=(0, 10))

        return view

    # ==========================
    # VIEW 5: LOG CONSOLE REAL-TIME
    # ==========================
    def _create_log_view(self) -> ctk.CTkFrame:
        view = ctk.CTkFrame(self.body_container, fg_color="#202024", corner_radius=6)
        self.txt_log = ctk.CTkTextbox(
            view,
            fg_color="#09090b",
            font=ctk.CTkFont(family="Consolas", size=10),
            text_color="#e4e4e7"
        )
        self.txt_log.pack(fill="both", expand=True, padx=6, pady=6)
        return view

    # ==========================
    # BOTTOM FOOTER (NÚT BẮT ĐẦU CHẠY Ở DƯỚI CÙNG BÊN PHẢI)
    # ==========================
    def _build_bottom_footer(self):
        footer = ctk.CTkFrame(self, fg_color="#141416", corner_radius=8)
        footer.pack(fill="x", side="bottom", padx=8, pady=(4, 8))

        # Output video file picker
        out_lbl_row = ctk.CTkFrame(footer, fg_color="transparent")
        out_lbl_row.pack(fill="x", padx=8, pady=(8, 2))
        ctk.CTkLabel(out_lbl_row, text="Nơi lưu video xuất:", font=ctk.CTkFont(size=11, weight="bold")).pack(side="left")
        
        self.chk_open_done = ctk.CTkCheckBox(out_lbl_row, text="Mở khi xong", font=ctk.CTkFont(size=10))
        self.chk_open_done.pack(side="right")
        self.chk_open_done.select()

        out_input_row = ctk.CTkFrame(footer, fg_color="transparent")
        out_input_row.pack(fill="x", padx=8, pady=(0, 6))

        self.ent_output = ctk.CTkEntry(out_input_row, height=28, placeholder_text="Đường dẫn file .mp4 đầu ra...")
        self.ent_output.pack(side="left", fill="x", expand=True, padx=(0, 4))

        btn_browse_out = ctk.CTkButton(out_input_row, text="...", width=32, height=28, command=self._browse_output)
        btn_browse_out.pack(side="right")

        # Progress Bar & Trạng thái
        self.lbl_progress = ctk.CTkLabel(footer, text="Sẵn sàng xử lý video", font=ctk.CTkFont(size=11), text_color="#a1a1aa", anchor="w")
        self.lbl_progress.pack(fill="x", padx=8, pady=(2, 1))

        ctk.CTkLabel(
            footer,
            text="📺 Nhấn Xuất để mở bảng chỉnh Bitrate, Độ phân giải, FPS (CapCut Style)",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#38bdf8",
            anchor="w"
        ).pack(fill="x", padx=8, pady=(0, 4))

        self.progress_bar = ctk.CTkProgressBar(footer, height=10)
        self.progress_bar.pack(fill="x", padx=8, pady=(0, 8))
        self.progress_bar.set(0.0)

        # NÚT BẮT ĐẦU CHẠY & NÚT HỦY
        btn_row = ctk.CTkFrame(footer, fg_color="transparent")
        btn_row.pack(fill="x", padx=8, pady=(0, 8))

        self.btn_start = ctk.CTkButton(
            btn_row,
            text="🚀  XUẤT VIDEO...",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=42,
            command=self._start_pipeline
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_cancel = ctk.CTkButton(
            btn_row,
            text="🛑 HỦY",
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#ef4444",
            hover_color="#dc2626",
            width=70,
            height=42,
            state="disabled",
            command=self._cancel_pipeline
        )
        self.btn_cancel.pack(side="right")

    # ==========================
    # LOGIC CHUYỂN TAB VÀ ĐỒNG BỘ
    # ==========================
    def _on_tab_changed(self, choice):
        # Ẩn tất cả view
        for f in (self.frame_subtitles, self.frame_tts, self.frame_overlay, self.frame_translation, self.frame_log):
            f.pack_forget()

        if "Phụ đề" in choice:
            self.frame_subtitles.pack(fill="both", expand=True)
        elif "Lồng tiếng" in choice:
            self.frame_tts.pack(fill="both", expand=True)
        elif "Logo" in choice:
            self.frame_overlay.pack(fill="both", expand=True)
        elif "Dịch" in choice:
            self.frame_translation.pack(fill="both", expand=True)
        elif "Log" in choice:
            self.frame_log.pack(fill="both", expand=True)

    def set_output_path(self, path_str: str):
        self.ent_output.delete(0, "end")
        self.ent_output.insert(0, path_str)

    def _browse_output(self):
        f = filedialog.asksaveasfilename(
            title="Lưu video kết quả",
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4")]
        )
        if f:
            self.set_output_path(f)
            self.app_state["output_path"] = f

    def _sync_sub_style(self):
        style = self.app_state["subtitle_style"]
        style["font_family"] = self.cbo_font.get()
        style["font_size"] = round(float(self.slider_font_size.get()), 1)
        style["border_width"] = int(self.slider_bw.get())
        style["effect"] = self.cbo_effect.get()

        self.preview_canvas.set_subtitle_style(
            font_family=style["font_family"],
            font_size=style["font_size"],
            text_color=style["text_color"],
            border_color=style["border_color"],
            border_width=style["border_width"]
        )
        self.on_state_updated()

    def _on_font_changed(self, choice):
        self._sync_sub_style()

    def _on_font_size_changed(self, val):
        val = round(float(val), 1)
        self.lbl_font_size.configure(text=f"{val:.1f}%")
        self._sync_sub_style()

    def _on_bw_changed(self, val):
        self.lbl_bw.configure(text=f"{int(val)}px")
        self._sync_sub_style()

    def _on_effect_changed(self, choice):
        self._sync_sub_style()

    def _pick_text_color(self):
        c = colorchooser.askcolor(title="Chọn màu chữ")
        if c and c[1]:
            hex_c = c[1].upper()
            self.btn_txt_col.configure(fg_color=hex_c)
            self.app_state["subtitle_style"]["text_color"] = hex_c
            self._sync_sub_style()

    def _pick_border_color(self):
        c = colorchooser.askcolor(title="Chọn màu viền")
        if c and c[1]:
            hex_c = c[1].upper()
            self.btn_brd_col.configure(fg_color=hex_c)
            self.app_state["subtitle_style"]["border_color"] = hex_c
            self._sync_sub_style()

    def _set_quick_sub_pos(self, xr: float, yr: float):
        self.app_state["subtitle_style"]["sub_pos_x"] = xr
        self.app_state["subtitle_style"]["sub_pos_y"] = yr
        self.preview_canvas.set_subtitle_coords(xr, yr)
        self.on_state_updated()

    def _apply_preset(self):
        name = self.cbo_preset.get()
        if name in self.presets:
            p = self.presets[name]
            self.cbo_font.set(p.get("font_family", "Arial"))
            try:
                raw_pfs = float(p.get("font_size", 5.5))
            except Exception:
                raw_pfs = 5.5
            pfs = 5.5 if raw_pfs >= 18.0 else max(1.5, min(25.0, raw_pfs))
            self.slider_font_size.set(pfs)
            self.lbl_font_size.configure(text=f"{pfs:.1f}%")
            self.slider_bw.set(p.get("border_width", 3))
            self.lbl_bw.configure(text=f"{int(p.get('border_width', 3))}px")
            self.cbo_effect.set(p.get("effect", "None"))

            tc = p.get("text_color", "#FFE600")
            bc = p.get("border_color", "#000000")
            self.btn_txt_col.configure(fg_color=tc)
            self.btn_brd_col.configure(fg_color=bc)
            self.app_state["subtitle_style"]["text_color"] = tc
            self.app_state["subtitle_style"]["border_color"] = bc

            self._sync_sub_style()

    def _on_tts_switched(self):
        self.app_state["enable_tts"] = bool(self.sw_tts.get())
        self.on_state_updated()

    def _on_voice_changed(self, choice):
        vtype = self.voice_map.get(choice, "BV074_streaming")
        self.app_state["voice_type"] = vtype
        self.on_state_updated()

    def _on_rate_changed(self, val):
        self.lbl_rate.configure(text=f"{val:.2f}x")
        self.app_state["speech_rate"] = float(val)
        self.on_state_updated()

    def _on_tts_v_changed(self, val):
        self.lbl_tts_v.configure(text=f"{int(val*100)}%")
        self.app_state["tts_volume"] = float(val)
        self.on_state_updated()

    def _on_duck_switched(self):
        self.app_state["enable_ducking"] = bool(self.sw_ducking.get())
        self.on_state_updated()

    def _on_duck_changed(self, val):
        self.lbl_duck.configure(text=f"{int(val*100)}%")
        self.app_state["ducking_volume"] = float(val)
        self.on_state_updated()

    def _test_voice(self):
        choice = self.cbo_voice.get()
        vtype = self.voice_map.get(choice, "BV074_streaming")
        rate_val = self.slider_rate.get()
        self.btn_preview_voice.configure(state="disabled", text="Đang tạo...")

        def run_t():
            try:
                sample = [{"index": 1, "start_time": 0.0, "end_time": 2.0, "text": "Xin chào, đây là giọng đọc thử nghiệm.", "translation": "Xin chào, đây là giọng đọc thử nghiệm."}]
                res = capcut_service.generate_speech_for_subtitles(sample, voice_type=vtype, speech_rate=rate_val)
                if res and res[0].get("audio_path"):
                    import subprocess
                    subprocess.run(["ffplay", "-nodisp", "-autoexit", str(res[0]["audio_path"])], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                app_logger.warning(f"Lỗi thử giọng: {e}")
            finally:
                self.after(0, lambda: self.btn_preview_voice.configure(state="normal", text="🔊 Nghe thử giọng"))
        threading.Thread(target=run_t, daemon=True).start()

    def _pick_overlay_image(self):
        f = filedialog.askopenfilename(title="Chọn ảnh Watermark", filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp")])
        if f:
            self.app_state["overlay_info"]["path"] = f
            self.lbl_ov_name.configure(text=Path(f).name)
            self.sw_ov.select()
            self._sync_overlay()

    def _on_ov_scale_changed(self, val):
        self.lbl_ov_scale.configure(text=f"{int(val*100)}%")
        self._sync_overlay()

    def _on_ov_op_changed(self, val):
        self.lbl_ov_op.configure(text=f"{int(val*100)}%")
        self._sync_overlay()

    def _set_ov_pos(self, x: int, y: int):
        self.app_state["overlay_info"]["x"] = x
        self.app_state["overlay_info"]["y"] = y
        self._sync_overlay()

    def _sync_overlay(self):
        ov = self.app_state["overlay_info"]
        ov["enabled"] = bool(self.sw_ov.get())
        ov["scale"] = float(self.slider_ov_scale.get())
        ov["opacity"] = float(self.slider_ov_op.get())
        self.preview_canvas.set_overlay_info(ov)
        self.on_state_updated()

    def _on_engine_changed(self, choice):
        self.app_state["translation_engine"] = "chatgpt" if "ChatGPT" in choice else "google"
        self.on_state_updated()

    def _on_headless_changed(self):
        self.app_state["chatgpt_headless"] = bool(self.chk_headless.get())
        self.on_state_updated()

    def _open_chatgpt_for_login(self):
        try:
            from core.translator import translator
            translator.open_browser_for_login()
            messagebox.showinfo(
                "Đăng nhập ChatGPT",
                "Đã mở trình duyệt Chrome!\n\n"
                "1. Bạn hãy nhấn 'Log in' và đăng nhập tài khoản ChatGPT của mình.\n"
                "2. Sau khi đăng nhập xong, bạn có thể đóng trình duyệt hoặc để nguyên.\n\n"
                "Hệ thống sẽ tự động lưu phiên đăng nhập vĩnh viễn cho tất cả các lần dịch video tiếp theo."
            )
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể mở trình duyệt: {e}")

    def _on_log_received(self, msg: str, lvl: str):
        def append():
            self.txt_log.insert("end", msg + "\n")
            self.txt_log.see("end")
            if hasattr(self, "_active_dialog") and self._active_dialog and self._active_dialog.winfo_exists():
                self._active_dialog.append_log(msg)
        self.after(0, append)

    def _start_pipeline(self):
        vp = self.app_state.get("video_path")
        if not vp or not Path(vp).exists():
            messagebox.showwarning("Thông báo", "Vui lòng chọn file video đầu vào ở cột bên trái trước khi xuất!")
            return

        from ui.export_dialog import ExportDialog
        ExportDialog(
            master=self.winfo_toplevel(),
            app_state=self.app_state,
            on_start_export=self._execute_export_pipeline,
            on_cancel_export=self._cancel_pipeline
        )

    def _execute_export_pipeline(self, export_settings: Dict[str, Any], output_path: Path, dialog: Any):
        vp = self.app_state.get("video_path")
        self.app_state["output_path"] = str(output_path)
        self.app_state["export_settings"] = export_settings
        self.set_output_path(str(output_path))
        self._active_dialog = dialog

        self.btn_start.configure(state="disabled", fg_color="#374151")
        self.btn_cancel.configure(state="normal")
        self.progress_bar.set(0.0)

        # Chuyển sang tab Log
        self.seg_tab.set("📋 Log")
        self._on_tab_changed("📋 Log")

        def on_prog(ratio: float, status: str):
            def upd():
                self.progress_bar.set(ratio)
                self.lbl_progress.configure(text=f"{status} ({int(ratio*100)}%)")
                if dialog and dialog.winfo_exists():
                    dialog.update_progress(ratio, status)
            self.after(0, upd)

        def on_sub_ready(subs):
            self.app_state["manual_subtitles"] = subs

        def on_succ(final_video: Path):
            def finish():
                self.btn_start.configure(state="normal", fg_color="#10b981")
                self.btn_cancel.configure(state="disabled")
                self.progress_bar.set(1.0)
                self.lbl_progress.configure(text="Đã hoàn tất xuất video! 🎉")
                if dialog and dialog.winfo_exists():
                    dialog.show_success(final_video)
                if self.chk_open_done.get():
                    try:
                        os.startfile(str(final_video))
                    except Exception:
                        pass
            self.after(0, finish)

        def on_err(exc: Exception):
            def fail():
                self.btn_start.configure(state="normal", fg_color="#10b981")
                self.btn_cancel.configure(state="disabled")
                self.lbl_progress.configure(text=f"Lỗi: {exc}")
                if dialog and dialog.winfo_exists():
                    dialog.show_error(str(exc))
                else:
                    messagebox.showerror("Lỗi xử lý", f"Có lỗi xảy ra:\n{exc}")
            self.after(0, fail)

        self.active_runner = PipelineRunner(
            video_path=Path(vp),
            output_path=output_path,
            settings=self.app_state,
            on_progress=on_prog,
            on_subtitles_ready=on_sub_ready,
            on_success=on_succ,
            on_error=on_err
        )
        self.active_runner.start()

    def _cancel_pipeline(self):
        if self.active_runner:
            self.active_runner.cancel()
            self.btn_cancel.configure(state="disabled")
            self.lbl_progress.configure(text="Đang hủy tiến trình...")
