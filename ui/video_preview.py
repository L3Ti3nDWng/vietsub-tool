import time
import cv2
import tkinter as tk
import numpy as np
from PIL import Image, ImageTk
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable

class VideoPreviewCanvas(tk.Frame):
    """
    Component xem trước video CapCut-Style với CHUẨN CỐ ĐỊNH 16:9 (1920x1080):
    - CỐ ĐỊNH TỈ LỆ 16:9: Khung xem trước luôn duy trì tỉ lệ chuẩn 16:9.
    - KHÔNG BỊ GIÃN (NO STRETCH): Bất kể video gốc là 9:16 (Douyin/TikTok), 4:3 hay crop tự do,
      hình ảnh luôn được giữ nguyên tỉ lệ gốc và đệm viền đen (Letterbox/Pillarbox) cân đối.
    - AUTOGRID (Rule of Thirds 3x3): Lưới chia bố cục 3x3 và tâm chữ thập (+) trên khung 16:9.
    - HÚT TRỤC TỰ ĐỘNG (Smart Magnetic Snapping): Hút phụ đề vào trục dọc giữa (50%),
      trục ngang tâm (50%), và vạch chuẩn an toàn TikTok (85%, 80%, 15%).
    - ĐỒNG NHẤT 100% VỚI VIDEO XUẤT (WYSIWYG): Vị trí phụ đề, watermark và crop trên preview
      khớp chính xác từng pixel với video MP4 1920x1080 xuất ra.
    - Tối ưu 60+ FPS và kéo thả phụ đề 0ms latency.
    """
    def __init__(
        self,
        master,
        width: int = 680,
        height: int = 440,
        on_sub_pos_changed: Optional[Callable[[float, float], None]] = None,
        on_boxes_changed: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
        on_crop_changed: Optional[Callable[[Optional[Dict[str, Any]]], None]] = None,
        **kwargs
    ):
        super().__init__(master, bg="#09090b", **kwargs)
        self.canvas_width = width
        self.canvas_height = height
        self.on_sub_pos_changed = on_sub_pos_changed
        self.on_boxes_changed = on_boxes_changed
        self.on_crop_changed = on_crop_changed

        self.canvas = tk.Canvas(
            self,
            width=self.canvas_width,
            height=self.canvas_height,
            bg="#09090b",
            highlightthickness=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Video playback state
        self.cap: Optional[cv2.VideoCapture] = None
        self.video_path: Optional[str] = None
        self.video_width = 1280
        self.video_height = 720
        self.fps = 30.0
        self.total_frames = 0
        self.current_frame_idx = 0
        self.is_playing = False
        self._last_frame_bgr = None
        self._current_photo = None

        # 16:9 Fixed Viewport Geometry
        self.screen_x = 0
        self.screen_y = 0
        self.screen_w = width
        self.screen_h = int(width * 9.0 / 16.0)

        # Video placement inside 16:9 Viewport (Letterbox / Pillarbox)
        self.fit_x = 0
        self.fit_y = 0
        self.fit_w = self.screen_w
        self.fit_h = self.screen_h
        self.fit_scale = 1.0

        # Persistent Canvas Item IDs
        self.bg_img_id = None
        self.screen_frame_id = None
        self.screen_badge_id = None
        self.sub_text_id = None
        self.sub_shadow_ids = []
        self.sub_box_id = None
        self.sub_hint_id = None
        self.crop_guide_id = None
        self.crop_label_id = None
        self.mode_tag_bg = None
        self.mode_tag_txt = None
        self.mask_item_ids = []

        # Smart Snapping & Autogrid Items
        self.enable_snapping = True
        self.show_grid = False
        self.grid_lines_ids = []
        self.snap_line_x_id = None
        self.snap_badge_x_bg = None
        self.snap_badge_x_txt = None
        self.snap_line_y_id = None
        self.snap_badge_y_bg = None
        self.snap_badge_y_txt = None
        self._snap_y_color = "#10b981"

        # Interactive Mode & Crop Aspect Ratio
        self.interaction_mode = "sub"       # "sub", "blur", "black", "crop"
        self.crop_view_mode = "cropped"     # "cropped" or "full"
        self.crop_aspect_ratio = "free"     # "free", "16:9", "9:16", "1:1"

        # Subtitle properties
        self.sub_x_ratio = 0.5
        self.sub_y_ratio = 0.85
        self.sub_text = "Phụ đề tiếng Việt xem trước"
        self.sub_font_family = "Arial"
        self.sub_font_size = 5.5   # % chiều cao màn hình
        self.sub_text_color = "#FFE600"
        self.sub_border_color = "#000000"
        self.sub_border_width = 3

        # Mask boxes & Crop box
        self.mask_boxes: List[Dict[str, Any]] = []
        self.crop_box: Optional[Dict[str, Any]] = None
        self.overlay_info: Optional[Dict[str, Any]] = None

        # Mouse tracking
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.current_drawing_box = None
        self.is_dragging_sub = False

        # Bind events
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_move)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Configure>", self._on_resize)

        self._calc_screen_geometry()
        self._draw_placeholder()

    # ==========================
    # HÌNH HỌC KHUNG 16:9 (VIEWPORT)
    # ==========================
    def _calc_screen_geometry(self):
        """Tính toán khung chữ nhật chuẩn 16:9 lớn nhất có thể nằm trọn trong canvas."""
        target_ratio = 16.0 / 9.0
        c_w = max(50, self.canvas_width)
        c_h = max(50, self.canvas_height)
        canvas_ratio = float(c_w) / float(c_h)

        if canvas_ratio > target_ratio:
            # Chiều cao là giới hạn
            self.screen_h = max(90, c_h - 12)
            self.screen_w = int(self.screen_h * target_ratio)
        else:
            # Chiều rộng là giới hạn
            self.screen_w = max(160, c_w - 12)
            self.screen_h = int(self.screen_w / target_ratio)

        self.screen_x = (c_w - self.screen_w) // 2
        self.screen_y = (c_h - self.screen_h) // 2

    def set_crop_aspect_ratio(self, ratio_str: str):
        """Thiết lập tỉ lệ khóa khi kéo vẽ Crop: 'free', '16:9', '9:16', '1:1'."""
        self.crop_aspect_ratio = ratio_str

    # ==========================
    # QUẢN LÝ LƯỚI & HÚT NAM CHÂM TRÊN KHUNG 16:9
    # ==========================
    def toggle_grid(self) -> bool:
        """Bật / Tắt hiển thị lưới căn chỉnh Rule of Thirds (3x3)."""
        self.show_grid = not self.show_grid
        self._update_grid_overlay()
        return self.show_grid

    def toggle_snapping(self) -> bool:
        """Bật / Tắt chế độ hút nam châm vào các trục thông minh."""
        self.enable_snapping = not self.enable_snapping
        return self.enable_snapping

    def _update_grid_overlay(self):
        """Vẽ hoặc ẩn lưới 3x3 và tâm điểm chữ thập trên khung hình 16:9."""
        for gid in self.grid_lines_ids:
            self.canvas.delete(gid)
        self.grid_lines_ids.clear()

        if not self.show_grid or self.screen_w <= 10 or self.screen_h <= 10:
            return

        sx = self.screen_x
        sy = self.screen_y
        sw = self.screen_w
        sh = self.screen_h

        grid_color = "#3f3f46"

        # 1. Đường dọc 1/3 và 2/3
        x_33 = sx + sw // 3
        x_66 = sx + (sw * 2) // 3
        g1 = self.canvas.create_line(x_33, sy, x_33, sy + sh, fill=grid_color, dash=(4, 4), width=1)
        g2 = self.canvas.create_line(x_66, sy, x_66, sy + sh, fill=grid_color, dash=(4, 4), width=1)

        # 2. Đường ngang 1/3 và 2/3
        y_33 = sy + sh // 3
        y_66 = sy + (sh * 2) // 3
        g3 = self.canvas.create_line(sx, y_33, sx + sw, y_33, fill=grid_color, dash=(4, 4), width=1)
        g4 = self.canvas.create_line(sx, y_66, sx + sw, y_66, fill=grid_color, dash=(4, 4), width=1)

        # 3. Chữ thập trung tâm (+) tại chính giữa (50%, 50%)
        cx = sx + sw // 2
        cy = sy + sh // 2
        g5 = self.canvas.create_line(cx - 14, cy, cx + 14, cy, fill="#f59e0b", width=1)
        g6 = self.canvas.create_line(cx, cy - 14, cx, cy + 14, fill="#f59e0b", width=1)

        # 4. Vùng an toàn phụ đề TikTok (85%)
        safe_y = sy + int(sh * 0.85)
        g7 = self.canvas.create_line(sx, safe_y, sx + sw, safe_y, fill="#10b981", dash=(2, 4), width=1)

        self.grid_lines_ids.extend([g1, g2, g3, g4, g5, g6, g7])

    def _clear_snap_guides(self):
        """Xóa toàn bộ đường gióng nam châm khi thả chuột."""
        for item in (self.snap_line_x_id, self.snap_badge_x_bg, self.snap_badge_x_txt,
                     self.snap_line_y_id, self.snap_badge_y_bg, self.snap_badge_y_txt):
            if item is not None:
                self.canvas.delete(item)
        self.snap_line_x_id = None
        self.snap_badge_x_bg = None
        self.snap_badge_x_txt = None
        self.snap_line_y_id = None
        self.snap_badge_y_bg = None
        self.snap_badge_y_txt = None

    def _update_snap_guides(self, snap_px, label_x, snap_py, label_y):
        """Vẽ đường gióng nam châm trục X và Y kèm huy hiệu thông báo khi đang hút."""
        sx = self.screen_x
        sy = self.screen_y
        sw = self.screen_w
        sh = self.screen_h

        # Đường gióng dọc X
        if snap_px is not None:
            if self.snap_line_x_id is None:
                self.snap_line_x_id = self.canvas.create_line(snap_px, sy, snap_px, sy + sh, fill="#fbbf24", dash=(3, 3), width=2)
                self.snap_badge_x_bg = self.canvas.create_rectangle(snap_px - 65, sy + 8, snap_px + 65, sy + 26, fill="#18181b", outline="#fbbf24", width=1)
                self.snap_badge_x_txt = self.canvas.create_text(snap_px, sy + 17, text=label_x, fill="#fbbf24", font=("Segoe UI", 8, "bold"))
            else:
                self.canvas.coords(self.snap_line_x_id, snap_px, sy, snap_px, sy + sh)
                self.canvas.coords(self.snap_badge_x_bg, snap_px - 65, sy + 8, snap_px + 65, sy + 26)
                self.canvas.coords(self.snap_badge_x_txt, snap_px, sy + 17)
                self.canvas.itemconfig(self.snap_badge_x_txt, text=label_x)
        else:
            if self.snap_line_x_id is not None:
                self.canvas.delete(self.snap_line_x_id)
                self.canvas.delete(self.snap_badge_x_bg)
                self.canvas.delete(self.snap_badge_x_txt)
                self.snap_line_x_id = None
                self.snap_badge_x_bg = None
                self.snap_badge_x_txt = None

        # Đường gióng ngang Y
        if snap_py is not None:
            col = getattr(self, "_snap_y_color", "#10b981")
            if self.snap_line_y_id is None:
                self.snap_line_y_id = self.canvas.create_line(sx, snap_py, sx + sw, snap_py, fill=col, dash=(3, 3), width=2)
                self.snap_badge_y_bg = self.canvas.create_rectangle(sx + sw - 170, snap_py - 18, sx + sw - 10, snap_py - 2, fill="#18181b", outline=col, width=1)
                self.snap_badge_y_txt = self.canvas.create_text(sx + sw - 90, snap_py - 10, text=label_y, fill=col, font=("Segoe UI", 8, "bold"))
            else:
                self.canvas.coords(self.snap_line_y_id, sx, snap_py, sx + sw, snap_py)
                self.canvas.itemconfig(self.snap_line_y_id, fill=col)
                self.canvas.coords(self.snap_badge_y_bg, sx + sw - 170, snap_py - 18, sx + sw - 10, snap_py - 2)
                self.canvas.itemconfig(self.snap_badge_y_bg, outline=col)
                self.canvas.coords(self.snap_badge_y_txt, sx + sw - 90, snap_py - 10)
                self.canvas.itemconfig(self.snap_badge_y_txt, text=label_y, fill=col)
        else:
            if self.snap_line_y_id is not None:
                self.canvas.delete(self.snap_line_y_id)
                self.canvas.delete(self.snap_badge_y_bg)
                self.canvas.delete(self.snap_badge_y_txt)
                self.snap_line_y_id = None
                self.snap_badge_y_bg = None
                self.snap_badge_y_txt = None

    # ==========================
    # VIDEO PLAYBACK & RENDER
    # ==========================
    def load_video(self, path: str):
        if self.cap:
            self.cap.release()

        self.video_path = path
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            return

        self.video_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
        self.video_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.current_frame_idx = 0

        self.canvas.delete("all")
        self.bg_img_id = None
        self.screen_frame_id = None
        self.screen_badge_id = None
        self.sub_text_id = None
        self.sub_shadow_ids.clear()
        self.sub_box_id = None
        self.sub_hint_id = None
        self.crop_guide_id = None
        self.crop_label_id = None
        self.mode_tag_bg = None
        self.mode_tag_txt = None
        self.mask_item_ids.clear()
        self.grid_lines_ids.clear()
        self._clear_snap_guides()

        self._calc_screen_geometry()
        self.seek_frame(0)

    def seek_frame(self, frame_idx: int):
        if not self.cap:
            return
        self.current_frame_idx = max(0, min(frame_idx, self.total_frames - 1))
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, self.current_frame_idx)
        ret, frame = self.cap.read()
        if ret:
            self._last_frame_bgr = frame
            self._render_frame(frame)

    def seek_seconds(self, sec: float):
        frame_idx = int(sec * self.fps)
        self.seek_frame(frame_idx)

    def get_current_time(self) -> float:
        if self.fps <= 0:
            return 0.0
        return float(self.current_frame_idx) / float(self.fps)

    def play(self):
        if not self.cap:
            return
        self.is_playing = True
        self._play_loop()

    def pause(self):
        self.is_playing = False

    def toggle_play(self):
        if self.is_playing:
            self.pause()
        else:
            self.play()
        return self.is_playing

    def _play_loop(self):
        if not self.is_playing or not self.cap:
            return

        t_start = time.perf_counter()
        ret, frame = self.cap.read()
        if not ret:
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            self.current_frame_idx = 0
            ret, frame = self.cap.read()

        if ret:
            self.current_frame_idx += 1
            self._last_frame_bgr = frame
            self._render_frame(frame)

            t_render = time.perf_counter() - t_start
            target_delay = 1.0 / max(10.0, self.fps)
            rem_ms = max(1, int((target_delay - t_render) * 1000))
            self.after(rem_ms, self._play_loop)
        else:
            self.is_playing = False

    def _on_resize(self, event):
        if event.width > 50 and event.height > 50:
            self.canvas_width = event.width
            self.canvas_height = event.height
            self._calc_screen_geometry()
            if self._last_frame_bgr is not None and not self.is_playing:
                self._render_frame(self._last_frame_bgr)
            elif not self.cap:
                self._draw_placeholder()

    def _draw_placeholder(self):
        """Vẽ khung hình nền 16:9 khi chưa nạp video."""
        self.canvas.delete("all")
        self.bg_img_id = None
        self.screen_frame_id = None
        self.screen_badge_id = None

        self._calc_screen_geometry()
        sx = self.screen_x
        sy = self.screen_y
        sw = self.screen_w
        sh = self.screen_h

        # Khung viền 16:9
        self.canvas.create_rectangle(sx, sy, sx + sw, sy + sh, fill="#0d0d10", outline="#27272a", width=2)
        self.canvas.create_text(
            sx + sw - 65, sy + 14,
            text="16:9 (1920x1080)",
            fill="#38bdf8",
            font=("Segoe UI", 8, "bold")
        )

        self.canvas.create_text(
            sx + sw // 2,
            sy + sh // 2,
            text="🎬 KHUNG XEM TRƯỚC CHUẨN 16:9 (CAPCUT STUDIO)\n\n"
                 "Nhấn 'Chọn Video Local' ở cột bên trái để tải video\n"
                 "• Tỉ lệ cố định 16:9 (1920x1080) cho Preview & Xuất video\n"
                 "• Mọi video / crop đều được giữ nguyên tỉ lệ (Không bị giãn méo)\n"
                 "• [Space]: Phát / Dừng  |  [🧲 Snap]: Hút trục căn chỉnh",
            fill="#71717a",
            font=("Segoe UI", 11, "bold"),
            justify=tk.CENTER
        )

    def _render_frame(self, frame_bgr):
        """
        Render frame video vào khung chuẩn 16:9:
        - Xử lý mask boxes (blur / blackbox) trên kích thước video gốc.
        - Xử lý crop (nếu có bật): Cắt vùng crop từ frame gốc.
        - Khung chuẩn 16:9 (screen_w x screen_h) được tạo với nền đen (0, 0, 0).
        - Video / Crop được scale vừa vặn không biến dạng (giữ nguyên tỉ lệ, không stretch).
        - Subtitle, Autogrid và Guides được căn chỉnh chính xác trên khung 16:9.
        """
        h, w = frame_bgr.shape[:2]
        frame_proc = frame_bgr.copy()

        # 1. Che vùng phụ đề gốc theo tọa độ video gốc
        for box in self.mask_boxes:
            bx = max(0, min(w, int(box["x"])))
            by = max(0, min(h, int(box["y"])))
            bw = max(0, min(w - bx, int(box["w"])))
            bh = max(0, min(h - by, int(box["h"])))
            if bw > 0 and bh > 0:
                if box.get("type") == "black":
                    cv2.rectangle(frame_proc, (bx, by), (bx + bw, by + bh), (0, 0, 0), -1)
                elif box.get("type") == "blur":
                    roi = frame_proc[by:by+bh, bx:bx+bw]
                    blurred_roi = cv2.GaussianBlur(roi, (25, 25), 12)
                    frame_proc[by:by+bh, bx:bx+bw] = blurred_roi

        # 2. Xử lý Crop View
        has_crop = bool(
            self.crop_box and self.crop_box.get("enabled") and
            self.crop_box.get("w", 0) > 10 and self.crop_box.get("h", 0) > 10
        )
        is_cropped_view = (has_crop and self.crop_view_mode == "cropped" and self.interaction_mode != "crop")

        if is_cropped_view:
            cx = max(0, min(w - 10, int(self.crop_box["x"])))
            cy = max(0, min(h - 10, int(self.crop_box["y"])))
            cw = max(10, min(w - cx, int(self.crop_box["w"])))
            ch = max(10, min(h - cy, int(self.crop_box["h"])))
            content_img = frame_proc[cy:cy+ch, cx:cx+cw]
            src_w, src_h = cw, ch
        else:
            content_img = frame_proc
            src_w, src_h = w, h

        # 3. Tính toán khung 16:9
        self._calc_screen_geometry()
        sw = self.screen_w
        sh = self.screen_h

        # 4. SCALE VỪA VẶN VÀO KHUNG 16:9 KHÔNG BIẾN DẠNG (NO STRETCH)
        fit_scale = min(float(sw) / src_w, float(sh) / src_h)
        fit_w = max(1, int(src_w * fit_scale))
        fit_h = max(1, int(src_h * fit_scale))

        fit_x = (sw - fit_w) // 2
        fit_y = (sh - fit_h) // 2

        self.fit_scale = fit_scale
        self.fit_w = fit_w
        self.fit_h = fit_h
        self.fit_x = fit_x
        self.fit_y = fit_y

        # Tạo buffer đen 16:9 và dán video vào giữa (Letterbox / Pillarbox giữ nguyên, không stretch)
        screen_buffer = np.zeros((sh, sw, 3), dtype=np.uint8)
        resized_content = cv2.resize(content_img, (fit_w, fit_h), interpolation=cv2.INTER_LINEAR)
        screen_buffer[fit_y:fit_y+fit_h, fit_x:fit_x+fit_w] = resized_content

        # Chuyển sang ảnh RGB Pillow
        rgb_img = cv2.cvtColor(screen_buffer, cv2.COLOR_BGR2RGB)
        pil_img = Image.fromarray(rgb_img)

        # 5. Chèn Watermark / Logo trên khung 16:9 (chuẩn hóa theo 1920x1080)
        if self.overlay_info and self.overlay_info.get("enabled") and self.overlay_info.get("path"):
            try:
                ov_path = self.overlay_info["path"]
                if Path(ov_path).exists():
                    ov_pil = Image.open(ov_path).convert("RGBA")
                    scale_to_16_9 = float(sw) / 1920.0
                    user_scale = float(self.overlay_info.get("scale", 1.0))
                    nw = int(ov_pil.width * user_scale * scale_to_16_9)
                    nh = int(ov_pil.height * user_scale * scale_to_16_9)
                    if nw > 0 and nh > 0:
                        ov_pil = ov_pil.resize((nw, nh), Image.Resampling.BILINEAR)
                        alpha = float(self.overlay_info.get("opacity", 1.0))
                        if alpha < 1.0:
                            r, g, b, a = ov_pil.split()
                            a = a.point(lambda p: int(p * alpha))
                            ov_pil = Image.merge("RGBA", (r, g, b, a))
                        ov_x = int(self.overlay_info.get("x", 20) * scale_to_16_9)
                        ov_y = int(self.overlay_info.get("y", 20) * scale_to_16_9)
                        pil_img.paste(ov_pil, (ov_x, ov_y), ov_pil)
            except Exception:
                pass

        # 6. Persistent Layer 0 (Ảnh nền 16:9)
        self._current_photo = ImageTk.PhotoImage(pil_img)
        if self.bg_img_id is None:
            self.bg_img_id = self.canvas.create_image(self.screen_x, self.screen_y, anchor=tk.NW, image=self._current_photo)
        else:
            self.canvas.coords(self.bg_img_id, self.screen_x, self.screen_y)
            self.canvas.itemconfig(self.bg_img_id, image=self._current_photo)
            self.canvas.tag_lower(self.bg_img_id)

        # 7. Viền khung màn hình 16:9 & Huy hiệu độ phân giải
        if self.screen_frame_id is None:
            self.screen_frame_id = self.canvas.create_rectangle(
                self.screen_x, self.screen_y, self.screen_x + sw, self.screen_y + sh,
                outline="#3f3f46", width=2
            )
        else:
            self.canvas.coords(self.screen_frame_id, self.screen_x, self.screen_y, self.screen_x + sw, self.screen_y + sh)

        badge_txt = "16:9 (1920x1080)"
        if self.screen_badge_id is None:
            self.screen_badge_id = self.canvas.create_text(
                self.screen_x + sw - 65, self.screen_y + 14,
                text=badge_txt, fill="#38bdf8", font=("Segoe UI", 8, "bold")
            )
        else:
            self.canvas.coords(self.screen_badge_id, self.screen_x + sw - 65, self.screen_y + 14)
            self.canvas.itemconfig(self.screen_badge_id, text=badge_txt)

        # 8. Thẻ thông báo chế độ Crop
        tag_str = "✂ ĐÃ CROP (16:9)" if is_cropped_view else "📺 TOÀN CẢNH GỐC"
        tag_color = "#10b981" if is_cropped_view else "#38bdf8"
        if self.mode_tag_bg is None:
            self.mode_tag_bg = self.canvas.create_rectangle(
                self.screen_x + 8, self.screen_y + 8, self.screen_x + 135, self.screen_y + 28,
                fill="#18181b", outline=tag_color, width=1
            )
            self.mode_tag_txt = self.canvas.create_text(
                self.screen_x + 14, self.screen_y + 18,
                text=f"PREVIEW: {tag_str}", fill=tag_color, font=("Segoe UI", 8, "bold"), anchor=tk.W
            )
        else:
            self.canvas.coords(self.mode_tag_bg, self.screen_x + 8, self.screen_y + 8, self.screen_x + 135, self.screen_y + 28)
            self.canvas.itemconfig(self.mode_tag_bg, outline=tag_color)
            self.canvas.coords(self.mode_tag_txt, self.screen_x + 14, self.screen_y + 18)
            self.canvas.itemconfig(self.mode_tag_txt, text=f"PREVIEW: {tag_str}", fill=tag_color)

        # 9. Viền Crop Guide khi ở chế độ Full View
        if not is_cropped_view and has_crop:
            cx_canvas = self.screen_x + self.fit_x + int(self.crop_box["x"] * self.fit_scale)
            cy_canvas = self.screen_y + self.fit_y + int(self.crop_box["y"] * self.fit_scale)
            cw_canvas = int(self.crop_box["w"] * self.fit_scale)
            ch_canvas = int(self.crop_box["h"] * self.fit_scale)
            if self.crop_guide_id is None:
                self.crop_guide_id = self.canvas.create_rectangle(
                    cx_canvas, cy_canvas, cx_canvas + cw_canvas, cy_canvas + ch_canvas,
                    outline="#10b981", width=2, dash=(4, 4)
                )
                self.crop_label_id = self.canvas.create_text(
                    cx_canvas + 6, cy_canvas + 12,
                    text="✂ VÙNG CROP", fill="#10b981", font=("Segoe UI", 8, "bold"), anchor=tk.W
                )
            else:
                self.canvas.coords(self.crop_guide_id, cx_canvas, cy_canvas, cx_canvas + cw_canvas, cy_canvas + ch_canvas)
                self.canvas.coords(self.crop_label_id, cx_canvas + 6, cy_canvas + 12)
        else:
            if self.crop_guide_id is not None:
                self.canvas.delete(self.crop_guide_id)
                self.canvas.delete(self.crop_label_id)
                self.crop_guide_id = None
                self.crop_label_id = None

        # 10. Mask boxes overlays
        self._update_mask_overlays(is_cropped_view)

        # 11. Autogrid 3x3 overlay
        self._update_grid_overlay()

        # 12. Subtitle persistent items
        self._update_sub_canvas_items()

    def _update_mask_overlays(self, is_cropped_view: bool):
        for rid, tid in self.mask_item_ids:
            self.canvas.delete(rid)
            self.canvas.delete(tid)
        self.mask_item_ids.clear()

        if not is_cropped_view:
            origin_x = self.screen_x + self.fit_x
            origin_y = self.screen_y + self.fit_y
            scale = self.fit_scale

            for idx, box in enumerate(self.mask_boxes):
                bx = origin_x + int(box["x"] * scale)
                by = origin_y + int(box["y"] * scale)
                bw = int(box["w"] * scale)
                bh = int(box["h"] * scale)
                color = "#3b82f6" if box.get("type") == "blur" else "#ef4444"
                lbl_t = f"[{'Blur' if box.get('type') == 'blur' else 'Box'} #{idx+1}]"

                rid = self.canvas.create_rectangle(bx, by, bx + bw, by + bh, outline=color, width=2)
                tid = self.canvas.create_text(bx + 4, by + 10, text=lbl_t, fill=color, font=("Segoe UI", 9, "bold"), anchor=tk.W)
                self.mask_item_ids.append((rid, tid))

    def _update_sub_canvas_items(self):
        """Vẽ hoặc cập nhật vị trí phụ đề trên khung chuẩn 16:9 theo tỉ lệ % chiều cao màn hình."""
        sub_px = self.screen_x + int(self.screen_w * self.sub_x_ratio)
        sub_py = self.screen_y + int(self.screen_h * self.sub_y_ratio)

        # Chuẩn hóa cỡ chữ theo % chiều cao khung nhìn preview (đồng bộ 100% với video render)
        try:
            raw_fs = float(self.sub_font_size)
        except Exception:
            raw_fs = 5.5
        fs_percent = 5.5 if raw_fs >= 18.0 else max(1.5, min(25.0, raw_fs))

        # Tkinter font với số âm là kích thước chuẩn xác theo PIXEL: -preview_pixel_h
        preview_pixel_h = max(8, int(round(self.screen_h * (fs_percent / 100.0))))
        font_spec = (self.sub_font_family, -preview_pixel_h, "bold")

        # Viền chữ co giãn hài hòa theo kích thước font
        outline_px = max(1, int(round(preview_pixel_h * 0.08)))
        offsets = [
            (-outline_px, 0), (outline_px, 0), (0, -outline_px), (0, outline_px),
            (-outline_px, -outline_px), (outline_px, outline_px),
            (-outline_px, outline_px), (outline_px, -outline_px)
        ]

        if not self.sub_shadow_ids:
            for dx, dy in offsets:
                sid = self.canvas.create_text(sub_px + dx, sub_py + dy, text=self.sub_text, fill=self.sub_border_color, font=font_spec, justify=tk.CENTER)
                self.sub_shadow_ids.append((sid, dx, dy))
        else:
            if len(self.sub_shadow_ids) != len(offsets):
                for sid, _, _ in self.sub_shadow_ids:
                    self.canvas.delete(sid)
                self.sub_shadow_ids.clear()
                for dx, dy in offsets:
                    sid = self.canvas.create_text(sub_px + dx, sub_py + dy, text=self.sub_text, fill=self.sub_border_color, font=font_spec, justify=tk.CENTER)
                    self.sub_shadow_ids.append((sid, dx, dy))
            else:
                for idx, (sid, _, _) in enumerate(self.sub_shadow_ids):
                    dx, dy = offsets[idx]
                    self.canvas.coords(sid, sub_px + dx, sub_py + dy)
                    self.canvas.itemconfig(sid, text=self.sub_text, fill=self.sub_border_color, font=font_spec)

        if self.sub_text_id is None:
            self.sub_text_id = self.canvas.create_text(sub_px, sub_py, text=self.sub_text, fill=self.sub_text_color, font=font_spec, justify=tk.CENTER)
        else:
            self.canvas.coords(self.sub_text_id, sub_px, sub_py)
            self.canvas.itemconfig(self.sub_text_id, text=self.sub_text, fill=self.sub_text_color, font=font_spec)

        if self.interaction_mode == "sub":
            bbox = self.canvas.bbox(self.sub_text_id)
            if bbox:
                pad = 4
                if self.sub_box_id is None:
                    self.sub_box_id = self.canvas.create_rectangle(bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad, outline="#38bdf8", dash=(3, 3), width=1)
                    self.sub_hint_id = self.canvas.create_text(bbox[0] - pad, bbox[1] - pad - 8, text="✥ Kéo phụ đề (Hút trục tự động)", fill="#38bdf8", font=("Segoe UI", 8), anchor=tk.W)
                else:
                    self.canvas.coords(self.sub_box_id, bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)
                    self.canvas.coords(self.sub_hint_id, bbox[0] - pad, bbox[1] - pad - 8)
        else:
            if self.sub_box_id is not None:
                self.canvas.delete(self.sub_box_id)
                self.canvas.delete(self.sub_hint_id)
                self.sub_box_id = None
                self.sub_hint_id = None

    # ==========================
    # CHUỘT TƯƠNG TÁC + SMART MAGNETIC SNAPPING TRÊN KHUNG 16:9
    # ==========================
    def _on_mouse_down(self, event):
        self.drag_start_x = event.x
        self.drag_start_y = event.y

        if self.interaction_mode == "sub":
            self.is_dragging_sub = True
            self._drag_subtitle_coords_only(event.x, event.y)
        elif self.interaction_mode in ("blur", "black", "crop"):
            color = "#10b981" if self.interaction_mode == "crop" else ("#3b82f6" if self.interaction_mode == "blur" else "#ef4444")
            self.current_drawing_box = self.canvas.create_rectangle(
                event.x, event.y, event.x, event.y,
                outline=color, width=2, dash=(2, 2)
            )

    def _calc_constrained_coords(self, cur_x: int, cur_y: int) -> Tuple[int, int]:
        """Tính tọa độ đích theo tỉ lệ khóa khi kéo chuột (16:9, 9:16, 1:1, free)."""
        if self.interaction_mode != "crop" or self.crop_aspect_ratio == "free":
            return cur_x, cur_y

        dx = cur_x - self.drag_start_x
        dy = cur_y - self.drag_start_y
        sign_x = 1 if dx >= 0 else -1
        sign_y = 1 if dy >= 0 else -1

        if self.crop_aspect_ratio == "16:9":
            w = abs(dx)
            h = int(w * 9.0 / 16.0)
            return self.drag_start_x + sign_x * w, self.drag_start_y + sign_y * h
        elif self.crop_aspect_ratio == "9:16":
            h = abs(dy)
            w = int(h * 9.0 / 16.0)
            return self.drag_start_x + sign_x * w, self.drag_start_y + sign_y * h
        elif self.crop_aspect_ratio == "1:1":
            side = min(abs(dx), abs(dy))
            return self.drag_start_x + sign_x * side, self.drag_start_y + sign_y * side

        return cur_x, cur_y

    def _on_mouse_move(self, event):
        if self.interaction_mode == "sub" and self.is_dragging_sub:
            self._drag_subtitle_coords_only(event.x, event.y)
        elif self.interaction_mode in ("blur", "black", "crop") and self.current_drawing_box:
            end_x, end_y = self._calc_constrained_coords(event.x, event.y)
            self.canvas.coords(
                self.current_drawing_box,
                self.drag_start_x, self.drag_start_y, end_x, end_y
            )

    def _drag_subtitle_coords_only(self, mouse_x: int, mouse_y: int):
        """Cập nhật tọa độ phụ đề trên khung 16:9 với thuật toán Hút Nam Châm thông minh (0ms lag)."""
        if self.screen_w <= 0 or self.screen_h <= 0:
            return

        sx = self.screen_x
        sy = self.screen_y
        sw = self.screen_w
        sh = self.screen_h

        raw_rx = (mouse_x - sx) / float(sw)
        raw_ry = (mouse_y - sy) / float(sh)

        snapped_x = raw_rx
        snapped_y = raw_ry

        snap_px = None
        snap_label_x = None
        snap_py = None
        snap_label_y = None

        # 🧲 THUẬT TOÁN HÚT TRỤC TỰ ĐỘNG TRÊN KHUNG 16:9
        if self.enable_snapping:
            tol_px = 16

            # 1. Hút trục dọc chính giữa (X = 50%) của khung 16:9
            center_x_px = sx + sw * 0.5
            if abs(mouse_x - center_x_px) <= tol_px:
                snapped_x = 0.5
                snap_px = center_x_px
                snap_label_x = "📐 CĂN GIỮA DỌC (50%)"

            # 2. Hút các mốc trục ngang Y trên khung 16:9 (Chuẩn TikTok 85%, Trung tâm 50%, 80%, Đỉnh 15%)
            y_targets = [
                (0.85, "📐 VỊ TRÍ SUB CHUẨN (85%)", "#10b981"),
                (0.50, "📐 TRUNG TÂM NGANG (50%)", "#fbbf24"),
                (0.80, "📐 VỊ TRÍ SUB (80%)", "#10b981"),
                (0.15, "📐 TIÊU ĐỀ ĐỈNH (15%)", "#a855f7")
            ]

            for t_ratio, t_label, t_col in y_targets:
                target_y_px = sy + sh * t_ratio
                if abs(mouse_y - target_y_px) <= tol_px:
                    snapped_y = t_ratio
                    snap_py = target_y_px
                    snap_label_y = t_label
                    self._snap_y_color = t_col
                    break

        self.sub_x_ratio = max(0.05, min(0.95, snapped_x))
        self.sub_y_ratio = max(0.05, min(0.95, snapped_y))

        sub_px = sx + int(sw * self.sub_x_ratio)
        sub_py = sy + int(sh * self.sub_y_ratio)

        # Di chuyển phụ đề siêu mượt (0ms)
        if self.sub_text_id:
            self.canvas.coords(self.sub_text_id, sub_px, sub_py)
        for sid, dx, dy in self.sub_shadow_ids:
            self.canvas.coords(sid, sub_px + dx, sub_py + dy)

        if self.sub_box_id and self.sub_text_id:
            bbox = self.canvas.bbox(self.sub_text_id)
            if bbox:
                pad = 4
                self.canvas.coords(self.sub_box_id, bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)
                self.canvas.coords(self.sub_hint_id, bbox[0] - pad, bbox[1] - pad - 8)

        # Cập nhật đường gióng thông minh
        self._update_snap_guides(snap_px, snap_label_x, snap_py, snap_label_y)

    def _on_mouse_up(self, event):
        if self.interaction_mode == "sub":
            self.is_dragging_sub = False
            self._clear_snap_guides()
            if self.on_sub_pos_changed:
                self.on_sub_pos_changed(self.sub_x_ratio, self.sub_y_ratio)

        elif self.interaction_mode in ("blur", "black", "crop") and self.current_drawing_box:
            self.canvas.delete(self.current_drawing_box)
            self.current_drawing_box = None

            end_x, end_y = self._calc_constrained_coords(event.x, event.y)
            x1, x2 = sorted([self.drag_start_x, end_x])
            y1, y2 = sorted([self.drag_start_y, end_y])

            if (x2 - x1) > 10 and (y2 - y1) > 10 and self.fit_scale > 0:
                is_cropped_active = (
                    self.crop_box and self.crop_box.get("enabled") and
                    self.crop_view_mode == "cropped" and self.interaction_mode != "crop"
                )
                base_cx = self.crop_box["x"] if is_cropped_active else 0
                base_cy = self.crop_box["y"] if is_cropped_active else 0

                origin_vx = self.screen_x + self.fit_x
                origin_vy = self.screen_y + self.fit_y
                scale = self.fit_scale

                vx = base_cx + max(0, int((x1 - origin_vx) / scale))
                vy = base_cy + max(0, int((y1 - origin_vy) / scale))
                vw = int((x2 - x1) / scale)
                vh = int((y2 - y1) / scale)

                # Giới hạn an toàn trong kích thước video gốc
                vx = max(0, min(self.video_width - 10, vx))
                vy = max(0, min(self.video_height - 10, vy))
                vw = max(10, min(self.video_width - vx, vw))
                vh = max(10, min(self.video_height - vy, vh))

                if vw > 10 and vh > 10:
                    if self.interaction_mode in ("blur", "black"):
                        new_box = {
                            "id": len(self.mask_boxes) + 1,
                            "type": self.interaction_mode,
                            "x": vx,
                            "y": vy,
                            "w": vw,
                            "h": vh
                        }
                        self.mask_boxes.append(new_box)
                        if self.on_boxes_changed:
                            self.on_boxes_changed(self.mask_boxes)

                    elif self.interaction_mode == "crop":
                        self.crop_box = {
                            "enabled": True,
                            "x": vx,
                            "y": vy,
                            "w": vw,
                            "h": vh
                        }
                        self.crop_view_mode = "cropped"
                        self.interaction_mode = "sub"
                        if self.on_crop_changed:
                            self.on_crop_changed(self.crop_box)

            if self._last_frame_bgr is not None and not self.is_playing:
                self._render_frame(self._last_frame_bgr)

    # ==========================
    # SETTER & CONFIG METHODS
    # ==========================
    def set_subtitle_style(
        self,
        font_family: str,
        font_size: float,
        text_color: str,
        border_color: str,
        border_width: int,
        text_sample: str = "Phụ đề tiếng Việt xem trước"
    ):
        self.sub_font_family = font_family
        self.sub_font_size = font_size
        self.sub_text_color = text_color
        self.sub_border_color = border_color
        self.sub_border_width = border_width
        self.sub_text = text_sample
        if self._last_frame_bgr is not None and not self.is_playing:
            self._render_frame(self._last_frame_bgr)

    def set_subtitle_coords(self, x_ratio: float, y_ratio: float):
        self.sub_x_ratio = max(0.0, min(1.0, x_ratio))
        self.sub_y_ratio = max(0.0, min(1.0, y_ratio))
        if self._last_frame_bgr is not None and not self.is_playing:
            self._render_frame(self._last_frame_bgr)

    def remove_mask_box(self, index: int):
        if 0 <= index < len(self.mask_boxes):
            del self.mask_boxes[index]
            if self.on_boxes_changed:
                self.on_boxes_changed(self.mask_boxes)
            if self._last_frame_bgr is not None and not self.is_playing:
                self._render_frame(self._last_frame_bgr)

    def clear_all_mask_boxes(self):
        self.mask_boxes.clear()
        if self.on_boxes_changed:
            self.on_boxes_changed(self.mask_boxes)
        if self._last_frame_bgr is not None and not self.is_playing:
            self._render_frame(self._last_frame_bgr)

    def reset_crop(self):
        self.crop_box = None
        self.crop_view_mode = "full"
        if self.on_crop_changed:
            self.on_crop_changed(None)
        if self._last_frame_bgr is not None and not self.is_playing:
            self._render_frame(self._last_frame_bgr)

    def toggle_crop_view(self) -> str:
        if self.crop_view_mode == "cropped":
            self.crop_view_mode = "full"
        else:
            self.crop_view_mode = "cropped"
        if self._last_frame_bgr is not None and not self.is_playing:
            self._render_frame(self._last_frame_bgr)
        return self.crop_view_mode

    def set_overlay_info(self, info: Optional[Dict[str, Any]]):
        self.overlay_info = info
        if self._last_frame_bgr is not None and not self.is_playing:
            self._render_frame(self._last_frame_bgr)

    def release(self):
        self.pause()
        if self.cap:
            self.cap.release()
            self.cap = None
