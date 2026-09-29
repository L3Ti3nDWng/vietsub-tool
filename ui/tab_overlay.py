import customtkinter as ctk
from tkinter import filedialog
from pathlib import Path
from typing import Dict, Any, Callable

from utils.logger import app_logger

class TabOverlay(ctk.CTkFrame):
    """
    Tab 4: Cài đặt Image Overlay (Chèn logo, hình ảnh thương hiệu, watermark)
    """
    def __init__(self, master, app_state: Dict[str, Any], preview_canvas, on_state_updated: Callable[[], None], **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app_state = app_state
        self.preview_canvas = preview_canvas
        self.on_state_updated = on_state_updated

        self._build_ui()
        self._load_from_state()

    def _build_ui(self):
        container = ctk.CTkScrollableFrame(self, fg_color="#18181b", corner_radius=8)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # 1. Bật / Tắt Overlay
        top_box = ctk.CTkFrame(container, fg_color="#202024")
        top_box.pack(fill="x", padx=15, pady=(15, 10))

        self.sw_enable = ctk.CTkSwitch(
            top_box,
            text="Bật tính năng chèn hình ảnh / Watermark / Logo",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._sync_and_update
        )
        self.sw_enable.pack(side="left", padx=15, pady=12)

        # 2. Chọn file hình ảnh
        file_box = ctk.CTkFrame(container, fg_color="#202024")
        file_box.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(file_box, text="File hình ảnh (Hỗ trợ PNG trong suốt, JPG):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=(12, 4))
        
        file_row = ctk.CTkFrame(file_box, fg_color="transparent")
        file_row.pack(fill="x", padx=15, pady=(0, 12))

        self.btn_browse = ctk.CTkButton(
            file_row,
            text="🖼 Chọn ảnh...",
            width=120,
            command=self._browse_image
        )
        self.btn_browse.pack(side="left", padx=(0, 10))

        self.lbl_image_path = ctk.CTkLabel(
            file_row,
            text="Chưa chọn file hình ảnh nào",
            text_color="#a1a1aa",
            anchor="w"
        )
        self.lbl_image_path.pack(side="left", fill="x", expand=True)

        # 3. Kích thước & Độ trong suốt (Scale & Opacity)
        sliders_box = ctk.CTkFrame(container, fg_color="#202024")
        sliders_box.pack(fill="x", padx=15, pady=5)

        # Scale
        scale_top = ctk.CTkFrame(sliders_box, fg_color="transparent")
        scale_top.pack(fill="x", padx=15, pady=(12, 0))
        ctk.CTkLabel(scale_top, text="Tỷ lệ thu phóng (Scale):", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.lbl_scale_val = ctk.CTkLabel(scale_top, text="100%", font=ctk.CTkFont(weight="bold"))
        self.lbl_scale_val.pack(side="right")

        self.slider_scale = ctk.CTkSlider(
            sliders_box,
            from_=0.1,
            to=2.0,
            number_of_steps=38,
            command=self._on_scale_changed
        )
        self.slider_scale.pack(fill="x", padx=15, pady=(4, 10))
        self.slider_scale.set(1.0)

        # Opacity
        op_top = ctk.CTkFrame(sliders_box, fg_color="transparent")
        op_top.pack(fill="x", padx=15, pady=(4, 0))
        ctk.CTkLabel(op_top, text="Độ mờ đục (Opacity):", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.lbl_op_val = ctk.CTkLabel(op_top, text="100%", font=ctk.CTkFont(weight="bold"))
        self.lbl_op_val.pack(side="right")

        self.slider_op = ctk.CTkSlider(
            sliders_box,
            from_=0.1,
            to=1.0,
            number_of_steps=18,
            command=self._on_op_changed
        )
        self.slider_op.pack(fill="x", padx=15, pady=(4, 12))
        self.slider_op.set(1.0)

        # 4. Tọa độ vị trí (X & Y) & Vị trí nhanh
        pos_box = ctk.CTkFrame(container, fg_color="#202024")
        pos_box.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(pos_box, text="Tọa độ vị trí trên video (Pixels):", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=15, pady=(12, 4))

        pos_row = ctk.CTkFrame(pos_box, fg_color="transparent")
        pos_row.pack(fill="x", padx=15, pady=4)

        ctk.CTkLabel(pos_row, text="X:", width=20).pack(side="left")
        self.ent_pos_x = ctk.CTkEntry(pos_row, width=80)
        self.ent_pos_x.insert(0, "30")
        self.ent_pos_x.pack(side="left", padx=(0, 20))
        self.ent_pos_x.bind("<Return>", lambda e: self._sync_and_update())

        ctk.CTkLabel(pos_row, text="Y:", width=20).pack(side="left")
        self.ent_pos_y = ctk.CTkEntry(pos_row, width=80)
        self.ent_pos_y.insert(0, "30")
        self.ent_pos_y.pack(side="left", padx=(0, 20))
        self.ent_pos_y.bind("<Return>", lambda e: self._sync_and_update())

        btn_apply_pos = ctk.CTkButton(pos_row, text="Áp dụng vị trí", width=110, command=self._sync_and_update)
        btn_apply_pos.pack(side="left")

        # Nút căn vị trí nhanh
        quick_row = ctk.CTkFrame(pos_box, fg_color="transparent")
        quick_row.pack(fill="x", padx=15, pady=(8, 12))

        ctk.CTkLabel(quick_row, text="Căn nhanh:").pack(side="left", padx=(0, 10))
        
        btn_tl = ctk.CTkButton(quick_row, text="Góc Trên Trái", width=100, command=lambda: self._set_quick_pos(30, 30))
        btn_tl.pack(side="left", padx=4)

        btn_tr = ctk.CTkButton(quick_row, text="Góc Trên Phải", width=100, command=lambda: self._set_quick_pos(1000, 30))
        btn_tr.pack(side="left", padx=4)

        btn_bl = ctk.CTkButton(quick_row, text="Góc Dưới Trái", width=100, command=lambda: self._set_quick_pos(30, 600))
        btn_bl.pack(side="left", padx=4)

        btn_br = ctk.CTkButton(quick_row, text="Góc Dưới Phải", width=100, command=lambda: self._set_quick_pos(1000, 600))
        btn_br.pack(side="left", padx=4)

    def _load_from_state(self):
        ov = self.app_state.get("overlay_info") or {}
        if ov.get("enabled"):
            self.sw_enable.select()
        else:
            self.sw_enable.deselect()

        if ov.get("path"):
            self.lbl_image_path.configure(text=Path(ov["path"]).name)

        sc = ov.get("scale", 1.0)
        self.slider_scale.set(sc)
        self.lbl_scale_val.configure(text=f"{int(sc*100)}%")

        op = ov.get("opacity", 1.0)
        self.slider_op.set(op)
        self.lbl_op_val.configure(text=f"{int(op*100)}%")

        self.ent_pos_x.delete(0, "end")
        self.ent_pos_x.insert(0, str(int(ov.get("x", 30))))
        self.ent_pos_y.delete(0, "end")
        self.ent_pos_y.insert(0, str(int(ov.get("y", 30))))

    def _browse_image(self):
        f = filedialog.askopenfilename(
            title="Chọn ảnh Logo / Watermark",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.webp *.bmp"), ("All Files", "*.*")]
        )
        if f:
            self.app_state["overlay_info"]["path"] = f
            self.lbl_image_path.configure(text=Path(f).name)
            self.sw_enable.select()
            self._sync_and_update()
            app_logger.info(f"Đã chọn ảnh overlay: {Path(f).name}")

    def _on_scale_changed(self, val):
        self.lbl_scale_val.configure(text=f"{int(val*100)}%")
        self._sync_and_update()

    def _on_op_changed(self, val):
        self.lbl_op_val.configure(text=f"{int(val*100)}%")
        self._sync_and_update()

    def _set_quick_pos(self, x: int, y: int):
        v_info = self.app_state.get("video_info") or {}
        vw = v_info.get("width", 1280)
        vh = v_info.get("height", 720)

        # Tính toán góc phù hợp với độ phân giải video
        actual_x = x
        actual_y = y
        if x > 500:
            actual_x = max(50, vw - 220)
        if y > 400:
            actual_y = max(50, vh - 150)

        self.ent_pos_x.delete(0, "end")
        self.ent_pos_x.insert(0, str(actual_x))
        self.ent_pos_y.delete(0, "end")
        self.ent_pos_y.insert(0, str(actual_y))
        self._sync_and_update()

    def _sync_and_update(self):
        try:
            px = int(self.ent_pos_x.get())
        except ValueError:
            px = 30
        try:
            py = int(self.ent_pos_y.get())
        except ValueError:
            py = 30

        ov = self.app_state["overlay_info"]
        ov["enabled"] = bool(self.sw_enable.get())
        ov["scale"] = float(self.slider_scale.get())
        ov["opacity"] = float(self.slider_op.get())
        ov["x"] = px
        ov["y"] = py

        self.preview_canvas.set_overlay_info(ov)
        self.on_state_updated()
