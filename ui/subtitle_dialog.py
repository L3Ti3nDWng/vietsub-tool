import customtkinter as ctk
from typing import List, Dict, Any, Callable, Optional

class SubtitleEditorDialog(ctk.CTkToplevel):
    """
    Hộp thoại chỉnh sửa chi tiết phụ đề tiếng Trung & tiếng Việt:
    - Cho phép user đọc lại toàn bộ câu dịch, sửa lỗi ngữ nghĩa.
    - Chỉnh sửa mốc thời gian bắt đầu và kết thúc (Start/End time).
    - Thêm hoặc xóa bớt câu phụ đề trước khi render xuất video.
    """
    def __init__(
        self,
        master,
        subtitles: List[Dict[str, Any]],
        on_save_callback: Callable[[List[Dict[str, Any]]], None],
        on_seek_callback: Optional[Callable[[float], None]] = None
    ):
        super().__init__(master)
        self.title("Chỉnh sửa phụ đề & Dịch thuật - Douyin Translator Pro")
        self.geometry("900x600")
        self.minsize(800, 500)
        self.transient(master)
        self.grab_set()

        self.subtitles = [dict(s) for s in subtitles] # bản sao
        self.on_save_callback = on_save_callback
        self.on_seek_callback = on_seek_callback
        self.row_widgets = []

        self._build_ui()
        self._populate_rows()

    def _build_ui(self):
        # Header toolbar
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.pack(fill="x", padx=15, pady=(15, 10))

        title_lbl = ctk.CTkLabel(
            header_frame,
            text="Danh sách phân đoạn phụ đề",
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold")
        )
        title_lbl.pack(side="left")

        add_btn = ctk.CTkButton(
            header_frame,
            text="+ Thêm dòng mới",
            width=130,
            command=self._add_row
        )
        add_btn.pack(side="right", padx=(10, 0))

        save_btn = ctk.CTkButton(
            header_frame,
            text="Lưu thay đổi ✓",
            fg_color="#10b981",
            hover_color="#059669",
            width=130,
            command=self._save_and_close
        )
        save_btn.pack(side="right")

        # Table header labels
        col_header = ctk.CTkFrame(self, height=30, fg_color="#27272a")
        col_header.pack(fill="x", padx=15, pady=(0, 5))

        headers = [
            ("#", 40),
            ("Bắt đầu (s)", 90),
            ("Kết thúc (s)", 90),
            ("Văn bản gốc (Trung)", 240),
            ("Bản dịch tiếng Việt", 320),
            ("Thao tác", 80)
        ]
        for name, width in headers:
            lbl = ctk.CTkLabel(
                col_header,
                text=name,
                width=width,
                font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"),
                anchor="w"
            )
            lbl.pack(side="left", padx=5)

        # Scrollable rows frame
        self.scroll_frame = ctk.CTkScrollableFrame(self, fg_color="#18181b")
        self.scroll_frame.pack(fill="both", expand=True, padx=15, pady=(0, 15))

    def _populate_rows(self):
        # Xóa các widget cũ
        for widgets in self.row_widgets:
            for w in widgets.values():
                w.destroy()
        self.row_widgets.clear()

        for idx, sub in enumerate(self.subtitles):
            self._create_row_ui(idx, sub)

    def _create_row_ui(self, idx: int, sub: Dict[str, Any]):
        row_frame = ctk.CTkFrame(self.scroll_frame, fg_color="#202024", height=42)
        row_frame.pack(fill="x", pady=2)

        # Index
        lbl_idx = ctk.CTkLabel(row_frame, text=str(idx + 1), width=40)
        lbl_idx.pack(side="left", padx=5)

        # Start Time
        ent_start = ctk.CTkEntry(row_frame, width=90)
        ent_start.insert(0, f"{sub.get('start_time', 0.0):.2f}")
        ent_start.pack(side="left", padx=5)

        # End Time
        ent_end = ctk.CTkEntry(row_frame, width=90)
        ent_end.insert(0, f"{sub.get('end_time', 0.0):.2f}")
        ent_end.pack(side="left", padx=5)

        # Text gốc
        ent_orig = ctk.CTkEntry(row_frame, width=240)
        ent_orig.insert(0, sub.get("text", ""))
        ent_orig.pack(side="left", padx=5)

        # Bản dịch tiếng Việt
        ent_trans = ctk.CTkEntry(row_frame, width=320)
        ent_trans.insert(0, sub.get("translation", ""))
        ent_trans.pack(side="left", padx=5)

        # Nút xóa
        del_btn = ctk.CTkButton(
            row_frame,
            text="✕",
            width=32,
            fg_color="#ef4444",
            hover_color="#dc2626",
            command=lambda i=idx: self._delete_row(i)
        )
        del_btn.pack(side="left", padx=5)

        self.row_widgets.append({
            "frame": row_frame,
            "ent_start": ent_start,
            "ent_end": ent_end,
            "ent_orig": ent_orig,
            "ent_trans": ent_trans
        })

    def _add_row(self):
        last_end = 0.0
        if self.subtitles:
            last_end = self.subtitles[-1].get("end_time", 0.0)

        new_sub = {
            "index": len(self.subtitles) + 1,
            "start_time": last_end + 0.2,
            "end_time": last_end + 2.5,
            "text": "",
            "translation": ""
        }
        self.subtitles.append(new_sub)
        self._populate_rows()

    def _delete_row(self, index: int):
        self._collect_current_data()
        if 0 <= index < len(self.subtitles):
            del self.subtitles[index]
            for i, s in enumerate(self.subtitles):
                s["index"] = i + 1
            self._populate_rows()

    def _collect_current_data(self):
        updated = []
        for idx, w in enumerate(self.row_widgets):
            try:
                st = float(w["ent_start"].get())
            except ValueError:
                st = 0.0
            try:
                et = float(w["ent_end"].get())
            except ValueError:
                et = st + 1.0

            orig_t = w["ent_orig"].get().strip()
            trans_t = w["ent_trans"].get().strip()

            updated.append({
                "index": idx + 1,
                "start_time": st,
                "end_time": et,
                "text": orig_t,
                "translation": trans_t
            })
        self.subtitles = updated

    def _save_and_close(self):
        self._collect_current_data()
        self.on_save_callback(self.subtitles)
        self.destroy()
