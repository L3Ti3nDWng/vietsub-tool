import customtkinter as ctk
import tkinter as tk
from typing import Dict, Any, Callable, Optional, List

from ui.video_preview import VideoPreviewCanvas

class PanelCenter(ctk.CTkFrame):
    """
    Khu vực trung tâm (CapCut Style):
    - Thanh công cụ thao tác chuột ở trên:
      * Kéo phụ đề, vẽ Blur, vẽ Blackbox, vẽ Crop.
      * AUTOGRID: Bật / Tắt lưới chia khung hình 3x3 và tâm điểm (+).
      * SMART SNAP: Bật / Tắt chế độ hút nam châm tự động vào các trục giữa và lề an toàn.
      * Chuyển đổi xem Crop / Gốc & Hủy Crop.
    - Khung Video Preview Canvas ở giữa (CROP PREVIEW REAL-TIME).
    - Thanh điều khiển Player ở dưới (Play/Pause, Hotkey Space, Seek 1s, Slider thời gian, Timecode).
    """
    def __init__(
        self,
        master,
        app_state: Dict[str, Any],
        on_sub_pos_changed: Optional[Callable[[float, float], None]] = None,
        on_boxes_changed: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
        on_crop_changed: Optional[Callable[[Optional[Dict[str, Any]]], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color="#121214", corner_radius=8, **kwargs)
        self.app_state = app_state
        self.on_sub_pos_changed = on_sub_pos_changed
        self.on_boxes_changed = on_boxes_changed
        self.on_crop_changed = on_crop_changed

        self._build_ui()

    def _build_ui(self):
        # 1. Top Toolbar thao tác chuột, Autogrid, Snap & Chế độ xem
        toolbar = ctk.CTkFrame(self, fg_color="#18181b", height=42, corner_radius=6)
        toolbar.pack(fill="x", padx=6, pady=(6, 4))

        ctk.CTkLabel(toolbar, text="Công cụ:", font=ctk.CTkFont(size=11, weight="bold"), text_color="#38bdf8").pack(side="left", padx=(10, 4))

        self.seg_tool = ctk.CTkSegmentedButton(
            toolbar,
            values=["✥ Kéo phụ đề", "🟦 Vẽ Blur", "⬛ Vẽ Blackbox", "✂ Vẽ Crop"],
            command=self._on_tool_changed,
            selected_color="#0284c7"
        )
        self.seg_tool.pack(side="left", padx=4, pady=5)
        self.seg_tool.set("✥ Kéo phụ đề")

        # NÚT BẬT / TẮT AUTOGRID (LƯỚI 3X3 & TÂM CHỮ THẬP)
        self.btn_grid = ctk.CTkButton(
            toolbar,
            text="📐 Lưới (Grid)",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#27272a",
            hover_color="#3f3f46",
            width=90,
            height=28,
            command=self._toggle_grid
        )
        self.btn_grid.pack(side="left", padx=4, pady=5)

        # NÚT BẬT / TẮT HÚT NAM CHÂM TRỤC (SMART MAGNETIC SNAP)
        self.btn_snap = ctk.CTkButton(
            toolbar,
            text="🧲 Hút trục: Bật",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            width=100,
            height=28,
            command=self._toggle_snap
        )
        self.btn_snap.pack(side="left", padx=4, pady=5)

        # CHỌN TỈ LỆ KHÓA KHI CROP (16:9, 9:16, 1:1, TỰ DO)
        self.lbl_crop_ratio = ctk.CTkLabel(toolbar, text="Khóa Crop:", font=ctk.CTkFont(size=11), text_color="#a1a1aa")
        self.lbl_crop_ratio.pack(side="left", padx=(10, 2), pady=5)

        self.cbo_crop_ratio = ctk.CTkComboBox(
            toolbar,
            values=["Tự do", "16:9 Chuẩn", "9:16 Dọc", "1:1 Vuông"],
            width=105,
            height=28,
            command=self._on_crop_ratio_changed
        )
        self.cbo_crop_ratio.pack(side="left", padx=2, pady=5)
        self.cbo_crop_ratio.set("Tự do")

        # Nút chuyển đổi xem: Đã Crop / Video Gốc
        self.btn_toggle_view = ctk.CTkButton(
            toolbar,
            text="👁 Xem: Đã Crop",
            font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#059669",
            hover_color="#047857",
            width=105,
            height=28,
            command=self._toggle_crop_view
        )
        self.btn_toggle_view.pack(side="right", padx=(4, 10), pady=5)

        self.btn_reset_crop = ctk.CTkButton(
            toolbar,
            text="🔄 Hủy Crop",
            font=ctk.CTkFont(size=11),
            fg_color="#374151",
            hover_color="#4b5563",
            width=75,
            height=28,
            command=self._reset_crop
        )
        self.btn_reset_crop.pack(side="right", padx=4, pady=5)

        # 2. Canvas Preview ở giữa
        self.preview_container = ctk.CTkFrame(self, fg_color="#09090b", corner_radius=6)
        self.preview_container.pack(fill="both", expand=True, padx=6, pady=2)

        self.preview = VideoPreviewCanvas(
            self.preview_container,
            width=680,
            height=440,
            on_sub_pos_changed=self.on_sub_pos_changed,
            on_boxes_changed=self.on_boxes_changed,
            on_crop_changed=self._internal_crop_changed
        )
        self.preview.pack(fill="both", expand=True, padx=4, pady=4)

        # 3. Thanh Player điều khiển phát video ở dưới
        playback = ctk.CTkFrame(self, fg_color="#18181b", height=42, corner_radius=6)
        playback.pack(fill="x", padx=6, pady=(4, 6))

        self.btn_play = ctk.CTkButton(playback, text="▶ Phát (Space)", width=95, height=28, command=self._toggle_play)
        self.btn_play.pack(side="left", padx=(10, 4), pady=5)

        btn_b1 = ctk.CTkButton(playback, text="◀ -1s", width=55, height=28, command=lambda: self._seek_offset(-1.0))
        btn_b1.pack(side="left", padx=2, pady=5)

        btn_f1 = ctk.CTkButton(playback, text="+1s ▶", width=55, height=28, command=lambda: self._seek_offset(1.0))
        btn_f1.pack(side="left", padx=2, pady=5)

        self.slider_time = ctk.CTkSlider(playback, from_=0.0, to=100.0, command=self._on_slider_moved)
        self.slider_time.pack(side="left", fill="x", expand=True, padx=10, pady=5)
        self.slider_time.set(0)

        self.lbl_time = ctk.CTkLabel(playback, text="00:00 / 00:00", font=ctk.CTkFont(size=11), width=90)
        self.lbl_time.pack(side="left", padx=(0, 10), pady=5)

        self._schedule_time_update()

    def _toggle_grid(self):
        is_on = self.preview.toggle_grid()
        if is_on:
            self.btn_grid.configure(text="📐 Lưới: Bật", fg_color="#0284c7", hover_color="#0369a1")
        else:
            self.btn_grid.configure(text="📐 Lưới: Tắt", fg_color="#27272a", hover_color="#3f3f46")

    def _toggle_snap(self):
        is_on = self.preview.toggle_snapping()
        if is_on:
            self.btn_snap.configure(text="🧲 Hút trục: Bật", fg_color="#059669", hover_color="#047857")
        else:
            self.btn_snap.configure(text="🧲 Hút trục: Tắt", fg_color="#374151", hover_color="#4b5563")

    def _on_crop_ratio_changed(self, choice: str):
        ratio_map = {
            "Tự do": "free",
            "16:9 Chuẩn": "16:9",
            "9:16 Dọc": "9:16",
            "1:1 Vuông": "1:1"
        }
        r = ratio_map.get(choice, "free")
        self.preview.set_crop_aspect_ratio(r)

    def _on_tool_changed(self, value):
        if "Kéo phụ đề" in value:
            self.preview.interaction_mode = "sub"
        elif "Blur" in value:
            self.preview.interaction_mode = "blur"
        elif "Blackbox" in value:
            self.preview.interaction_mode = "black"
        elif "Crop" in value:
            self.preview.interaction_mode = "crop"
            self.preview.crop_view_mode = "full"
            self.btn_toggle_view.configure(text="👁 Xem: Gốc", fg_color="#0284c7")
            if not self.preview.is_playing:
                self.preview.seek_frame(self.preview.current_frame_idx)

    def _internal_crop_changed(self, crop):
        self.btn_toggle_view.configure(text="👁 Xem: Đã Crop", fg_color="#059669")
        self.seg_tool.set("✥ Kéo phụ đề")
        if self.on_crop_changed:
            self.on_crop_changed(crop)

    def _toggle_crop_view(self):
        new_mode = self.preview.toggle_crop_view()
        if new_mode == "cropped":
            self.btn_toggle_view.configure(text="👁 Xem: Đã Crop", fg_color="#059669")
        else:
            self.btn_toggle_view.configure(text="👁 Xem: Gốc", fg_color="#0284c7")

    def _reset_crop(self):
        self.preview.reset_crop()
        self.btn_toggle_view.configure(text="👁 Xem: Gốc", fg_color="#0284c7")
        if self.on_crop_changed:
            self.on_crop_changed(None)

    def _toggle_play(self):
        is_playing = self.preview.toggle_play()
        if is_playing:
            self.btn_play.configure(text="⏸ Dừng (Space)")
        else:
            self.btn_play.configure(text="▶ Phát (Space)")

    def _seek_offset(self, offset_sec: float):
        curr = self.preview.get_current_time()
        new_t = max(0.0, curr + offset_sec)
        self.preview.seek_seconds(new_t)
        self.slider_time.set(new_t)

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

    def set_duration(self, duration_sec: float):
        self.slider_time.configure(to=max(1.0, duration_sec))
        self.slider_time.set(0)
        tot_str = f"{int(duration_sec//60):02d}:{int(duration_sec%60):02d}"
        self.lbl_time.configure(text=f"00:00 / {tot_str}")
