import tkinter as tk
import tkinter.font as tkfont
from typing import List

POPULAR_FONTS = [
    "Arial",
    "Segoe UI",
    "Tahoma",
    "Verdana",
    "Calibri",
    "Times New Roman",
    "Roboto",
    "Montserrat",
    "Be Vietnam Pro",
    "Open Sans",
    "Inter",
    "Nunito"
]

def get_system_fonts() -> List[str]:
    """
    Lấy danh sách font hệ thống từ tkinter.font.families(),
    lọc bỏ các font hệ thống bắt đầu bằng '@' (font dọc),
    sắp xếp ưu tiên các font phổ biến hỗ trợ tiếng Việt lên đầu.
    """
    try:
        root = tk._default_root
        created_temp = False
        if root is None:
            root = tk.Tk()
            root.withdraw()
            created_temp = True
            
        families = list(tkfont.families(root))
        if created_temp:
            root.destroy()
            
        # Lọc bỏ font dọc (@) và loại bỏ trùng lặp
        cleaned = sorted(list(set(f for f in families if not f.startswith("@"))))
        
        # Đưa các font phổ biến lên đầu
        prioritized = [f for f in POPULAR_FONTS if f in cleaned]
        others = [f for f in cleaned if f not in prioritized]
        
        result = prioritized + others
        return result if result else ["Arial", "Segoe UI", "Tahoma"]
    except Exception as e:
        return ["Arial", "Segoe UI", "Tahoma"]
