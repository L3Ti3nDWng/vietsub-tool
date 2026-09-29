import re
from pathlib import Path
from typing import List, Dict, Any, Optional

def hex_to_ass_color(hex_color: str, alpha: int = 0) -> str:
    """
    Chuyển đổi mã màu hex (#RRGGBB) sang định dạng màu của ASS (&HAABBGGRR).
    Lưu ý: ASS dùng thứ tự Blue-Green-Red (BGR), alpha 00 là hoàn toàn hiển thị.
    """
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join([c * 2 for c in hex_color])
    if len(hex_color) != 6:
        hex_color = "FFFFFF"
    
    r = hex_color[0:2]
    g = hex_color[2:4]
    b = hex_color[4:6]
    a = f"{alpha:02X}"
    return f"&H{a}{b}{g}{r}&"

def sec_to_ass_time(seconds: float) -> str:
    """Chuyển đổi giây sang định dạng thời gian ASS: H:MM:SS.cs (centiseconds)"""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs >= 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"

def sec_to_srt_time(seconds: float) -> str:
    """Chuyển đổi giây sang định dạng thời gian SRT: HH:MM:SS,mmm"""
    if seconds < 0:
        seconds = 0.0
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int(round((seconds - int(seconds)) * 1000))
    if ms >= 1000:
        ms = 999
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

class SubtitleGenerator:
    """
    Tạo file phụ đề ASS và SRT chuyên nghiệp, hỗ trợ đầy đủ font hệ thống,
    màu sắc, viền, vị trí tự do và các hiệu ứng động (Fade, Slide, Typewriter, Zoom).
    """

    @staticmethod
    def build_ass(
        subtitles: List[Dict[str, Any]],
        video_width: int,
        video_height: int,
        style_config: Dict[str, Any],
        output_file: Path
    ) -> Path:
        """
        Tạo file ASS chuẩn với Style và Effect theo cấu hình người dùng.
        """
        font_family = style_config.get("font_family", "Arial")
        raw_font_size = float(style_config.get("font_size", 5.5))
        # Nếu là giá trị px cũ (>= 18), tự động chuẩn hóa sang 5.5%
        if raw_font_size >= 18.0:
            font_size_percent = 5.5
        else:
            font_size_percent = max(1.5, min(25.0, raw_font_size))

        # TÍNH CỠ CHỮ THEO % CHIỀU CAO THỰC TẾ CỦA VIDEO
        # Ví dụ: Video 1080p với 5.5% -> font_size = 59px. Video 720p -> 40px. Video 4K -> 119px.
        ass_font_size = max(12, int(round(video_height * (font_size_percent / 100.0))))

        text_color_hex = style_config.get("text_color", "#FFE600")
        border_color_hex = style_config.get("border_color", "#000000")
        raw_border = float(style_config.get("border_width", 3))
        # Viền chữ co giãn hài hòa theo cỡ chữ
        border_width = max(1.0, round(ass_font_size * 0.075, 1)) if raw_border <= 0 else max(1.0, round(raw_border * (ass_font_size / 30.0), 1))
        
        # Tọa độ chuẩn hóa (0.0 -> 1.0) chuyển sang pixel thực tế của video
        pos_x_ratio = float(style_config.get("sub_pos_x", 0.5))
        pos_y_ratio = float(style_config.get("sub_pos_y", 0.85))
        
        target_x = int(video_width * pos_x_ratio)
        target_y = int(video_height * pos_y_ratio)

        primary_color_ass = hex_to_ass_color(text_color_hex)
        outline_color_ass = hex_to_ass_color(border_color_hex)
        effect_name = style_config.get("effect", "None")

        # Alignment 2 = bottom-center, 5 = middle-center
        alignment = 2

        ass_header = f"""[Script Info]
Title: Douyin Translator Pro Subtitles
ScriptType: v4.00+
WrapStyle: 2
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: {video_width}
PlayResY: {video_height}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font_family},{ass_font_size},{primary_color_ass},&H000000FF&,{outline_color_ass},&H80000000&,-1,0,0,0,100,100,0,0,1,{border_width},1,{alignment},20,20,20,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        events = []
        for item in subtitles:
            text = item.get("translation") or item.get("text") or ""
            # Đảm bảo chỉ 1 dòng duy nhất theo yêu cầu
            text = re.sub(r"[\r\n]+", " ", text).strip()
            if not text:
                continue

            start_str = sec_to_ass_time(item["start_time"])
            end_str = sec_to_ass_time(item["end_time"])

            # Xử lý hiệu ứng phụ đề
            text_with_effect = SubtitleGenerator._apply_effect(
                text=text,
                effect=effect_name,
                x=target_x,
                y=target_y,
                duration_sec=item["end_time"] - item["start_time"],
                font_size=ass_font_size
            )

            line = f"Dialogue: 0,{start_str},{end_str},Default,,0,0,0,,{text_with_effect}"
            events.append(line)

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(ass_header)
            f.write("\n".join(events))
            f.write("\n")

        return output_file

    @staticmethod
    def _apply_effect(text: str, effect: str, x: int, y: int, duration_sec: float, font_size: int = 50) -> str:
        """Gắn thẻ tag hiệu ứng ASS vào câu phụ đề."""
        pos_tag = f"\\pos({x},{y})"
        shift_y = int(round(font_size * 0.6))
        
        if effect == "Fade In/Out":
            # Fade in 180ms, Fade out 180ms
            return f"{{\\an2{pos_tag}\\fad(180,180)}}{text}"

        elif effect == "Slide Up":
            # Trượt từ dưới lên
            start_y = y + shift_y
            return f"{{\\an2\\move({x},{start_y},{x},{y},0,220)}}{text}"

        elif effect == "Slide Down":
            # Trượt từ trên xuống
            start_y = max(0, y - shift_y)
            return f"{{\\an2\\move({x},{start_y},{x},{y},0,220)}}{text}"

        elif effect == "Zoom In":
            # Phóng to từ 60% lên 100% trong 200ms
            return f"{{\\an2{pos_tag}\\fscx60\\fscy60\\t(0,200,\\fscx100\\fscy100)}}{text}"

        elif effect == "Typewriter":
            # Hiệu ứng gõ chữ tuần tự từng từ
            words = text.split(" ")
            if len(words) <= 1:
                return f"{{\\an2{pos_tag}}}{text}"
            
            # Tính thời gian xuất hiện cho mỗi từ (đơn vị centiseconds)
            total_cs = max(10, int(duration_sec * 80)) # dành 80% thời lượng cho gõ chữ
            per_word_cs = max(8, total_cs // len(words))
            
            karaoke_text = "".join([f"{{\\k{per_word_cs}}}{w} " for w in words]).strip()
            return f"{{\\an2{pos_tag}}}{karaoke_text}"

        else:
            # None: hiển thị tĩnh tại tọa độ đã chọn
            return f"{{\\an2{pos_tag}}}{text}"

    @staticmethod
    def build_srt(subtitles: List[Dict[str, Any]], output_file: Path) -> Path:
        """Xuất file SRT truyền thống cho phụ đề."""
        lines = []
        count = 1
        for item in subtitles:
            text = item.get("translation") or item.get("text") or ""
            text = re.sub(r"[\r\n]+", " ", text).strip()
            if not text:
                continue

            start_str = sec_to_srt_time(item["start_time"])
            end_str = sec_to_srt_time(item["end_time"])

            lines.append(f"{count}")
            lines.append(f"{start_str} --> {end_str}")
            lines.append(text)
            lines.append("")
            count += 1

        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return output_file
