# 🎬 Douyin Translator Pro

**Douyin Translator Pro** là phần mềm desktop chuyên nghiệp viết bằng Python 3.10+, chuyên dùng để tự động hóa quy trình dịch thuật, lồng tiếng (TTS) và tạo phụ đề tiếng Việt chuẩn điện ảnh cho các video Douyin (TikTok Trung Quốc) hoặc bất kỳ video ngắn nào.

---

## ✨ Tính Năng Nổi Bật

### 1. Nhận diện giọng nói & Trích xuất phụ đề gốc (STT)
- Tích hợp trực tiếp **CapCut API** để trích xuất âm thanh và nhận diện văn bản tiếng Trung với độ chính xác cao kèm timestamp chi tiết theo từng mili-giây.

### 2. Dịch thuật thông minh qua Playwright + ChatGPT Web
- Tự động hóa trình duyệt **Chromium** (Playwright) mở ChatGPT Web, gửi prompt dịch thuật văn phong video ngắn tự nhiên, cuốn hút.
- Giữ phiên đăng nhập ổn định bằng **Persistent Context**.
- Tích hợp bộ máy dự phòng tốc độ cao bằng **Google Translate API** hoàn toàn miễn phí.

### 3. Lồng tiếng tự động (TTS tiếng Việt)
- Hơn **24 giọng đọc CapCut tiếng Việt** thịnh hành (cô gái hoạt bát, chàng trai ấm áp, nữ MC, nam MC, giọng kể chuyện...).
- Tùy chỉnh tốc độ đọc (0.6x - 1.8x) và âm lượng lồng tiếng.
- Hỗ trợ nghe thử giọng đọc trực tiếp trên giao diện.

### 4. Tự động hạ nhạc nền (Auto Audio Ducking)
- Tự động nhận diện khi người thuyết minh đang nói để giảm âm lượng nhạc nền video gốc xuống mức 15% - 20%.
- Tự động phục hồi âm lượng gốc 100% khi im lặng, chuyển tiếp âm thanh mượt mà (Fade In/Out) chuẩn phòng thu.

### 5. Che phụ đề tiếng Trung gốc (Vẽ tự do nhiều vùng)
- Hỗ trợ 2 chế độ:
  - **Làm mờ (Gaussian Blur)** nhiều vùng tự do.
  - **Hộp đen (Black Box)** nhiều vùng tự do.
- Cho phép người dùng vẽ trực tiếp các hình chữ nhật lên khung xem trước video.

### 6. Đồ họa phụ đề 1 dòng & Hiệu ứng chuyển động
- Hiển thị phụ đề tiếng Việt chuẩn 1 dòng, không bị tràn hay che khuất khung hình.
- **Autogrid & Hút trục thông minh (Smart Magnetic Snapping)**:
  - Tự động hút (snap) phụ đề vào **Trục dọc chính giữa (50%)**, **Trục ngang trung tâm (50%)**, và **Vị trí phụ đề tiêu chuẩn TikTok/Douyin (85%, 80%, 15%)**.
  - Hiển thị đường gióng nét đứt phát sáng và huy hiệu tọa độ khi phụ đề được hút vào các trục.
  - Tùy chọn bật/tắt hiển thị lưới bố cục **Rule of Thirds 3x3** kèm tâm chữ thập `(+)` để căn chỉnh góc máy và bố cục.
- Kéo thả tự do vị trí phụ đề ngay trên video hoặc nhập tọa độ chính xác.
- Chọn toàn bộ font chữ có sẵn trong hệ thống máy tính (`Arial`, `Segoe UI`, `Tahoma`, `Roboto`, `Montserrat`...).
- Tùy chỉnh màu chữ chính, màu viền chữ, độ dày viền.
- Đầy đủ các hiệu ứng động:
  - **Fade In/Out** (Mờ dần)
  - **Typewriter** (Đánh máy từng chữ)
  - **Slide Up / Slide Down** (Trượt lên / trượt xuống)
  - **Zoom In** (Phóng to xuất hiện)
  - **None** (Tĩnh)
- **Hệ thống Preset**: Lưu và tải sẵn các mẫu style đẹp mắt (TikTok Viral, Douyin Modern, Neon Cyan, Typewriter, Cinematic).

### 7. Cắt khung hình (Crop) & Chèn Watermark/Logo
- Hỗ trợ kéo chuột chọn vùng Crop trực tiếp trên màn hình video.
- Chèn Logo/Watermark với tùy chỉnh vị trí, tỷ lệ thu phóng (Scale) và độ mờ đục (Opacity).

### 8. Tự động dọn dẹp & Quản lý tiến trình an toàn
- Toàn bộ file âm thanh tạm, file phụ đề trung gian đều được tự động dọn dẹp sạch sẽ sau khi xuất xong hoặc khi đóng phần mềm.
- Xử lý video dài bằng FFmpeg streaming, không chiếm dụng và không tràn bộ nhớ RAM.
- Nút **Hủy bỏ (Cancel)** tức thời cho phép dừng giữa chừng mà không treo ứng dụng.

---

## 📁 Cấu Trúc Dự Án

```
vietsub-tool/
├── main.py                     # Điểm khởi chạy ứng dụng chính
├── requirements.txt            # Danh sách thư viện phụ thuộc
├── README.md                   # Tài liệu hướng dẫn sử dụng
├── Voice.json                  # Danh mục 129 giọng đọc CapCut
├── config.json                 # Cấu hình lưu trữ gần nhất của người dùng
├── presets.json                # Danh sách Preset phong cách phụ đề
│
├── core/                       # Các module xử lý logic nền tảng
│   ├── capcut_service.py       # Tích hợp CapCut STT & TTS với retry tự động
│   ├── translator.py           # Dịch thuật ChatGPT Web (Playwright) + Google fallback
│   ├── audio_ducking.py        # Xử lý Auto Audio Ducking và trộn âm thanh
│   ├── subtitle_generator.py   # Tạo file phụ đề ASS / SRT kèm hiệu ứng động
│   ├── video_processor.py      # Bộ lọc FFmpeg: blur, blackbox, crop, watermark, render H.264
│   └── pipeline.py             # Điều phối 8 bước xử lý video đa luồng với Progress bar
│
├── ui/                         # Giao diện người dùng CustomTkinter
│   ├── app.py                  # Cửa sổ chính kết nối các Tab và dữ liệu
│   ├── video_preview.py        # Khung phát video OpenCV + tương tác kéo thả Canvas
│   ├── tab_video.py            # Tab 1: Chọn video, phát thử, vẽ che mờ & crop
│   ├── tab_subtitles.py        # Tab 2: Cài đặt font chữ, màu sắc, hiệu ứng & preset
│   ├── tab_tts.py              # Tab 3: Cài đặt giọng đọc CapCut, tốc độ, audio ducking
│   ├── tab_overlay.py          # Tab 4: Cài đặt chèn logo / watermark
│   ├── tab_process.py          # Tab 5: Chọn bộ máy dịch, xuất file, progress & log
│   └── subtitle_dialog.py      # Bảng chỉnh sửa phụ đề chi tiết trước khi render
│
└── utils/                      # Các tiện ích bổ trợ
    ├── config_manager.py       # Quản lý file cấu hình & Preset
    ├── logger.py               # Hệ thống ghi nhật ký thread-safe ra UI
    ├── system_fonts.py         # Quét danh sách font chữ hệ thống máy tính
    └── temp_manager.py         # Quản lý và tự động dọn dẹp file tạm
```

---

## ⚙️ Khởi Chạy Nhanh (Khuyến Nghị)

### Cách 1: Chạy bằng file `run.bat` (1-Click)
- Chỉ cần nhấp đúp chuột vào file **[`run.bat`](file:///d:/Study/vietsub-tool/run.bat)** trong thư mục dự án.
- Ứng dụng sẽ tự động kích hoạt môi trường ảo `venv` và sử dụng `FFmpeg` cục bộ trong thư mục `bin/` để hoạt động ngay lập tức mà không cần cài đặt bất kỳ thứ gì vào hệ thống máy tính.

### Cách 2: Khởi chạy thủ công qua Terminal
1. Kích hoạt môi trường ảo `venv`:
   ```bash
   .\venv\Scripts\activate
   ```
2. Chạy ứng dụng:
   ```bash
   python main.py
   ```

> [!NOTE]
> Dự án đã tích hợp sẵn **FFmpeg cục bộ** trong thư mục [`bin/`](file:///d:/Study/vietsub-tool/bin/) và tự động nhận diện khi chạy, **hoàn toàn không can thiệp hay phụ thuộc vào biến môi trường hệ thống (PATH)**.

---

## 🖥️ Bố Cục Giao Diện Chuẩn CapCut Studio

Ứng dụng được thiết kế theo mô hình **3 Cột Chuyên Nghiệp** chuẩn của CapCut Desktop:

```
+-----------------------------------------------------------------------------------------------------------------------------+
|                                        HEADER: 🎬 DOUYIN TRANSLATOR PRO (CAPCUT STYLE)                                      |
+------------------------------------+---------------------------------------------------+------------------------------------+
|  CỘT TRÁI (LEFT PANEL: ~290px)     |      KHU VỰC Ở GIỮA (CENTER: PREVIEW & PLAYER)    |    CỘT BÊN PHẢI (RIGHT: SETTINGS)  |
|                                    |                                                   |                                    |
| 1. THUỘC TÍNH VIDEO                | [TOOLBAR TRÊN PREVIEW]                            | [TABS CÀI ĐẶT THÔNG SỐ]            |
|    - [📂 Chọn Video Local]         |  [✥ Kéo Sub] [🟦 Blur] [⬛ Blackbox] [✂ Crop]      |  (Segmented Tab Selection):        |
|    - Tên file, Độ phân giải        |  [👁 Xem: Đã Crop / Gốc] [🔄 Hủy Crop]             |  • 💬 Phụ đề & Style (Font, màu..) |
|    - Tốc độ khung FPS              |                                                   |  • 🎙 Lồng tiếng & Ducking (CapCut)|
|    - Thời lượng, Track Audio       | ------------------------------------------------- |  • 🖼 Logo & Watermark             |
|                                    | [CANVAS PREVIEW Ở TRUNG TÂM]                      |  • 🌐 Dịch thuật (ChatGPT / Google)|
| 2. TRẠNG THÁI CROP                 |  (Tự động CROP REAL-TIME ngay khi kéo crop!)      |  • 📋 Logs Real-time               |
|    - Đang bật: W x H (Tỷ lệ)       |  (Kéo thả phụ đề trực quan)                       |                                    |
|    - [✂ Vẽ Crop] [Hủy Crop]        |                                                   | [SCROLLABLE CONTENT FOR TAB]       |
|                                    | ------------------------------------------------- |                                    |
| 3. VÙNG CHE (BLUR & BLACKBOX)      | [THANH ĐIỀU KHIỂN VIDEO DƯỚI PREVIEW]             | ---------------------------------- |
|    - Danh sách các hộp đã vẽ       |  [◀ -1s] [▶ Phát / ⏸ Dừng] [+1s ▶]                 | [DƯỚI CÙNG CỘT BÊN PHẢI]:          |
|      #1: BLUR 200x60 [✕]           |  [====== Slider thời gian ======]                 |  - Nơi lưu file xuất (.mp4)        |
|      #2: BLACK 180x40 [✕]          |  [00:15 / 01:23]                                  |  - [X] Mở video khi xong           |
|    - [Xóa hết]                     |                                                   |  - Progress Bar + Trạng thái       |
|                                    |                                                   |  - [🚀 BẮT ĐẦU XỬ LÝ & XUẤT VIDEO] |
| 4. PHỤ ĐỀ & LỜI THOẠI              |                                                   |  - [🛑 HỦY BỎ]                     |
|    - Thống kê số câu thoại         |                                                   |                                    |
|    - [📝 Chỉnh sửa phụ đề chi tiết]|                                                   |                                    |
+------------------------------------+---------------------------------------------------+------------------------------------+
```

---

## 🚀 Hướng Dẫn Sử Dụng Theo Layout CapCut

1. **Cột bên trái (Thuộc tính & Media)**:
   - Nhấn **📂 Chọn Video Local** để tải video lên.
   - Quan sát ngay các thuộc tính kỹ thuật của video (Độ phân giải, FPS, thời lượng, âm thanh).
   - Quản lý danh sách các vùng che mờ (xóa từng vùng bằng nút `✕` hoặc xóa tất cả).
   - Bấm **📝 Chỉnh sửa phụ đề chi tiết** nếu muốn xem/sửa thủ công trước khi render.

2. **Khu vực ở giữa (Preview & Crop Real-time)**:
   - Thanh công cụ trên Preview:
     - Chọn `✂ Vẽ Crop`: Kéo chuột trên video để chọn vùng muốn cắt. **Sau khi thả chuột, Preview sẽ tự động CROP luôn khung hình phóng to vừa vặn**, đúng như bạn mong muốn!
     - Nút `👁 Xem: Đã Crop` / `👁 Xem: Gốc`: Cho phép bạn chuyển đổi nhanh giữa khung hình đã crop và video toàn cảnh gốc bất kỳ lúc nào.
     - Chọn `✥ Kéo phụ đề`: Kéo thả phụ đề mẫu đến vị trí mong muốn ngay trong khung hình đã crop.
     - Chọn `🟦 Vẽ Blur` hoặc `⬛ Vẽ Blackbox`: Giữ chuột và vẽ lên các vùng phụ đề tiếng Trung gốc cần che.
   - Thanh Player bên dưới: Nhấn **▶ Phát** để xem thử chuyển động video và phụ đề.

3. **Cột bên phải (Thông số cài đặt & Xuất video)**:
   - Chọn các Tab thông số bên trên:
     - **💬 Phụ đề**: Chọn font chữ hệ thống, cỡ chữ, màu sắc, màu viền, độ dày viền, hiệu ứng động (`Fade In/Out`, `Typewriter`, `Slide Up`, `Zoom In`...) hoặc áp dụng Preset có sẵn.
     - **🎙 Lồng tiếng**: Chọn giọng đọc CapCut tiếng Việt (có nút nghe thử giọng), tốc độ nói và mức hạ nhạc nền (Auto Audio Ducking).
     - **🖼 Logo**: Bật chèn ảnh watermark, logo thương hiệu, scale và opacity.
     - **🌐 Dịch**: Chọn ChatGPT Web (Playwright) hoặc Google Translate.
     - **📋 Log**: Theo dõi nhật ký log thời gian thực.
   - **Dưới cùng cột bên phải**:
     - Chọn nơi lưu file video xuất ra (`.mp4`).
     - Bấm **🚀 BẮT ĐẦU XỬ LÝ & XUẤT** để chạy toàn bộ tiến trình tự động.
     - Có thể bấm **🛑 HỦY** nếu muốn dừng lại giữa chừng.

---

## 🛠️ Xử Lý Sự Cố Thường Gặp

- **Không tìm thấy FFmpeg**: Hãy cài đặt FFmpeg (từ [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) hoặc qua `winget install Gyan.FFmpeg`) và đảm bảo mở Terminal mới có nhận diện lệnh `ffmpeg`.
- **ChatGPT yêu cầu xác minh Cloudflare hoặc đăng nhập**: Tại Tab 5, bỏ chọn *"Chạy ẩn ChatGPT (Headless)"*, khi khởi động Playwright sẽ hiện cửa sổ trình duyệt Chromium để bạn đăng nhập tài khoản ChatGPT của mình. Các lần sau phiên đăng nhập sẽ được lưu trong thư mục `data/browser_profile/`.
- **Dịch nhanh không cần trình duyệt**: Hãy chuyển lựa chọn Bộ máy dịch thuật sang *"Google Translate (Dự phòng nhanh / Miễn phí)"*.
- **Giọng đọc CapCut không phát âm**: Đảm bảo kết nối mạng Internet ổn định để ứng dụng kết nối tới CapCut Cloud API.
