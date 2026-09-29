import os
import re
import cv2
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable

from utils.logger import app_logger
from utils.temp_manager import temp_manager

LOCAL_BIN_DIR = Path(__file__).parent.parent / "bin"

def get_ffmpeg_binary() -> str:
    exe = LOCAL_BIN_DIR / "ffmpeg.exe"
    if exe.exists():
        return str(exe)
    return "ffmpeg"

def get_ffprobe_binary() -> str:
    exe = LOCAL_BIN_DIR / "ffprobe.exe"
    if exe.exists():
        return str(exe)
    return "ffprobe"

class VideoProcessor:
    """
    Xử lý video bằng FFmpeg và OpenCV:
    - Trích xuất thông tin video (resolution, fps, duration).
    - Trích xuất audio gốc.
    - Che phụ đề gốc bằng Gaussian blur / Black box nhiều vùng tự do.
    - Cắt khung hình (Crop video).
    - Chèn hình ảnh / Logo (Image Overlay với scale và opacity).
    - Ghép phụ đề tiếng Việt (burn ASS subtitle).
    - Ghép audio sau ducking.
    - Xuất video H.264 MP4 với quản lý tiến trình và hủy tác vụ an toàn.
    """

    @staticmethod
    def get_video_info(video_path: Path) -> Dict[str, Any]:
        """Lấy thông số kỹ thuật của video bằng OpenCV và FFprobe"""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            raise ValueError(f"Không thể mở file video: {video_path}")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = float(frame_count) / float(fps) if fps > 0 else 0.0
        cap.release()

        # Kiểm tra xem video có stream audio hay không qua ffprobe
        has_audio = False
        try:
            cmd = [
                get_ffprobe_binary(), "-v", "error",
                "-select_streams", "a:0",
                "-show_entries", "stream=codec_type",
                "-of", "csv=p=0",
                str(video_path)
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if "audio" in res.stdout.lower():
                has_audio = True
        except Exception:
            has_audio = True # Dự phòng mặc định

        return {
            "path": str(video_path),
            "width": width,
            "height": height,
            "fps": fps,
            "total_frames": frame_count,
            "duration": duration,
            "has_audio": has_audio
        }

    @staticmethod
    def extract_audio(video_path: Path, output_audio: Optional[Path] = None) -> Optional[Path]:
        """Trích xuất file audio từ video sang định dạng mp3/wav."""
        if output_audio is None:
            output_audio = temp_manager.get_temp_file(suffix=".mp3", name="extracted_audio.mp3")

        app_logger.info(f"Đang trích xuất audio từ video: {video_path.name}...")
        cmd = [
            get_ffmpeg_binary(), "-v", "error", "-y",
            "-i", str(video_path),
            "-vn",
            "-acodec", "libmp3lame",
            "-q:a", "2",
            str(output_audio)
        ]

        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            app_logger.warning("Không thể trích xuất audio hoặc video không có track tiếng.")
            return None

        app_logger.success(f"Đã trích xuất audio thành công: {output_audio.name}")
        return output_audio

    @staticmethod
    def build_video_filtergraph(
        video_width: int,
        video_height: int,
        mask_boxes: List[Dict[str, Any]],
        crop_box: Optional[Dict[str, Any]],
        overlay_info: Optional[Dict[str, Any]],
        ass_sub_path: Optional[Path],
        target_width: int = 1920,
        target_height: int = 1080
    ) -> Tuple[str, List[str]]:
        """
        Xây dựng chuỗi bộ lọc FFmpeg:
        1. Che phụ đề gốc (Blur / Blackbox nhiều vùng theo tọa độ gốc)
        2. Crop khung hình (nếu có bật)
        3. CỐ ĐỊNH TỈ LỆ 16:9 (1920x1080): Tự động scale và thêm viền đen (Letterbox/Pillarbox),
           tuyệt đối KHÔNG BỊ GIÃN (Stretch/Méo hình).
        4. Image Overlay (Logo/Watermark trên khung 16:9)
        5. Render phụ đề ASS chuẩn 16:9
        """
        filter_parts = []
        extra_inputs = []

        curr_label = "0:v"
        step_idx = 0

        # 1. Che vùng phụ đề gốc: Xử lý Blackbox trước (nhẹ và nhanh)
        black_boxes = [b for b in mask_boxes if b.get("type") == "black"]
        for b in black_boxes:
            bx = int(b.get("x", 0))
            by = int(b.get("y", 0))
            bw = int(b.get("w", 0))
            bh = int(b.get("h", 0))
            if bw > 0 and bh > 0:
                next_label = f"v_bb_{step_idx}"
                filter_parts.append(
                    f"[{curr_label}]drawbox=x={bx}:y={by}:w={bw}:h={bh}:color=black:t=fill[{next_label}]"
                )
                curr_label = next_label
                step_idx += 1

        # Xử lý Blur boxes (Gaussian/Box blur)
        blur_boxes = [b for b in mask_boxes if b.get("type") == "blur"]
        for b in blur_boxes:
            bx = int(b.get("x", 0))
            by = int(b.get("y", 0))
            bw = int(b.get("w", 0))
            bh = int(b.get("h", 0))
            if bw > 0 and bh > 0:
                base_lbl = f"v_base_{step_idx}"
                crop_lbl = f"v_crp_{step_idx}"
                blur_lbl = f"v_blr_{step_idx}"
                out_lbl = f"v_out_{step_idx}"
                
                # Cắt vùng cần làm mờ, làm mờ rồi đè lại lên video gốc
                filter_parts.append(f"[{curr_label}]split[{base_lbl}][{crop_lbl}]")
                filter_parts.append(f"[{crop_lbl}]crop={bw}:{bh}:{bx}:{by},gblur=sigma=12:steps=2[{blur_lbl}]")
                filter_parts.append(f"[{base_lbl}][{blur_lbl}]overlay={bx}:{by}[{out_lbl}]")
                
                curr_label = out_lbl
                step_idx += 1

        # 2. Xử lý Crop nếu có bật
        if crop_box and crop_box.get("enabled", False):
            cx = max(0, min(video_width - 10, int(crop_box.get("x", 0))))
            cy = max(0, min(video_height - 10, int(crop_box.get("y", 0))))
            cw = max(10, min(video_width - cx, int(crop_box.get("w", video_width))))
            ch = max(10, min(video_height - cy, int(crop_box.get("h", video_height))))
            if cw > 0 and ch > 0:
                crop_out_lbl = f"v_cropped_{step_idx}"
                filter_parts.append(f"[{curr_label}]crop={cw}:{ch}:{cx}:{cy}[{crop_out_lbl}]")
                curr_label = crop_out_lbl
                step_idx += 1

        # 3. FIX CỐ ĐỊNH TỈ LỆ 16:9 (1920x1080) - GIỮ NGUYÊN TỈ LỆ, KHÔNG BỊ STRETCH
        # force_original_aspect_ratio=decrease đảm bảo video nằm trọn trong khung 1920x1080
        # scale=trunc(iw/2)*2:trunc(ih/2)*2 đảm bảo kích thước chẵn cho H.264
        # pad=1920:1080:... đệm viền đen căn giữa chính xác
        fix_16_9_lbl = f"v_16_9_{step_idx}"
        filter_parts.append(
            f"[{curr_label}]scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
            f"scale=trunc(iw/2)*2:trunc(ih/2)*2,"
            f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1[{fix_16_9_lbl}]"
        )
        curr_label = fix_16_9_lbl
        step_idx += 1

        # 4. Xử lý Image Overlay nếu có (trên khung 16:9)
        if overlay_info and overlay_info.get("enabled", False) and overlay_info.get("path"):
            img_path = Path(overlay_info["path"])
            if img_path.exists():
                extra_inputs.extend(["-i", str(img_path)])
                img_input_idx = 1 # input thứ hai
                
                ox = int(overlay_info.get("x", 20))
                oy = int(overlay_info.get("y", 20))
                scale = float(overlay_info.get("scale", 1.0))
                opacity = float(overlay_info.get("opacity", 1.0))

                img_proc_lbl = f"v_img_{step_idx}"
                ovl_out_lbl = f"v_overlaid_{step_idx}"

                # Scale và chỉnh alpha
                filter_parts.append(
                    f"[{img_input_idx}:v]format=rgba,scale=iw*{scale:.3f}:-1,colorchannelmixer=aa={opacity:.3f}[{img_proc_lbl}]"
                )
                filter_parts.append(
                    f"[{curr_label}][{img_proc_lbl}]overlay={ox}:{oy}[{ovl_out_lbl}]"
                )
                curr_label = ovl_out_lbl
                step_idx += 1

        # 5. Gắn phụ đề ASS (libass) trên khung 16:9
        if ass_sub_path and ass_sub_path.exists() and ass_sub_path.stat().st_size > 0:
            sub_str = str(ass_sub_path.resolve()).replace("\\", "/").replace(":", "\\:")
            sub_out_lbl = f"v_sub_{step_idx}"
            filter_parts.append(f"[{curr_label}]subtitles='{sub_str}'[{sub_out_lbl}]")
            curr_label = sub_out_lbl
            step_idx += 1

        # Nối output cuối cùng với [v_final]
        full_filter = "; ".join(filter_parts)
        if filter_parts[-1].endswith(f"[{curr_label}]"):
            last_bracket = full_filter.rfind(f"[{curr_label}]")
            full_filter = full_filter[:last_bracket] + "[v_final]"
        else:
            full_filter += f"; [{curr_label}]null[v_final]"

        return full_filter, extra_inputs

    @staticmethod
    def render_final_video(
        video_path: Path,
        mixed_audio_path: Optional[Path],
        ass_sub_path: Optional[Path],
        output_path: Path,
        video_info: Dict[str, Any],
        mask_boxes: List[Dict[str, Any]],
        crop_box: Optional[Dict[str, Any]],
        overlay_info: Optional[Dict[str, Any]],
        progress_callback: Optional[Callable[[float, str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
        export_settings: Optional[Dict[str, Any]] = None
    ) -> Path:
        """
        Render toàn bộ video hoàn chỉnh bằng FFmpeg.
        Hỗ trợ cấu hình tùy biến: Bitrate, Độ phân giải, FPS, Codec (CapCut Style),
        đọc log tiến độ real-time và hủy ngang an toàn.
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            if output_path.exists():
                output_path.unlink()
        except Exception as e:
            app_logger.warning(f"Không thể xóa file output cũ trước khi render: {e}")

        total_duration = video_info.get("duration", 10.0)

        # Lấy thông số độ phân giải đích từ export_settings
        exp = export_settings or {}
        target_w = exp.get("target_width", 1920)
        target_h = exp.get("target_height", 1080)

        video_w = video_info["width"]
        video_h = video_info["height"]
        
        filter_str, extra_inputs = VideoProcessor.build_video_filtergraph(
            video_width=video_w,
            video_height=video_h,
            mask_boxes=mask_boxes,
            crop_box=crop_box,
            overlay_info=overlay_info,
            ass_sub_path=ass_sub_path,
            target_width=target_w,
            target_height=target_h
        )

        cmd = [get_ffmpeg_binary(), "-v", "info", "-y", "-i", str(video_path)]
        if extra_inputs:
            cmd.extend(extra_inputs)

        # Thêm file audio đã ducking nếu có và có dữ liệu
        audio_input_idx = None
        if mixed_audio_path and mixed_audio_path.exists() and mixed_audio_path.stat().st_size > 100:
            cmd.extend(["-i", str(mixed_audio_path)])
            audio_input_idx = 1 + (len(extra_inputs) // 2)

        # Xây dựng tham số map và filter
        if filter_str:
            cmd.extend(["-filter_complex", filter_str, "-map", "[v_final]"])
        else:
            cmd.extend(["-map", "0:v:0"])

        if audio_input_idx is not None:
            cmd.extend(["-map", f"{audio_input_idx}:a:0?"])
        elif video_info.get("has_audio"):
            cmd.extend(["-map", "0:a:0?"])

        # 1. Bộ mã hóa Video (Codec H.264 / H.265)
        codec_name = exp.get("codec", "H.264")
        if "265" in codec_name or "hevc" in codec_name.lower():
            cmd.extend(["-c:v", "libx265", "-tag:v", "hvc1"])
        else:
            cmd.extend(["-c:v", "libx264", "-pix_fmt", "yuv420p"])

        cmd.extend(["-preset", "faster"])

        # 2. Cấu hình Bitrate
        bitrate_kbps = exp.get("bitrate_kbps")
        if bitrate_kbps and int(bitrate_kbps) > 0:
            b_val = int(bitrate_kbps)
            cmd.extend([
                "-b:v", f"{b_val}k",
                "-maxrate", f"{int(b_val * 1.3)}k",
                "-bufsize", f"{int(b_val * 2)}k"
            ])
        else:
            cmd.extend(["-crf", "20"])

        # 3. Cấu hình FPS (Tốc độ khung hình)
        fps_opt = exp.get("fps")
        if fps_opt and str(fps_opt).lower() not in ("original", "gốc", "none"):
            try:
                fps_num = float(str(fps_opt).replace("fps", "").strip())
                if fps_num > 0:
                    cmd.extend(["-r", str(int(fps_num))])
            except Exception:
                pass

        # 4. Audio & Container
        audio_bitrate = exp.get("audio_bitrate", "192k")
        cmd.extend([
            "-c:a", "aac",
            "-b:a", str(audio_bitrate),
            "-shortest",
            "-movflags", "+faststart",
            str(output_path)
        ])

        app_logger.info(f"Đang render video: {output_path.name}...")
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            encoding="utf-8",
            errors="replace"
        )

        time_pattern = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")
        stderr_lines = []

        try:
            while True:
                if cancel_check and cancel_check():
                    proc.kill()
                    app_logger.warning("Đã hủy quá trình render video theo yêu cầu.")
                    raise InterruptedError("Người dùng đã hủy xuất video.")

                line = proc.stderr.readline()
                if not line and proc.poll() is not None:
                    break

                if line:
                    stderr_lines.append(line)
                    if len(stderr_lines) > 50:
                        stderr_lines.pop(0)

                if "time=" in line:
                    m = time_pattern.search(line)
                    if m:
                        hours, mins, secs = int(m.group(1)), int(m.group(2)), float(m.group(3))
                        current_sec = hours * 3600 + mins * 60 + secs
                        progress = min(1.0, current_sec / total_duration) if total_duration > 0 else 0.5
                        if progress_callback:
                            progress_callback(progress, f"Đang render: {int(progress * 100)}% ({current_sec:.1f}s / {total_duration:.1f}s)")

            retcode = proc.wait()
            if retcode != 0:
                err_summary = "".join(stderr_lines).strip()
                app_logger.error(f"FFmpeg render lỗi (code {retcode}). Chi tiết từ FFmpeg:\n{err_summary}")
                raise RuntimeError(f"FFmpeg xuất video thất bại (Return code: {retcode}).")

            app_logger.success(f"Xuất video hoàn tất thành công: {output_path}")
            if progress_callback:
                progress_callback(1.0, "Hoàn tất xuất video!")
            return output_path

        except Exception as e:
            if proc.poll() is None:
                proc.kill()
            raise e

