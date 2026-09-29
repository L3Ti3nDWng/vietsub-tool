import os
import subprocess
import customtkinter as ctk
from tkinter import filedialog, messagebox
from pathlib import Path
from typing import Dict, Any, Callable, Optional

from core.pipeline import PipelineRunner
from utils.logger import app_logger

class TabProcess(ctk.CTkFrame):
    """
    Tab 5: Cấu hình dịch thuật, Thanh tiến trình, Nhật ký Log real-time & Nút Bắt đầu / Hủy bỏ
    """
    def __init__(self, master, app_state: Dict[str, Any], on_state_updated: Callable[[], None], **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app_state = app_state
        self.on_state_updated = on_state_updated
        self.active_runner: Optional[PipelineRunner] = None

        self._build_ui()
        app_logger.register_callback(self._on_log_received)

    def _build_ui(self):
        # 1. Hàng cấu hình Dịch thuật & Nơi lưu file
        top_box = ctk.CTkFrame(self, fg_color="#18181b", corner_radius=8)
        top_box.pack(fill="x", padx=10, pady=(10, 5))

        # Công cụ dịch
        row1 = ctk.CTkFrame(top_box, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=(10, 4))
        
        ctk.CTkLabel(row1, text="Bộ máy dịch thuật:", font=ctk.CTkFont(weight="bold"), width=160, anchor="w").pack(side="left")
        self.cbo_engine = ctk.CTkComboBox(
            row1,
            values=["ChatGPT Web (Playwright Chromium)", "Google Translate (Dự phòng nhanh / Miễn phí)"],
            width=320,
            command=self._on_engine_changed
        )
        self.cbo_engine.pack(side="left", padx=5)

        self.chk_headless = ctk.CTkCheckBox(
            row1,
            text="Chạy ẩn ChatGPT (Headless)",
            command=self._on_headless_toggled
        )
        self.chk_headless.pack(side="left", padx=10)
        self.chk_headless.deselect()

        btn_login = ctk.CTkButton(
            row1,
            text="🔑 Đăng nhập ChatGPT",
            width=140,
            fg_color="#2563eb",
            hover_color="#1d4ed8",
            command=self._open_chatgpt_for_login
        )
        btn_login.pack(side="left", padx=5)

        # Đường dẫn xuất file
        row2 = ctk.CTkFrame(top_box, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=(4, 10))

        ctk.CTkLabel(row2, text="Đường dẫn video xuất ra:", font=ctk.CTkFont(weight="bold"), width=160, anchor="w").pack(side="left")
        self.ent_output = ctk.CTkEntry(row2, placeholder_text="Đường dẫn file video đầu ra (.mp4)...")
        self.ent_output.pack(side="left", fill="x", expand=True, padx=5)

        btn_browse_out = ctk.CTkButton(row2, text="Chọn nơi lưu...", width=110, command=self._browse_output)
        btn_browse_out.pack(side="left", padx=(0, 10))

        self.chk_auto_open = ctk.CTkCheckBox(row2, text="Mở video khi hoàn tất")
        self.chk_auto_open.pack(side="left")
        self.chk_auto_open.select()

        # 2. Khung Nút Bắt đầu & Hủy bỏ
        action_box = ctk.CTkFrame(self, fg_color="#18181b", corner_radius=8)
        action_box.pack(fill="x", padx=10, pady=5)

        action_inner = ctk.CTkFrame(action_box, fg_color="transparent")
        action_inner.pack(fill="x", padx=15, pady=12)

        self.btn_start = ctk.CTkButton(
            action_inner,
            text="🚀 BẮT ĐẦU XỬ LÝ & XUẤT VIDEO",
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#10b981",
            hover_color="#059669",
            height=42,
            command=self._start_pipeline
        )
        self.btn_start.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_cancel = ctk.CTkButton(
            action_inner,
            text="🛑 HỦY BỎ",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#ef4444",
            hover_color="#dc2626",
            height=42,
            width=120,
            state="disabled",
            command=self._cancel_pipeline
        )
        self.btn_cancel.pack(side="right")

        # 3. Khung Tiến trình (Progress Bar)
        prog_box = ctk.CTkFrame(self, fg_color="#18181b", corner_radius=8)
        prog_box.pack(fill="x", padx=10, pady=5)

        self.lbl_progress_status = ctk.CTkLabel(
            prog_box,
            text="Sẵn sàng xử lý video...",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        self.lbl_progress_status.pack(fill="x", padx=15, pady=(10, 4))

        self.progress_bar = ctk.CTkProgressBar(prog_box, height=14)
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 12))
        self.progress_bar.set(0.0)

        # 4. Khung Log Nhật ký real-time
        log_box = ctk.CTkFrame(self, fg_color="#18181b", corner_radius=8)
        log_box.pack(fill="both", expand=True, padx=10, pady=(5, 10))

        log_header = ctk.CTkFrame(log_box, fg_color="transparent")
        log_header.pack(fill="x", padx=15, pady=(10, 4))

        ctk.CTkLabel(
            log_header,
            text="Nhật ký hoạt động (Logs Real-time):",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(side="left")

        btn_clear_log = ctk.CTkButton(
            log_header,
            text="Xóa Log",
            width=80,
            height=26,
            fg_color="#27272a",
            hover_color="#3f3f46",
            command=self._clear_log
        )
        btn_clear_log.pack(side="right")

        self.txt_log = ctk.CTkTextbox(
            log_box,
            fg_color="#09090b",
            font=ctk.CTkFont(family="Consolas", size=11),
            text_color="#e4e4e7"
        )
        self.txt_log.pack(fill="both", expand=True, padx=15, pady=(0, 12))

    def update_default_output(self, out_path: str):
        self.ent_output.delete(0, "end")
        self.ent_output.insert(0, out_path)

    def _browse_output(self):
        f = filedialog.asksaveasfilename(
            title="Chọn nơi lưu file video kết quả",
            defaultextension=".mp4",
            filetypes=[("MP4 Video", "*.mp4"), ("All Files", "*.*")]
        )
        if f:
            self.ent_output.delete(0, "end")
            self.ent_output.insert(0, f)
            self.app_state["output_path"] = f

    def _on_engine_changed(self, choice):
        if "ChatGPT" in choice:
            self.app_state["translation_engine"] = "chatgpt"
        else:
            self.app_state["translation_engine"] = "google"
        self.on_state_updated()

    def _on_headless_toggled(self):
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

    def _on_log_received(self, message: str, level: str):
        def append():
            self.txt_log.insert("end", message + "\n")
            self.txt_log.see("end")
            if hasattr(self, "_active_dialog") and self._active_dialog and self._active_dialog.winfo_exists():
                self._active_dialog.append_log(message)
        self.after(0, append)

    def _clear_log(self):
        self.txt_log.delete("1.0", "end")

    def _start_pipeline(self):
        video_p = self.app_state.get("video_path")
        if not video_p or not Path(video_p).exists():
            messagebox.showwarning("Thông báo", "Vui lòng chọn file video đầu vào trước khi xuất!")
            return

        self.app_state["translation_engine"] = "chatgpt" if "ChatGPT" in self.cbo_engine.get() else "google"
        self.app_state["chatgpt_headless"] = bool(self.chk_headless.get())

        from ui.export_dialog import ExportDialog
        ExportDialog(
            master=self.winfo_toplevel(),
            app_state=self.app_state,
            on_start_export=self._execute_export_pipeline,
            on_cancel_export=self._cancel_pipeline
        )

    def _execute_export_pipeline(self, export_settings: Dict[str, Any], output_path: Path, dialog: Any):
        video_p = self.app_state.get("video_path")
        self.app_state["output_path"] = str(output_path)
        self.app_state["export_settings"] = export_settings
        self.ent_output.delete(0, "end")
        self.ent_output.insert(0, str(output_path))
        self._active_dialog = dialog

        self.btn_start.configure(state="disabled", fg_color="#374151")
        self.btn_cancel.configure(state="normal")
        self.progress_bar.set(0.0)

        def on_prog(ratio: float, status_text: str):
            def update():
                self.progress_bar.set(ratio)
                self.lbl_progress_status.configure(text=f"{status_text} ({int(ratio * 100)}%)")
                if dialog and dialog.winfo_exists():
                    dialog.update_progress(ratio, status_text)
            self.after(0, update)

        def on_sub_ready(subs):
            self.app_state["manual_subtitles"] = subs

        def on_succ(final_video: Path):
            def finish():
                self.btn_start.configure(state="normal", fg_color="#10b981")
                self.btn_cancel.configure(state="disabled")
                self.progress_bar.set(1.0)
                self.lbl_progress_status.configure(text="Đã hoàn tất xuất video thành công! 🎉")
                if dialog and dialog.winfo_exists():
                    dialog.show_success(final_video)
                if self.chk_auto_open.get():
                    try:
                        os.startfile(str(final_video))
                    except Exception:
                        pass
            self.after(0, finish)

        def on_err(exc: Exception):
            def fail():
                self.btn_start.configure(state="normal", fg_color="#10b981")
                self.btn_cancel.configure(state="disabled")
                self.lbl_progress_status.configure(text=f"Lỗi: {exc}")
                if dialog and dialog.winfo_exists():
                    dialog.show_error(str(exc))
                else:
                    messagebox.showerror("Lỗi xử lý", f"Có lỗi xảy ra trong quá trình xử lý:\n{exc}")
            self.after(0, fail)

        self.active_runner = PipelineRunner(
            video_path=Path(video_p),
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
            self.lbl_progress_status.configure(text="Đang hủy tiến trình...")
