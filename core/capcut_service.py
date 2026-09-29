import os
import re
import json
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import requests

from capcut_tts_api.client import CapCutClient
from capcut_tts_api.models import DeviceConfig, SubtitleResult, VoiceInfo
from capcut_tts_api.exceptions import CapCutError, CapCutTaskError
from utils.logger import app_logger
from utils.temp_manager import temp_manager

VOICE_CATALOG_PATH = Path(__file__).parent.parent / "Voice.json"

def sanitize_tts_text(text: str) -> str:
    """Làm sạch văn bản trước khi gửi tới CapCut TTS để tránh lỗi TTSInvalidText."""
    if not text:
        return ""
    # Bỏ mã ID [1], 1., v.v. ở đầu câu
    text = re.sub(r"^\s*\[?\d+\]?[\.\:\-\s]*", "", text)
    # Bỏ ký tự html/markdown và ký tự đặc biệt
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[\#\@\*\_\~\^\|\`\\\/\[\]\{\}\=\+\<\>]", " ", text)
    # Bỏ url và hashtag
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"#\S+", "", text)
    # Bỏ các ký tự lạ, emoji (chỉ giữ chữ cái tiếng Việt/Latin, số, dấu câu thông dụng)
    text = re.sub(r"[^\w\s\.,\?!'-]", " ", text, flags=re.UNICODE)
    # Rút gọn các dấu câu lặp lại liên tiếp
    text = re.sub(r"\.{2,}", ".", text)
    text = re.sub(r"\!{2,}", "!", text)
    text = re.sub(r"\?{2,}", "?", text)
    text = re.sub(r"\-{2,}", "-", text)
    # Chuẩn hóa khoảng trắng
    text = re.sub(r"\s+", " ", text).strip()
    return text

def is_speakable_text(text: str) -> bool:
    """Kiểm tra câu có chứa ký tự chữ/số đọc được không."""
    return bool(text and re.search(r"\w", text))

class CapCutService:
    """
    Dịch vụ giao tiếp với CapCut Cloud API cho Speech-To-Text (STT) và Text-To-Speech (TTS).
    Tối ưu hóa khả năng chịu lỗi, hỗ trợ kiểm tra trạng thái succeed/success,
    tải audio trực tiếp từ CDN và dọn dẹp file tạm an toàn.
    """
    def __init__(self, catalog_path: Path = VOICE_CATALOG_PATH):
        self.device = DeviceConfig()
        self.client = CapCutClient(device=self.device)
        self.catalog_path = catalog_path
        self._cached_voices: Optional[List[Dict[str, Any]]] = None

    def get_vietnamese_voices(self) -> List[Dict[str, Any]]:
        """Lấy danh sách các giọng đọc tiếng Việt từ file Voice.json"""
        if self._cached_voices is not None:
            return self._cached_voices

        if not self.catalog_path.exists():
            app_logger.warning(f"Không tìm thấy file danh mục giọng đọc: {self.catalog_path}")
            return []

        try:
            with open(self.catalog_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            vi_voices = []
            for item in data:
                lan = item.get("lan", "").lower()
                lang = item.get("lang", "").lower()
                if "vi" in lan or "vi" in lang:
                    vi_voices.append({
                        "display_name": item.get("display_name", "Giọng đọc"),
                        "voice_type": item.get("voice_type"),
                        "resource_id": item.get("resource_id", ""),
                        "lang": item.get("lang", "vi-VN")
                    })
            
            self._cached_voices = vi_voices
            return vi_voices
        except Exception as e:
            app_logger.error(f"Lỗi khi đọc danh mục giọng đọc: {e}")
            return []

    def transcribe_audio(
        self,
        audio_path: Path,
        source_lang: str = "zh-CN",
        poll_interval: float = 2.0,
        timeout: float = 180.0,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Gửi audio lên CapCut STT để nhận diện văn bản và mốc thời gian (timestamp).
        Trả về danh sách câu có start_time, end_time (giây) và text gốc.
        """
        app_logger.info(f"Đang tải audio lên CapCut VOD để nhận diện phụ đề ({source_lang})...")
        upload_res = self.client.upload_audio(str(audio_path))
        duration_ms = upload_res.duration_ms or 10000

        if cancel_check and cancel_check():
            raise InterruptedError("Người dùng đã hủy tiến trình.")

        app_logger.info(f"Đã tải audio thành công (VID: {upload_res.vid[:10]}...). Đang khởi tạo tác vụ STT...")
        stt_res = self.client.create_stt_task(
            audio_vid=upload_res.vid,
            audio_md5=upload_res.md5,
            duration_ms=duration_ms,
            language=source_lang,
            use_translation=False
        )

        tasks = (stt_res.get("data") or {}).get("tasks") or []
        if not tasks:
            raise CapCutTaskError(f"CapCut API không trả về tác vụ STT: {stt_res}")

        task_id = tasks[0]["id"]
        token = tasks[0]["token"]

        app_logger.info(f"Đang chờ kết quả STT từ CapCut (Task ID: {task_id})...")
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if cancel_check and cancel_check():
                raise InterruptedError("Người dùng đã hủy tiến trình.")
                
            query_res = self.client.query_stt_task(task_id, token)
            query_tasks = (query_res.get("data") or {}).get("tasks") or []
            if query_tasks:
                status = str(query_tasks[0].get("status", "")).lower()
                if status in ("success", "succeed"):
                    app_logger.success("CapCut STT đã hoàn tất nhận diện âm thanh!")
                    return self._parse_subtitles(query_res)
                elif status == "failed":
                    raise CapCutTaskError(f"Tác vụ STT thất bại: {query_res}")
            time.sleep(poll_interval)

        raise TimeoutError(f"Quá thời gian chờ STT ({timeout}s).")

    def _parse_subtitles(self, query_response: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Phân tích payload của CapCut STT thành mảng phụ đề chuẩn."""
        tasks = (query_response.get("data") or {}).get("tasks") or []
        if not tasks:
            return []
        
        raw_payload = tasks[0].get("payload", "{}")
        if isinstance(raw_payload, str):
            payload_dict = json.loads(raw_payload)
        else:
            payload_dict = raw_payload

        utterances = payload_dict.get("utterances") or []
        parsed = []
        for idx, item in enumerate(utterances):
            start_ms = item.get("start_time", 0)
            end_ms = item.get("end_time", 0)
            text = item.get("text", "").strip()
            
            start_sec = max(0.0, float(start_ms) / 1000.0)
            end_sec = max(start_sec + 0.1, float(end_ms) / 1000.0)
            
            if text:
                parsed.append({
                    "index": idx + 1,
                    "start_time": start_sec,
                    "end_time": end_sec,
                    "text": text,
                    "translation": ""
                })
        return parsed

    def _download_audio_item(self, sub_item: Dict[str, Any], audio_url: str, tts_duration_ms: float):
        if audio_url:
            local_audio = temp_manager.get_temp_file(suffix=".mp3", name=f"tts_{sub_item['index']}.mp3")
            resp = requests.get(audio_url, timeout=30)
            resp.raise_for_status()
            with open(local_audio, "wb") as f:
                f.write(resp.content)
            sub_item["audio_path"] = str(local_audio)
            sub_item["tts_duration"] = float(tts_duration_ms) / 1000.0
        else:
            sub_item["audio_path"] = None
            sub_item["tts_duration"] = 0.0

    def _execute_tts_batch(
        self,
        texts: List[str],
        voice_type: str,
        rate_str: str,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> List[Dict[str, Any]]:
        """Gửi 1 danh sách texts lên CapCut và poll kết quả."""
        create_res = self.client.create_tts_task(texts, voice=voice_type, rate=rate_str)
        tasks = (create_res.get("data") or {}).get("tasks") or []
        if not tasks:
            raise CapCutTaskError(f"Lỗi tạo task TTS: {create_res}")

        task_id = tasks[0]["id"]
        token = tasks[0]["token"]

        start_poll = time.time()
        while time.time() - start_poll < 60.0:
            if cancel_check and cancel_check():
                raise InterruptedError("Người dùng đã hủy tiến trình.")
            query_res = self.client.query_tts_task(task_id, token)
            q_tasks = (query_res.get("data") or {}).get("tasks") or []
            if q_tasks:
                status = str(q_tasks[0].get("status", "")).lower()
                if status in ("success", "succeed"):
                    payload = q_tasks[0].get("payload", "{}")
                    if isinstance(payload, str):
                        payload = json.loads(payload)
                    return payload.get("audio_subtitles") or []
                elif status == "failed":
                    raise CapCutTaskError(f"Task TTS thất bại: {query_res}")
            time.sleep(1.0)
        raise TimeoutError("Quá thời gian chờ CapCut TTS.")

    def generate_speech_for_subtitles(
        self,
        subtitles: List[Dict[str, Any]],
        voice_type: str,
        speech_rate: float = 1.0,
        batch_size: int = 15,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Sinh giọng đọc TTS tiếng Việt cho toàn bộ danh sách phụ đề.
        Tự động làm sạch ký tự và hỗ trợ fallback từng câu nếu gặp lỗi TTSInvalidText.
        """
        if not subtitles:
            return []

        # Khởi tạo mặc định cho tất cả câu
        for sub in subtitles:
            if "audio_path" not in sub:
                sub["audio_path"] = None
            if "tts_duration" not in sub:
                sub["tts_duration"] = 0.0

        rate_str = f"{speech_rate:.2f}"
        app_logger.info(f"Bắt đầu tạo TTS với giọng '{voice_type}', tốc độ {rate_str} cho {len(subtitles)} câu...")

        for i in range(0, len(subtitles), batch_size):
            if cancel_check and cancel_check():
                raise InterruptedError("Người dùng đã hủy tiến trình.")

            chunk = subtitles[i:i + batch_size]
            clean_texts = [sanitize_tts_text(c.get("translation") or c.get("text") or "") for c in chunk]
            valid_indices = [idx for idx, t in enumerate(clean_texts) if is_speakable_text(t)]

            batch_success = False
            if valid_indices:
                texts_to_send = [clean_texts[idx] for idx in valid_indices]
                try:
                    audio_items = self._execute_tts_batch(
                        texts=texts_to_send,
                        voice_type=voice_type,
                        rate_str=rate_str,
                        cancel_check=cancel_check
                    )
                    for chunk_pos, audio_info in zip(valid_indices, audio_items):
                        self._download_audio_item(
                            sub_item=chunk[chunk_pos],
                            audio_url=audio_info.get("speech_url"),
                            tts_duration_ms=audio_info.get("duration", 0)
                        )
                    batch_success = True
                except Exception as batch_err:
                    app_logger.warning(
                        f"Batch TTS {i+1}-{min(i+batch_size, len(subtitles))} báo lỗi ({batch_err}). "
                        f"Tự động chuyển sang xử lý từng câu để giữ tối đa giọng đọc..."
                    )

            # Fallback: Nếu batch thất bại (ví dụ 1 câu chứa từ cấm), xử lý từng câu một
            if not batch_success and valid_indices:
                for chunk_pos in valid_indices:
                    sub_item = chunk[chunk_pos]
                    clean_t = clean_texts[chunk_pos]
                    try:
                        single_items = self._execute_tts_batch(
                            texts=[clean_t],
                            voice_type=voice_type,
                            rate_str=rate_str,
                            cancel_check=cancel_check
                        )
                        if single_items:
                            self._download_audio_item(
                                sub_item=sub_item,
                                audio_url=single_items[0].get("speech_url"),
                                tts_duration_ms=single_items[0].get("duration", 0)
                            )
                    except Exception as single_err:
                        app_logger.warning(
                            f"Bỏ qua câu [{sub_item['index']}] do không thể tạo TTS: '{clean_t[:30]}...' ({single_err})"
                        )

            app_logger.info(f"Đã xử lý TTS {min(i + batch_size, len(subtitles))}/{len(subtitles)} câu.")

        return subtitles

capcut_service = CapCutService()
