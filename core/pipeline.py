import os
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional, Callable

from core.capcut_service import capcut_service
from core.translator import translator
from core.audio_ducking import AudioDuckingMixer
from core.subtitle_generator import SubtitleGenerator
from core.video_processor import VideoProcessor
from utils.logger import app_logger
from utils.temp_manager import temp_manager

class PipelineRunner:
    """
    Điều phối toàn bộ quy trình xử lý video từ A-Z trong một luồng riêng biệt:
    1. Kiểm tra video gốc
    2. Trích xuất audio
    3. Nhận diện giọng nói STT (CapCut API)
    4. Dịch thuật sang tiếng Việt (ChatGPT Web qua Playwright / Google Translate)
    5. Tạo lồng tiếng TTS tiếng Việt (CapCut API)
    6. Trộn âm thanh Auto Ducking
    7. Tạo phụ đề ASS 1 dòng với hiệu ứng đồ họa
    8. Render video cuối cùng (Crop, che phụ đề gốc, overlay ảnh, phụ đề, audio)
    9. Dọn dẹp file tạm
    """
    def __init__(
        self,
        video_path: Path,
        output_path: Path,
        settings: Dict[str, Any],
        on_progress: Optional[Callable[[float, str], None]] = None,
        on_subtitles_ready: Optional[Callable[[List[Dict[str, Any]]], None]] = None,
        on_success: Optional[Callable[[Path], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None
    ):
        self.video_path = Path(video_path)
        self.output_path = Path(output_path)
        self.settings = settings
        self.on_progress = on_progress
        self.on_subtitles_ready = on_subtitles_ready
        self.on_success = on_success
        self.on_error = on_error

        self._cancel_flag = False
        self._thread: Optional[threading.Thread] = None

    def cancel(self):
        """Yêu cầu hủy tiến trình ngay lập tức."""
        self._cancel_flag = True
        app_logger.warning("Đang gửi lệnh hủy bỏ tiến trình...")

    def is_cancelled(self) -> bool:
        return self._cancel_flag

    def start(self):
        """Khởi động pipeline trên luồng nền."""
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _update_progress(self, ratio: float, status_text: str):
        if self.on_progress:
            self.on_progress(ratio, status_text)

    def _run(self):
        try:
            app_logger.info(f"=== BẮT ĐẦU QUY TRÌNH XỬ LÝ: {self.video_path.name} ===")
            self._update_progress(0.05, "Bước 1/8: Đang kiểm tra thông tin video...")
            
            # 1. Đọc thông tin video
            video_info = VideoProcessor.get_video_info(self.video_path)
            app_logger.info(f"Độ phân giải: {video_info['width']}x{video_info['height']} | Thời lượng: {video_info['duration']:.2f}s | FPS: {video_info['fps']}")

            if self.is_cancelled():
                raise InterruptedError("Đã hủy bởi người dùng.")

            # 2. Trích xuất audio
            self._update_progress(0.12, "Bước 2/8: Đang trích xuất audio gốc...")
            extracted_audio = VideoProcessor.extract_audio(self.video_path)

            if self.is_cancelled():
                raise InterruptedError("Đã hủy bởi người dùng.")

            # 3. STT nhận diện phụ đề tiếng Trung
            self._update_progress(0.25, "Bước 3/8: Đang nhận diện phụ đề gốc bằng CapCut STT...")
            subtitles = self.settings.get("manual_subtitles")
            if not subtitles:
                if extracted_audio and extracted_audio.exists():
                    try:
                        subtitles = capcut_service.transcribe_audio(
                            audio_path=extracted_audio,
                            source_lang=self.settings.get("stt_language", "zh-CN"),
                            cancel_check=self.is_cancelled
                        )
                    except Exception as e:
                        app_logger.warning(f"CapCut STT báo lỗi ({e}). Tiến hành xử lý với danh sách phụ đề rỗng hoặc tiếp tục.")
                        subtitles = []
                else:
                    app_logger.warning("Video không có audio, bỏ qua bước nhận diện STT.")
                    subtitles = []

            app_logger.info(f"Đã có {len(subtitles)} phân đoạn phụ đề.")

            if self.is_cancelled():
                raise InterruptedError("Đã hủy bởi người dùng.")

            # 4. Dịch thuật sang tiếng Việt
            self._update_progress(0.40, "Bước 4/8: Đang dịch thuật nội dung sang tiếng Việt...")
            trans_engine = self.settings.get("translation_engine", "chatgpt")
            
            if subtitles:
                if trans_engine == "chatgpt":
                    try:
                        subtitles = translator.translate_with_chatgpt(
                            subtitles=subtitles,
                            headless=self.settings.get("chatgpt_headless", False),
                            cancel_check=self.is_cancelled
                        )
                    except Exception as exc:
                        app_logger.warning(f"ChatGPT Web gặp lỗi: {exc}. Tự động chuyển sang Google Translate dự phòng...")
                        subtitles = translator.translate_with_google(subtitles, cancel_check=self.is_cancelled)
                else:
                    subtitles = translator.translate_with_google(subtitles, cancel_check=self.is_cancelled)

            if self.on_subtitles_ready:
                self.on_subtitles_ready(subtitles)

            if self.is_cancelled():
                raise InterruptedError("Đã hủy bởi người dùng.")

            # 5. Tạo lồng tiếng TTS tiếng Việt
            self._update_progress(0.55, "Bước 5/8: Đang tạo giọng đọc TTS bằng CapCut...")
            voice_type = self.settings.get("voice_type", "BV074_streaming")
            speech_rate = float(self.settings.get("speech_rate", 1.0))
            
            if subtitles and self.settings.get("enable_tts", True):
                try:
                    subtitles = capcut_service.generate_speech_for_subtitles(
                        subtitles=subtitles,
                        voice_type=voice_type,
                        speech_rate=speech_rate,
                        cancel_check=self.is_cancelled
                    )
                except Exception as tts_err:
                    app_logger.warning(f"Lỗi tạo TTS ({tts_err}). Bỏ qua phần giọng đọc và giữ âm thanh gốc.")

            if self.is_cancelled():
                raise InterruptedError("Đã hủy bởi người dùng.")

            # 6. Auto Audio Ducking & Trộn âm thanh
            self._update_progress(0.68, "Bước 6/8: Đang xử lý Auto Audio Ducking...")
            mixed_audio = None
            if self.settings.get("enable_ducking", True) and subtitles:
                mixed_audio = AudioDuckingMixer.mix_audio(
                    original_audio_path=extracted_audio,
                    subtitles=subtitles,
                    total_duration=video_info["duration"],
                    ducking_volume=float(self.settings.get("ducking_volume", 0.18)),
                    tts_volume=float(self.settings.get("tts_volume", 1.0)),
                    original_volume=float(self.settings.get("original_volume", 1.0))
                )
            else:
                mixed_audio = extracted_audio

            if self.is_cancelled():
                raise InterruptedError("Đã hủy bởi người dùng.")

            # 7. Tạo phụ đề ASS 1 dòng
            self._update_progress(0.75, "Bước 7/8: Đang tạo đồ họa phụ đề 1 dòng với hiệu ứng...")
            # Lấy cấu hình xuất (CapCut Style: Resolution, Bitrate, FPS, Codec)
            export_settings = dict(self.settings.get("export_settings") or {})
            res_opt = str(export_settings.get("resolution", "1080p")).lower()

            orig_w = video_info.get("width", 1920) if video_info else 1920
            orig_h = video_info.get("height", 1080) if video_info else 1080
            is_vertical = orig_h > orig_w

            if "720" in res_opt:
                sub_w, sub_h = (720, 1280) if is_vertical else (1280, 720)
            elif "2k" in res_opt or "1440" in res_opt:
                sub_w, sub_h = (1440, 2560) if is_vertical else (2560, 1440)
            elif "4k" in res_opt or "2160" in res_opt:
                sub_w, sub_h = (2160, 3840) if is_vertical else (3840, 2160)
            elif "gốc" in res_opt or "orig" in res_opt:
                sub_w, sub_h = orig_w, orig_h
            else:
                sub_w, sub_h = (1080, 1920) if is_vertical else (1920, 1080)

            export_settings["target_width"] = sub_w
            export_settings["target_height"] = sub_h

            ass_sub_path = None
            if subtitles and self.settings.get("enable_subtitles", True):
                ass_sub_path = temp_manager.get_temp_file(suffix=".ass", name="subtitles.ass")
                
                SubtitleGenerator.build_ass(
                    subtitles=subtitles,
                    video_width=sub_w,
                    video_height=sub_h,
                    style_config=self.settings.get("subtitle_style", {}),
                    output_file=ass_sub_path
                )

            if self.is_cancelled():
                raise InterruptedError("Đã hủy bởi người dùng.")

            # 8. Render video xuất xưởng
            codec_lbl = export_settings.get("codec", "H.264")
            self._update_progress(0.82, f"Bước 8/8: Đang render video ({sub_w}x{sub_h} • {codec_lbl})...")
            
            def render_progress(ratio: float, msg: str):
                scaled = 0.82 + (ratio * 0.17)
                self._update_progress(scaled, msg)

            final_video = VideoProcessor.render_final_video(
                video_path=self.video_path,
                mixed_audio_path=mixed_audio,
                ass_sub_path=ass_sub_path,
                output_path=self.output_path,
                video_info=video_info,
                mask_boxes=self.settings.get("mask_boxes", []),
                crop_box=self.settings.get("crop_box", None),
                overlay_info=self.settings.get("overlay_info", None),
                progress_callback=render_progress,
                cancel_check=self.is_cancelled,
                export_settings=export_settings
            )

            # Đảm bảo video đã render hoàn tất và hợp lệ trước khi dọn dẹp cache
            if final_video and final_video.exists() and final_video.stat().st_size > 0:
                self._update_progress(1.0, "HOÀN TẤT XUẤT VIDEO!")
                app_logger.success(f"=== ĐÃ XUẤT THÀNH CÔNG: {final_video} ===")

                if self.on_success:
                    self.on_success(final_video)

                # CHỈ dọn dẹp file tạm SAU KHI render xong xuôi hoàn toàn 100%
                app_logger.info("Đang tự động dọn dẹp các file âm thanh & phụ đề tạm...")
                temp_manager.cleanup_all()
            else:
                raise RuntimeError("File video xuất ra không tồn tại hoặc bị lỗi 0-byte.")

        except InterruptedError:
            app_logger.warning("Quy trình xử lý đã dừng lại theo lệnh của người dùng.")
            temp_manager.cleanup_all()
            self._update_progress(0.0, "Đã hủy bỏ tiến trình.")
        except Exception as e:
            app_logger.error(f"Lỗi trong quy trình xử lý: {e}")
            # Giữ lại cache khi gặp lỗi để không xóa mất dữ liệu dịch/audio và phục vụ kiểm tra
            if self.on_error:
                self.on_error(e)
