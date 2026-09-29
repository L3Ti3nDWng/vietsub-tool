import customtkinter as ctk
import tkinter as tk
from tkinter import colorchooser, messagebox
from typing import Dict, Any, Callable, Optional

from utils.system_fonts import get_system_fonts
from utils.config_manager import config_manager
from ui.subtitle_dialog import SubtitleEditorDialog
from utils.logger import app_logger

class TabSubtitles(ctk.CTkFrame):
    """
    Tab 2: Cài đặt phụ đề chuyên nghiệp (Font hệ thống, màu chữ, màu viền, hiệu ứng, preset)
    """
    def __init__(self, master, app_state: Dict[str, Any], preview_canvas, on_state_updated: Callable[[], None], **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app_state = app_state
        self.preview_canvas = preview_canvas
        self.on_state_updated = on_state_updated

        self.fonts = get_system_fonts()
        self.presets = config_manager.load_presets()

        self._build_ui()
        self._load_from_state()

    def _build_ui(self):
        # Chia layout 2 cột: Cột trái (Font, Màu, Hiệu ứng), Cột phải (Presets & Quản lý phụ đề)
        self.grid_columnconfigure((0, 1), weight=1, uniform="col")
        self.grid_rowconfigure(0, weight=1)

        # === CỘT TRÁI: ĐỊNH DẠNG PHỤ ĐỀ ===
        col_left = ctk.CTkScrollableFrame(self, fg_color="#18181b", corner_radius=8)
        col_left.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        ctk.CTkLabel(
            col_left,
            text="Kiểu dáng & Định dạng Phụ đề",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # 1. Font Family
        f_frame = ctk.CTkFrame(col_left, fg_color="#202024")
        f_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(f_frame, text="Font chữ (Hệ thống):", width=140, anchor="w").pack(side="left", padx=10, pady=8)
        
        self.cbo_font = ctk.CTkComboBox(
            f_frame,
            values=self.fonts[:60], # 60 font thông dụng nhất
            command=self._on_font_changed,
            width=200
        )
        self.cbo_font.pack(side="right", padx=10, pady=8)

        # 2. Font Size (% chiều cao màn hình)
        fs_frame = ctk.CTkFrame(col_left, fg_color="#202024")
        fs_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(fs_frame, text="Cỡ chữ (% chiều cao):", width=140, anchor="w").pack(side="left", padx=10, pady=8)
        self.lbl_font_size_val = ctk.CTkLabel(fs_frame, text="5.5%", width=50)
        self.lbl_font_size_val.pack(side="right", padx=(0, 10))
        self.slider_font_size = ctk.CTkSlider(
            fs_frame,
            from_=2.0,
            to=15.0,
            number_of_steps=130,
            command=self._on_font_size_changed
        )
        self.slider_font_size.pack(side="right", fill="x", expand=True, padx=10)

        # 3. Màu chữ chính (Text Color)
        tc_frame = ctk.CTkFrame(col_left, fg_color="#202024")
        tc_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(tc_frame, text="Màu chữ chính:", width=140, anchor="w").pack(side="left", padx=10, pady=8)
        
        self.btn_text_color = ctk.CTkButton(
            tc_frame,
            text="",
            width=40,
            height=28,
            fg_color="#FFE600",
            hover_color="#E5CF00",
            command=self._pick_text_color
        )
        self.btn_text_color.pack(side="right", padx=10, pady=8)
        
        self.ent_text_color = ctk.CTkEntry(tc_frame, width=90)
        self.ent_text_color.insert(0, "#FFE600")
        self.ent_text_color.pack(side="right", padx=5)
        self.ent_text_color.bind("<Return>", lambda e: self._on_hex_text_changed())

        # 4. Màu viền chữ (Border / Outline Color)
        bc_frame = ctk.CTkFrame(col_left, fg_color="#202024")
        bc_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(bc_frame, text="Màu viền chữ:", width=140, anchor="w").pack(side="left", padx=10, pady=8)

        self.btn_border_color = ctk.CTkButton(
            bc_frame,
            text="",
            width=40,
            height=28,
            fg_color="#000000",
            hover_color="#18181b",
            command=self._pick_border_color
        )
        self.btn_border_color.pack(side="right", padx=10, pady=8)

        self.ent_border_color = ctk.CTkEntry(bc_frame, width=90)
        self.ent_border_color.insert(0, "#000000")
        self.ent_border_color.pack(side="right", padx=5)
        self.ent_border_color.bind("<Return>", lambda e: self._on_hex_border_changed())

        # 5. Độ dày viền (Border Width)
        bw_frame = ctk.CTkFrame(col_left, fg_color="#202024")
        bw_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(bw_frame, text="Độ dày viền:", width=140, anchor="w").pack(side="left", padx=10, pady=8)
        self.lbl_border_width_val = ctk.CTkLabel(bw_frame, text="3px", width=45)
        self.lbl_border_width_val.pack(side="right", padx=(0, 10))
        self.slider_border_width = ctk.CTkSlider(
            bw_frame,
            from_=0,
            to=8,
            number_of_steps=8,
            command=self._on_border_width_changed
        )
        self.slider_border_width.pack(side="right", fill="x", expand=True, padx=10)

        # 6. Hiệu ứng phụ đề (Effects)
        eff_frame = ctk.CTkFrame(col_left, fg_color="#202024")
        eff_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(eff_frame, text="Hiệu ứng động:", width=140, anchor="w").pack(side="left", padx=10, pady=8)
        
        self.cbo_effect = ctk.CTkComboBox(
            eff_frame,
            values=["None", "Fade In/Out", "Typewriter", "Slide Up", "Slide Down", "Zoom In"],
            command=self._on_effect_changed,
            width=200
        )
        self.cbo_effect.pack(side="right", padx=10, pady=8)
        self.cbo_effect.set("Fade In/Out")

        # 7. Vị trí phụ đề (Tọa độ X & Y)
        pos_frame = ctk.CTkFrame(col_left, fg_color="#202024")
        pos_frame.pack(fill="x", padx=15, pady=5)
        ctk.CTkLabel(pos_frame, text="Tọa độ vị trí (X, Y):", width=140, anchor="w").pack(side="left", padx=10, pady=8)
        
        btn_pos_top = ctk.CTkButton(pos_frame, text="Đỉnh", width=50, command=lambda: self._set_quick_pos(0.5, 0.15))
        btn_pos_top.pack(side="right", padx=4)
        btn_pos_mid = ctk.CTkButton(pos_frame, text="Giữa", width=50, command=lambda: self._set_quick_pos(0.5, 0.50))
        btn_pos_mid.pack(side="right", padx=4)
        btn_pos_bot = ctk.CTkButton(pos_frame, text="Đáy", width=50, command=lambda: self._set_quick_pos(0.5, 0.85))
        btn_pos_bot.pack(side="right", padx=4)

        # === CỘT PHẢI: PRESETS & QUẢN LÝ NỘI DUNG ===
        col_right = ctk.CTkScrollableFrame(self, fg_color="#18181b", corner_radius=8)
        col_right.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)

        ctk.CTkLabel(
            col_right,
            text="Hệ thống Preset Style & Dữ liệu",
            font=ctk.CTkFont(size=15, weight="bold")
        ).pack(anchor="w", padx=15, pady=(15, 10))

        # Khung Preset
        preset_box = ctk.CTkFrame(col_right, fg_color="#202024")
        preset_box.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(preset_box, text="Chọn Preset mẫu:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=12, pady=(10, 4))
        self.cbo_presets = ctk.CTkComboBox(
            preset_box,
            values=list(self.presets.keys()),
            width=280
        )
        self.cbo_presets.pack(fill="x", padx=12, pady=4)

        btn_row_pre = ctk.CTkFrame(preset_box, fg_color="transparent")
        btn_row_pre.pack(fill="x", padx=12, pady=8)

        btn_apply_pre = ctk.CTkButton(
            btn_row_pre,
            text="Áp dụng Preset",
            fg_color="#3b82f6",
            hover_color="#2563eb",
            command=self._apply_preset
        )
        btn_apply_pre.pack(side="left", fill="x", expand=True, padx=(0, 4))

        btn_del_pre = ctk.CTkButton(
            btn_row_pre,
            text="Xóa",
            fg_color="#ef4444",
            hover_color="#dc2626",
            width=60,
            command=self._delete_preset
        )
        btn_del_pre.pack(side="right", padx=(4, 0))

        # Lưu Preset mới
        save_pre_box = ctk.CTkFrame(col_right, fg_color="#202024")
        save_pre_box.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(save_pre_box, text="Lưu cấu hình hiện tại thành Preset:").pack(anchor="w", padx=12, pady=(10, 4))
        self.ent_new_preset_name = ctk.CTkEntry(save_pre_box, placeholder_text="Nhập tên Preset...")
        self.ent_new_preset_name.pack(fill="x", padx=12, pady=4)

        btn_save_pre = ctk.CTkButton(
            save_pre_box,
            text="💾 Lưu Preset Mới",
            fg_color="#10b981",
            hover_color="#059669",
            command=self._save_new_preset
        )
        btn_save_pre.pack(fill="x", padx=12, pady=(4, 10))

        # Nút mở bảng chỉnh sửa phụ đề chi tiết
        edit_box = ctk.CTkFrame(col_right, fg_color="#202024")
        edit_box.pack(fill="x", padx=15, pady=10)

        ctk.CTkLabel(
            edit_box,
            text="Bảng phụ đề & Dịch thuật:",
            font=ctk.CTkFont(weight="bold")
        ).pack(anchor="w", padx=12, pady=(10, 4))

        lbl_desc = ctk.CTkLabel(
            edit_box,
            text="Xem lại bản dịch, tinh chỉnh mốc thời gian hoặc sửa từng câu trước khi xuất video.",
            font=ctk.CTkFont(size=11),
            text_color="#a1a1aa",
            wraplength=300,
            justify="left"
        )
        lbl_desc.pack(anchor="w", padx=12, pady=4)

        self.btn_open_editor = ctk.CTkButton(
            edit_box,
            text="📝 Mở bảng chỉnh sửa phụ đề",
            fg_color="#8b5cf6",
            hover_color="#7c3aed",
            height=36,
            command=self._open_subtitle_dialog
        )
        self.btn_open_editor.pack(fill="x", padx=12, pady=(8, 12))

    def _load_from_state(self):
        style = self.app_state.get("subtitle_style", {})
        font_name = style.get("font_family", "Arial")
        if font_name in self.fonts:
            self.cbo_font.set(font_name)
        
        try:
            raw_fs = float(style.get("font_size", 5.5))
        except Exception:
            raw_fs = 5.5
        fs = 5.5 if raw_fs >= 18.0 else max(1.5, min(25.0, raw_fs))
        self.slider_font_size.set(fs)
        self.lbl_font_size_val.configure(text=f"{fs:.1f}%")

        tc = style.get("text_color", "#FFE600")
        self.ent_text_color.delete(0, "end")
        self.ent_text_color.insert(0, tc)
        self.btn_text_color.configure(fg_color=tc)

        bc = style.get("border_color", "#000000")
        self.ent_border_color.delete(0, "end")
        self.ent_border_color.insert(0, bc)
        self.btn_border_color.configure(fg_color=bc)

        bw = style.get("border_width", 3)
        self.slider_border_width.set(bw)
        self.lbl_border_width_val.configure(text=f"{int(bw)}px")

        eff = style.get("effect", "Fade In/Out")
        self.cbo_effect.set(eff)

    def _sync_to_state_and_preview(self):
        style = self.app_state["subtitle_style"]
        style["font_family"] = self.cbo_font.get()
        style["font_size"] = round(float(self.slider_font_size.get()), 1)
        style["text_color"] = self.ent_text_color.get().strip()
        style["border_color"] = self.ent_border_color.get().strip()
        style["border_width"] = int(self.slider_border_width.get())
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
        self._sync_to_state_and_preview()

    def _on_font_size_changed(self, val):
        val = round(float(val), 1)
        self.lbl_font_size_val.configure(text=f"{val:.1f}%")
        self._sync_to_state_and_preview()

    def _on_border_width_changed(self, val):
        self.lbl_border_width_val.configure(text=f"{int(val)}px")
        self._sync_to_state_and_preview()

    def _on_effect_changed(self, choice):
        self._sync_to_state_and_preview()

    def _pick_text_color(self):
        color = colorchooser.askcolor(title="Chọn màu chữ phụ đề", initialcolor=self.ent_text_color.get())
        if color and color[1]:
            hex_c = color[1].upper()
            self.ent_text_color.delete(0, "end")
            self.ent_text_color.insert(0, hex_c)
            self.btn_text_color.configure(fg_color=hex_c)
            self._sync_to_state_and_preview()

    def _pick_border_color(self):
        color = colorchooser.askcolor(title="Chọn màu viền phụ đề", initialcolor=self.ent_border_color.get())
        if color and color[1]:
            hex_c = color[1].upper()
            self.ent_border_color.delete(0, "end")
            self.ent_border_color.insert(0, hex_c)
            self.btn_border_color.configure(fg_color=hex_c)
            self._sync_to_state_and_preview()

    def _on_hex_text_changed(self):
        hex_c = self.ent_text_color.get().strip()
        if hex_c.startswith("#") and len(hex_c) == 7:
            self.btn_text_color.configure(fg_color=hex_c)
            self._sync_to_state_and_preview()

    def _on_hex_border_changed(self):
        hex_c = self.ent_border_color.get().strip()
        if hex_c.startswith("#") and len(hex_c) == 7:
            self.btn_border_color.configure(fg_color=hex_c)
            self._sync_to_state_and_preview()

    def _set_quick_pos(self, x_r: float, y_r: float):
        self.app_state["subtitle_style"]["sub_pos_x"] = x_r
        self.app_state["subtitle_style"]["sub_pos_y"] = y_r
        self.preview_canvas.set_subtitle_coords(x_r, y_r)
        self.on_state_updated()

    def _apply_preset(self):
        name = self.cbo_presets.get()
        if name in self.presets:
            p = self.presets[name]
            try:
                raw_pfs = float(p.get("font_size", 5.5))
            except Exception:
                raw_pfs = 5.5
            pfs = 5.5 if raw_pfs >= 18.0 else max(1.5, min(25.0, raw_pfs))
            self.slider_font_size.set(pfs)
            self.lbl_font_size_val.configure(text=f"{pfs:.1f}%")
            
            tc = p.get("text_color", "#FFE600")
            self.ent_text_color.delete(0, "end")
            self.ent_text_color.insert(0, tc)
            self.btn_text_color.configure(fg_color=tc)

            bc = p.get("border_color", "#000000")
            self.ent_border_color.delete(0, "end")
            self.ent_border_color.insert(0, bc)
            self.btn_border_color.configure(fg_color=bc)

            bw = p.get("border_width", 3)
            self.slider_border_width.set(bw)
            self.lbl_border_width_val.configure(text=f"{int(bw)}px")

            eff = p.get("effect", "None")
            self.cbo_effect.set(eff)

            x_r = p.get("sub_pos_x", 0.5)
            y_r = p.get("sub_pos_y", 0.85)
            self.preview_canvas.set_subtitle_coords(x_r, y_r)
            self.app_state["subtitle_style"]["sub_pos_x"] = x_r
            self.app_state["subtitle_style"]["sub_pos_y"] = y_r

            self._sync_to_state_and_preview()
            app_logger.info(f"Đã áp dụng Preset: '{name}'")

    def _save_new_preset(self):
        name = self.ent_new_preset_name.get().strip()
        if not name:
            messagebox.showwarning("Cảnh báo", "Vui lòng nhập tên cho Preset!")
            return

        style_data = {
            "font_family": self.cbo_font.get(),
            "font_size": round(float(self.slider_font_size.get()), 1),
            "text_color": self.ent_text_color.get().strip(),
            "border_color": self.ent_border_color.get().strip(),
            "border_width": int(self.slider_border_width.get()),
            "sub_pos_x": self.app_state["subtitle_style"].get("sub_pos_x", 0.5),
            "sub_pos_y": self.app_state["subtitle_style"].get("sub_pos_y", 0.85),
            "effect": self.cbo_effect.get(),
            "single_line": True
        }
        config_manager.save_preset(name, style_data)
        self.presets = config_manager.load_presets()
        self.cbo_presets.configure(values=list(self.presets.keys()))
        self.cbo_presets.set(name)
        self.ent_new_preset_name.delete(0, "end")
        app_logger.success(f"Đã lưu thành công Preset mới: '{name}'")

    def _delete_preset(self):
        name = self.cbo_presets.get()
        if config_manager.delete_preset(name):
            self.presets = config_manager.load_presets()
            self.cbo_presets.configure(values=list(self.presets.keys()))
            if self.presets:
                self.cbo_presets.set(list(self.presets.keys())[0])
            app_logger.info(f"Đã xóa Preset: '{name}'")

    def _open_subtitle_dialog(self):
        subs = self.app_state.get("manual_subtitles") or []
        if not subs:
            # Tạo 1 dòng mẫu nếu chưa có
            subs = [
                {"index": 1, "start_time": 0.5, "end_time": 3.0, "text": "你好，欢迎大家", "translation": "Xin chào, chào mừng các bạn!"}
            ]

        def on_saved(updated_subs):
            self.app_state["manual_subtitles"] = updated_subs
            app_logger.info(f"Đã lưu danh sách {len(updated_subs)} câu phụ đề thủ công.")
            self.on_state_updated()

        dialog = SubtitleEditorDialog(
            master=self.winfo_toplevel(),
            subtitles=subs,
            on_save_callback=on_saved
        )
