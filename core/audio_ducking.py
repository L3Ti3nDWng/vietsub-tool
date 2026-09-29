import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
import numpy as np

from utils.logger import app_logger
from utils.temp_manager import temp_manager

SAMPLE_RATE = 44100
CHANNELS = 2
LOCAL_BIN_DIR = Path(__file__).parent.parent / "bin"

def get_ffmpeg_binary() -> str:
    exe = LOCAL_BIN_DIR / "ffmpeg.exe"
    if exe.exists():
        return str(exe)
    return "ffmpeg"

def decode_audio_to_numpy(audio_path: Path, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """
    Giải mã bất kỳ file audio nào sang mảng numpy float32 [-1.0, 1.0] stereo bằng ffmpeg.
    """
    cmd = [
        get_ffmpeg_binary(), "-v", "error", "-y",
        "-i", str(audio_path),
        "-f", "f32le",
        "-ac", str(CHANNELS),
        "-ar", str(sample_rate),
        "-"
    ]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        raw_data, err = proc.communicate()
        if proc.returncode != 0:
            app_logger.warning(f"Lỗi giải mã audio {audio_path}: {err.decode('utf-8', errors='ignore')}")
            return np.zeros((0, CHANNELS), dtype=np.float32)
        
        arr = np.frombuffer(raw_data, dtype=np.float32)
        return arr.reshape(-1, CHANNELS)
    except Exception as e:
        app_logger.error(f"Ngoại lệ khi giải mã audio: {e}")
        return np.zeros((0, CHANNELS), dtype=np.float32)

class AudioDuckingMixer:
    """
    Bộ trộn âm thanh tự động (Auto Audio Ducking):
    - Tự động hạ âm lượng audio gốc xuống mức chỉ định (15-20%) khi giọng đọc TTS phát biểu.
    - Chuyển tiếp âm lượng mượt mà (Fade In/Out) để tránh tiếng bụp hoặc giật cục.
    - Trộn TTS và audio gốc thành file audio hoàn chỉnh với chuẩn AAC 192k.
    """

    @staticmethod
    def mix_audio(
        original_audio_path: Optional[Path],
        subtitles: List[Dict[str, Any]],
        total_duration: float,
        ducking_volume: float = 0.18,
        tts_volume: float = 1.0,
        original_volume: float = 1.0,
        output_path: Optional[Path] = None
    ) -> Path:
        """
        Trộn audio gốc với toàn bộ các đoạn voiceover TTS theo mốc thời gian và ducking.
        """
        if output_path is None:
            output_path = temp_manager.get_temp_file(suffix=".aac", name="final_mixed_audio.aac")

        total_samples = max(int(total_duration * SAMPLE_RATE), 1000)

        # 1. Đọc audio gốc
        orig_data = None
        if original_audio_path and original_audio_path.exists():
            orig_data = decode_audio_to_numpy(original_audio_path, SAMPLE_RATE)
        
        if orig_data is None or len(orig_data) == 0:
            # Nếu video không có tiếng, tạo nền tĩnh lặng
            orig_data = np.zeros((total_samples, CHANNELS), dtype=np.float32)
        else:
            # Điều chỉnh độ dài cho khớp với total_samples
            if len(orig_data) < total_samples:
                pad_len = total_samples - len(orig_data)
                orig_data = np.pad(orig_data, ((0, pad_len), (0, 0)), mode="constant")
            elif len(orig_data) > total_samples:
                orig_data = orig_data[:total_samples]

        # Áp dụng âm lượng gốc cơ bản
        orig_data = orig_data * float(original_volume)

        # 2. Tạo đường cong Envelope Ducking cho audio gốc
        ducking_curve = np.ones((total_samples, 1), dtype=np.float32)
        tts_track = np.zeros((total_samples, CHANNELS), dtype=np.float32)

        fade_samples = int(0.15 * SAMPLE_RATE) # 150ms fade chuyển tiếp mượt

        speech_intervals = []

        for sub in subtitles:
            audio_file = sub.get("audio_path")
            if not audio_file or not Path(audio_file).exists():
                continue

            seg_data = decode_audio_to_numpy(Path(audio_file), SAMPLE_RATE)
            if len(seg_data) == 0:
                continue

            start_sec = sub["start_time"]
            start_idx = int(start_sec * SAMPLE_RATE)
            end_idx = start_idx + len(seg_data)

            if start_idx >= total_samples:
                continue

            # Đặt phân đoạn TTS vào track tổng
            actual_end = min(end_idx, total_samples)
            copy_len = actual_end - start_idx
            tts_track[start_idx:actual_end] += seg_data[:copy_len]

            speech_intervals.append((start_idx, actual_end))

        # 3. Tính toán Ducking Curve với chuyển tiếp mượt
        for s_idx, e_idx in speech_intervals:
            # Đoạn hạ âm lượng (ramp down)
            ramp_down_start = max(0, s_idx - fade_samples)
            ramp_down_len = s_idx - ramp_down_start
            if ramp_down_len > 0:
                fade_out = np.linspace(1.0, ducking_volume, ramp_down_len, dtype=np.float32).reshape(-1, 1)
                ducking_curve[ramp_down_start:s_idx] = np.minimum(ducking_curve[ramp_down_start:s_idx], fade_out)

            # Đoạn duy trì âm lượng thấp
            ducking_curve[s_idx:e_idx] = np.minimum(ducking_curve[s_idx:e_idx], ducking_volume)

            # Đoạn phục hồi âm lượng (ramp up)
            ramp_up_end = min(total_samples, e_idx + fade_samples)
            ramp_up_len = ramp_up_end - e_idx
            if ramp_up_len > 0:
                fade_in = np.linspace(ducking_volume, 1.0, ramp_up_len, dtype=np.float32).reshape(-1, 1)
                ducking_curve[e_idx:ramp_up_end] = np.minimum(ducking_curve[e_idx:ramp_up_end], fade_in)

        # 4. Trộn hai nguồn âm thanh
        ducked_orig = orig_data * ducking_curve
        scaled_tts = tts_track * float(tts_volume)
        mixed = ducked_orig + scaled_tts

        # Giới hạn biên độ âm thanh tránh rè (Soft Limiter)
        mixed = np.clip(mixed, -0.98, 0.98)

        # 5. Xuất ra file định dạng AAC qua ffmpeg
        app_logger.info(f"Đang mã hóa track âm thanh hoàn chỉnh (AAC 192kbps)...")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            get_ffmpeg_binary(), "-v", "error", "-y",
            "-f", "f32le",
            "-ar", str(SAMPLE_RATE),
            "-ac", str(CHANNELS),
            "-i", "-",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]

        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
        _, err = proc.communicate(input=mixed.astype(np.float32).tobytes())
        
        if proc.returncode != 0:
            app_logger.error(f"Lỗi khi mã hóa audio mixed: {err.decode('utf-8', errors='ignore')}")
            raise RuntimeError(f"FFmpeg audio encoding failed: {err}")

        app_logger.success(f"Đã tạo file audio hoàn chỉnh với Auto Ducking thành công!")
        return output_path
