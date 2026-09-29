import customtkinter as ctk
import threading
from typing import Dict, Any, Callable
from pathlib import Path
import winsound

from core.capcut_service import capcut_service
from utils.logger import app_logger
from utils.temp_manager import temp_manager

class TabTTS(ctk.CTkFrame):
    """
    Tab 3: Cài đặt Text-To-Speech (TTS) CapCut & Auto Audio Ducking
    """
    def __init__(self, master, app_state: Dict[str, Any], on_state_updated: Callable[[], None], **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.app_state = app_state
        self.on_state_updated = on_state_updated

        self.voices = capcut_service.get_vietnamese_voices()
        self.voice_map = {}
        for v in self.voices:
            label = f"{v['display_name']} ({v['voice_type']})"
            self.voice_map[label] = v["voice_type"]

        self._build_ui()
        self._load_from_state()

    def _build_ui(self):
        container = ctk.CTkScrollableFrame(self, fg_color="#18181b", corner_radius=8)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # 1. Kích hoạt TTS
        top_box = ctk.CTkFrame(container, fg_color="#202024")
        top_box.pack(fill="x", padx=15, pady=(15, 10))

        self.sw_enable_tts = ctk.CTkSwitch(
            top_box,
            text="Bật tính năng lồng tiếng tự động (TTS tiếng Việt)",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_tts_toggled
        )
        self.sw_enable_tts.pack(side="left", padx=15, pady=12)
        self.sw_enable_tts.select()

        # 2. Chọn giọng đọc CapCut
        voice_box = ctk.CTkFrame(container, fg_color="#202024")
        voice_box.pack(fill="x", padx=15, pady=5)

        ctk.CTkLabel(
            voice_box,
            text="Giọng đọc CapCut tiếng Việt:",
            font=ctk.CTkFont(size=13, weight="bold")
        ).pack(anchor="w", padx=15, pady=(12, 4))

        voice_row = ctk.CTkFrame(voice_box, fg_color="transparent")
        voice_row.pack(fill="x", padx=15, pady=(0, 12))

        voice_labels = list(self.voice_map.keys()) if self.voice_map else ["Mặc định (BV074_streaming)"]
        self.cbo_voice = ctk.CTkComboBox(
            voice_row,
            values=voice_labels,
            width=380,
            command=self._on_voice_changed
        )
        self.cbo_voice.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.btn_test_voice = ctk.CTkButton(
            voice_row,
            text="🔊 Nghe thử giọng",
            fg_color="#3b82f6",
            hover_color="#2563eb",
            width=130,
            command=self._test_voice
        )
        self.btn_test_voice.pack(side="right")

        # 3. Tốc độ đọc (Speech Rate)
        rate_box = ctk.CTkFrame(container, fg_color="#202024")
        rate_box.pack(fill="x", padx=15, pady=5)

        rate_top = ctk.CTkFrame(rate_box, fg_color="transparent")
        rate_top.pack(fill="x", padx=15, pady=(10, 0))
        ctk.CTkLabel(rate_top, text="Tốc độ đọc (Speech Rate):", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.lbl_rate_val = ctk.CTkLabel(rate_top, text="1.0x", font=ctk.CTkFont(weight="bold"))
        self.lbl_rate_val.pack(side="right")

        self.slider_rate = ctk.CTkSlider(
            rate_box,
            from_=0.6,
            to=1.8,
            number_of_steps=24,
            command=self._on_rate_changed
        )
        self.slider_rate.pack(fill="x", padx=15, pady=(4, 12))

        # 4. Âm lượng Thuyết minh (TTS Volume)
        tts_vol_box = ctk.CTkFrame(container, fg_color="#202024")
        tts_vol_box.pack(fill="x", padx=15, pady=5)

        tts_vol_top = ctk.CTkFrame(tts_vol_box, fg_color="transparent")
        tts_vol_top.pack(fill="x", padx=15, pady=(10, 0))
        ctk.CTkLabel(tts_vol_top, text="Âm lượng lồng tiếng TTS:", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.lbl_tts_vol = ctk.CTkLabel(tts_vol_top, text="100%", font=ctk.CTkFont(weight="bold"))
        self.lbl_tts_vol.pack(side="right")

        self.slider_tts_vol = ctk.CTkSlider(
            tts_vol_box,
            from_=0.0,
            to=2.0,
            number_of_steps=40,
            command=self._on_tts_vol_changed
        )
        self.slider_tts_vol.pack(fill="x", padx=15, pady=(4, 12))

        # 5. Âm lượng Video gốc (Original Volume)
        orig_vol_box = ctk.CTkFrame(container, fg_color="#202024")
        orig_vol_box.pack(fill="x", padx=15, pady=5)

        orig_vol_top = ctk.CTkFrame(orig_vol_box, fg_color="transparent")
        orig_vol_top.pack(fill="x", padx=15, pady=(10, 0))
        ctk.CTkLabel(orig_vol_top, text="Âm lượng âm thanh gốc:", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.lbl_orig_vol = ctk.CTkLabel(orig_vol_top, text="100%", font=ctk.CTkFont(weight="bold"))
        self.lbl_orig_vol.pack(side="right")

        self.slider_orig_vol = ctk.CTkSlider(
            orig_vol_box,
            from_=0.0,
            to=1.5,
            number_of_steps=30,
            command=self._on_orig_vol_changed
        )
        self.slider_orig_vol.pack(fill="x", padx=15, pady=(4, 12))

        # 6. Auto Audio Ducking
        duck_box = ctk.CTkFrame(container, fg_color="#202024")
        duck_box.pack(fill="x", padx=15, pady=(5, 15))

        self.sw_ducking = ctk.CTkSwitch(
            duck_box,
            text="Bật Auto Audio Ducking (Tự động hạ âm thanh gốc khi thuyết minh)",
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._on_ducking_toggled
        )
        self.sw_ducking.pack(anchor="w", padx=15, pady=(12, 6))
        self.sw_ducking.select()

        duck_val_row = ctk.CTkFrame(duck_box, fg_color="transparent")
        duck_val_row.pack(fill="x", padx=15, pady=(4, 0))
        ctk.CTkLabel(duck_val_row, text="Mức âm lượng nền khi đang nói:").pack(side="left")
        self.lbl_duck_val = ctk.CTkLabel(duck_val_row, text="18%", font=ctk.CTkFont(weight="bold"))
        self.lbl_duck_val.pack(side="right")

        self.slider_duck = ctk.CTkSlider(
            duck_box,
            from_=0.05,
            to=0.40,
            number_of_steps=35,
            command=self._on_duck_changed
        )
        self.slider_duck.pack(fill="x", padx=15, pady=(4, 6))

        lbl_duck_info = ctk.CTkLabel(
            duck_box,
            text="Khuyến nghị 15% - 20%: Nhạc nền sẽ tự động giảm êm dịu khi có tiếng nói tiếng Việt và phục hồi 100% khi im lặng.",
            font=ctk.CTkFont(size=11),
            text_color="#a1a1aa",
            anchor="w"
        )
        lbl_duck_info.pack(fill="x", padx=15, pady=(0, 12))

    def _load_from_state(self):
        self.sw_enable_tts.select() if self.app_state.get("enable_tts", True) else self.sw_enable_tts.deselect()
        self.sw_ducking.select() if self.app_state.get("enable_ducking", True) else self.sw_ducking.deselect()

        rate = self.app_state.get("speech_rate", 1.0)
        self.slider_rate.set(rate)
        self.lbl_rate_val.configure(text=f"{rate:.2f}x")

        tts_v = self.app_state.get("tts_volume", 1.0)
        self.slider_tts_vol.set(tts_v)
        self.lbl_tts_vol.configure(text=f"{int(tts_v * 100)}%")

        orig_v = self.app_state.get("original_volume", 1.0)
        self.slider_orig_vol.set(orig_v)
        self.lbl_orig_vol.configure(text=f"{int(orig_v * 100)}%")

        duck_v = self.app_state.get("ducking_volume", 0.18)
        self.slider_duck.set(duck_v)
        self.lbl_duck_val.configure(text=f"{int(duck_v * 100)}%")

        saved_voice = self.app_state.get("voice_type")
        for lbl, vtype in self.voice_map.items():
            if vtype == saved_voice:
                self.cbo_voice.set(lbl)
                break

    def _on_tts_toggled(self):
        self.app_state["enable_tts"] = bool(self.sw_enable_tts.get())
        self.on_state_updated()

    def _on_ducking_toggled(self):
        self.app_state["enable_ducking"] = bool(self.sw_ducking.get())
        self.on_state_updated()

    def _on_voice_changed(self, choice):
        vtype = self.voice_map.get(choice, "BV074_streaming")
        self.app_state["voice_type"] = vtype
        self.on_state_updated()

    def _on_rate_changed(self, val):
        self.lbl_rate_val.configure(text=f"{val:.2f}x")
        self.app_state["speech_rate"] = float(val)
        self.on_state_updated()

    def _on_tts_vol_changed(self, val):
        self.lbl_tts_vol.configure(text=f"{int(val * 100)}%")
        self.app_state["tts_volume"] = float(val)
        self.on_state_updated()

    def _on_orig_vol_changed(self, val):
        self.lbl_orig_vol.configure(text=f"{int(val * 100)}%")
        self.app_state["original_volume"] = float(val)
        self.on_state_updated()

    def _on_duck_changed(self, val):
        self.lbl_duck_val.configure(text=f"{int(val * 100)}%")
        self.app_state["ducking_volume"] = float(val)
        self.on_state_updated()

    def _test_voice(self):
        """Tạo thử 1 đoạn mẫu ngắn để nghe thử giọng đọc."""
        choice = self.cbo_voice.get()
        vtype = self.voice_map.get(choice, "BV074_streaming")
        rate_val = self.slider_rate.get()

        self.btn_test_voice.configure(state="disabled", text="Đang tạo...")

        def run_test():
            try:
                sample_item = [{"index": 1, "start_time": 0.0, "end_time": 2.0, "text": "Xin chào, đây là giọng đọc thử nghiệm.", "translation": "Xin chào, đây là giọng đọc thử nghiệm."}]
                res = capcut_service.generate_speech_for_subtitles(
                    subtitles=sample_item,
                    voice_type=vtype,
                    speech_rate=rate_val
                )
                if res and res[0].get("audio_path"):
                    audio_p = res[0]["audio_path"]
                    # Chuyển đổi và phát qua winsound hoặc ffplay
                    import subprocess
                    subprocess.run(["ffplay", "-nodisp", "-autoexit", str(audio_p)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e:
                app_logger.warning(f"Không thể phát thử giọng: {e}")
            finally:
                self.after(0, lambda: self.btn_test_voice.configure(state="normal", text="🔊 Nghe thử giọng"))

        threading.Thread(target=run_test, daemon=True).start()
