import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable
import requests

from utils.logger import app_logger

DEFAULT_PROMPT_TEMPLATE = (
    "Bạn là một chuyên gia biên dịch nội dung video ngắn Douyin/TikTok sang tiếng Việt.\n"
    "Hãy dịch các câu sau sang tiếng Việt tự nhiên, cuốn hút, súc tích và khớp với nhịp điệu nói của video.\n"
    "YÊU CẦU BẮT BUỘC:\n"
    "1. Giữ nguyên số thứ tự [ID] ở đầu mỗi dòng.\n"
    "2. Mỗi câu chỉ nằm trên ĐÚNG 1 DÒNG.\n"
    "3. Chỉ trả về kết quả dịch kèm [ID], không thêm bất kỳ lời chào, giải thích hay markdown code block nào.\n\n"
    "{content}"
)

def get_chrome_executable() -> Optional[str]:
    """Tìm đường dẫn Google Chrome cài trên hệ thống nếu có để tối ưu tốc độ và tránh Cloudflare."""
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe")
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return None

PROMPT_INPUT_SELECTOR = "#mobile-composer-prompt, #prompt-textarea, textarea, div[contenteditable='true'], [data-id='root']"

class SubtitleTranslator:
    """
    Module dịch phụ đề sử dụng Playwright tự động hóa ChatGPT Web (Google Chrome / Chromium),
    hỗ trợ chia nhỏ theo chunk, phát hiện chính xác tức thì khi nào ChatGPT dừng lại (nút gửi/copy hiện trở lại),
    kèm cơ chế dự phòng tự động bằng Google Translate API miễn phí.
    """
    def __init__(self, browser_profile_dir: Optional[Path] = None):
        if browser_profile_dir is None:
            self.profile_dir = Path(__file__).parent.parent / "data" / "browser_profile"
        else:
            self.profile_dir = Path(browser_profile_dir)
        self.profile_dir.mkdir(parents=True, exist_ok=True)

    def _is_logged_in(self, page) -> bool:
        """Kiểm tra xem người dùng đã đăng nhập tài khoản ChatGPT trên trình duyệt chưa."""
        try:
            return page.evaluate("""() => {
                // 1. Kiểm tra avatar / nút profile (chỉ có khi đã đăng nhập)
                const profileBtn = document.querySelector(
                    '[data-testid="profile-button"], [data-testid="accounts-profile-button"], button[aria-label*="User profile"], button[aria-label*="Profile"], img[alt*="User"]'
                );
                if (profileBtn) return true;

                // 2. Kiểm tra các nút đăng nhập / đăng ký
                const allButtons = Array.from(document.querySelectorAll('button, a'));
                const loginBtn = allButtons.find(el => {
                    const text = (el.innerText || '').trim().toLowerCase();
                    const testId = (el.getAttribute('data-testid') || '').toLowerCase();
                    const href = (el.getAttribute('href') || '').toLowerCase();
                    return (
                        testId === 'login-button' ||
                        testId === 'signup-button' ||
                        href.includes('/auth/login') ||
                        text === 'log in' ||
                        text === 'sign up' ||
                        text === 'sign up for free' ||
                        text === 'đăng nhập' ||
                        text === 'đăng ký'
                    );
                });

                if (loginBtn) return false;

                // 3. Nếu URL đang ở trang auth
                if (window.location.href.includes('/auth/')) return false;

                return true;
            }""")
        except Exception:
            return True

    def open_browser_for_login(self) -> None:
        """Mở cửa sổ Chrome với profile của ứng dụng để người dùng chủ động đăng nhập ChatGPT."""
        import subprocess
        chrome_exe = get_chrome_executable()
        cmd = []
        if chrome_exe:
            cmd = [
                chrome_exe,
                f"--user-data-dir={self.profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
                "https://chatgpt.com"
            ]
        else:
            script = f"""
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(r'{self.profile_dir}', headless=False)
    page = ctx.new_page() if not ctx.pages else ctx.pages[0]
    page.goto('https://chatgpt.com')
    page.wait_for_timeout(300000)
"""
            import sys
            cmd = [sys.executable, "-c", script]

        subprocess.Popen(cmd)

    def _find_prompt_input(self, page, timeout_ms: int = 10000):
        """Tìm ô nhập prompt của ChatGPT bằng selector gộp đa năng siêu tốc."""
        try:
            el = page.wait_for_selector(PROMPT_INPUT_SELECTOR, timeout=timeout_ms)
            if el and el.is_visible():
                return el
        except Exception:
            pass
        return None

    def _click_send(self, page, target_input=None) -> bool:
        """Bấm nút gửi hoặc nhấn Enter trên ô nhập mà không delay thừa."""
        t0 = time.time()
        while time.time() - t0 < 2.5:
            clicked = page.evaluate("""() => {
                const sendSelectors = [
                    'button[data-testid="send-button"]',
                    'button[data-testid="fruitjuice-send-button"]',
                    'button[aria-label*="Send" i]',
                    'button[aria-label*="Gửi" i]',
                    'button[aria-label="Send message"]',
                    'button[aria-label="Send prompt"]'
                ];
                for (const sel of sendSelectors) {
                    const btns = Array.from(document.querySelectorAll(sel));
                    for (const b of btns) {
                        if (b.offsetParent !== null && !b.disabled && b.getAttribute('aria-disabled') !== 'true') {
                            b.click();
                            return true;
                        }
                    }
                }
                return false;
            }""")
            if clicked:
                return True
            time.sleep(0.15)

        if target_input:
            try:
                target_input.press("Enter")
                return True
            except Exception:
                pass

        try:
            page.keyboard.press("Enter")
            return True
        except Exception:
            return False

    def _get_current_response_text(self, page) -> str:
        """Lấy văn bản phản hồi mới nhất từ giao diện ChatGPT."""
        return page.evaluate("""() => {
            const assistantMsgs = document.querySelectorAll('[data-message-author-role="assistant"], div[class*="agent-turn"], article');
            if (assistantMsgs.length > 0) {
                const lastMsg = assistantMsgs[assistantMsgs.length - 1];
                const text = (lastMsg.innerText || '').trim();
                if (text) return text;
            }
            const container = document.querySelector('[data-mobile-thread-content], [aria-label="Conversation"], [data-octane-detail-pane], main') || document.body;
            const fullText = container.innerText || '';
            const parts = fullText.split(/ChatGPT said:|ChatGPT đã nói:/i);
            if (parts.length > 1) {
                return parts[parts.length - 1].trim();
            }
            return "";
        }""")

    def _inject_prompt_text(self, page, text: str) -> bool:
        """
        Điền prompt vào ô chat ChatGPT an toàn tuyệt đối, hỗ trợ cả div[contenteditable='true'] và textarea,
        tránh hoàn toàn lỗi 'element is not visible' của Playwright fill().
        """
        try:
            return page.evaluate("""(promptText) => {
                let el = document.querySelector('#prompt-textarea');
                if (!el || el.offsetParent === null) {
                    el = document.querySelector('div[contenteditable="true"]') || document.querySelector('textarea:not([style*="display: none"])');
                }
                if (!el) return false;

                el.scrollIntoView({ block: 'center' });
                el.focus();

                if (el.getAttribute('contenteditable') === 'true' || el.tagName === 'DIV') {
                    document.execCommand('selectAll', false, null);
                    const success = document.execCommand('insertText', false, promptText);
                    if (!success || !el.innerText.trim()) {
                        el.innerText = promptText;
                        el.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                } else {
                    el.value = promptText;
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                }
                el.dispatchEvent(new Event('change', { bubbles: true }));
                return true;
            }""", text)
        except Exception:
            return False

    def _wait_for_response(
        self,
        page,
        prev_text: str,
        timeout: int = 240,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> str:
        """
        Chờ ChatGPT hoàn tất câu trả lời:
        - Tự động duy trì thời gian chờ (reset timer liên tục) khi ChatGPT đang gõ hoặc văn bản tiếp tục tăng.
        - Nhận diện dừng chuẩn xác bằng:
          1. Nút Stop biến mất
          2. Nút Send / Copy xuất hiện trở lại
          3. Văn bản mới khác với prev_text và ổn định không đổi trong ít nhất 1.2s.
        """
        start_wait = time.time()
        last_seen_text = ""
        stable_count = 0
        last_activity_time = time.time()
        prev_clean = prev_text.strip() if prev_text else ""

        # Cho phép ChatGPT bắt đầu sinh (chờ tối đa 6s để nút Stop xuất hiện hoặc có chữ mới)
        t_trigger = time.time()
        while time.time() - t_trigger < 6.0:
            if cancel_check and cancel_check():
                raise InterruptedError("Người dùng đã hủy tiến trình.")
            is_gen = page.evaluate("""() => {
                const stopBtn = Array.from(document.querySelectorAll('button')).find(b => {
                    const l = (b.getAttribute('aria-label') || '').toLowerCase();
                    const t = (b.getAttribute('data-testid') || '').toLowerCase();
                    return b.offsetParent !== null && (l.includes('stop') || l.includes('dừng') || t.includes('stop'));
                });
                return !!stopBtn;
            }""")
            cur = self._get_current_response_text(page).strip()
            if is_gen or (cur and cur != prev_clean):
                break
            time.sleep(0.3)

        while time.time() - last_activity_time < timeout:
            if cancel_check and cancel_check():
                raise InterruptedError("Người dùng đã hủy tiến trình.")

            state = page.evaluate("""() => {
                const stopBtn = Array.from(document.querySelectorAll('button')).find(b => {
                    const l = (b.getAttribute('aria-label') || '').toLowerCase();
                    const t = (b.getAttribute('data-testid') || '').toLowerCase();
                    return b.offsetParent !== null && (l.includes('stop') || l.includes('dừng') || t.includes('stop'));
                });

                const sendBtn = Array.from(document.querySelectorAll('button')).find(b => {
                    const l = (b.getAttribute('aria-label') || '').toLowerCase();
                    const t = (b.getAttribute('data-testid') || '').toLowerCase();
                    return b.offsetParent !== null && (l.includes('send') || l.includes('gửi') || t.includes('send'));
                });

                const copyBtns = Array.from(document.querySelectorAll('button')).filter(b => {
                    const l = (b.getAttribute('aria-label') || '').toLowerCase();
                    const t = (b.getAttribute('data-testid') || '').toLowerCase();
                    return b.offsetParent !== null && (l.includes('copy') || l.includes('sao chép') || t.includes('copy'));
                });

                let text = "";
                const assistantMsgs = document.querySelectorAll('[data-message-author-role="assistant"], div[class*="agent-turn"], article');
                if (assistantMsgs.length > 0) {
                    text = (assistantMsgs[assistantMsgs.length - 1].innerText || '').trim();
                } else {
                    const container = document.querySelector('[data-mobile-thread-content], [aria-label="Conversation"], [data-octane-detail-pane], main') || document.body;
                    const fullText = container.innerText || '';
                    const parts = fullText.split(/ChatGPT said:|ChatGPT đã nói:/i);
                    if (parts.length > 1) {
                        text = parts[parts.length - 1].trim();
                    }
                }

                return {
                    isGenerating: !!stopBtn,
                    sendReady: !!sendBtn,
                    copyCount: copyBtns.length,
                    text: text
                };
            }""")

            is_generating = state.get("isGenerating", False)
            send_ready = state.get("sendReady", False)
            copy_count = state.get("copyCount", 0)
            current_text = state.get("text", "").strip()

            # NẾU ChatGPT ĐANG VIẾT HOẶC CÓ CHỮ MỚI -> RESET LẠI THỜI GIAN CHỜ ĐỂ KHÔNG BAO GIỜ BỊ TIMEOUT OAN
            if is_generating or (current_text and current_text != last_seen_text):
                last_activity_time = time.time()

            # Khi nút Stop biến mất, và có nút Send/Copy hoặc văn bản không đổi, và khác nội dung chunk trước
            if not is_generating and (send_ready or copy_count > 0) and current_text and current_text != prev_clean:
                if current_text == last_seen_text:
                    stable_count += 1
                else:
                    last_seen_text = current_text
                    stable_count = 0

                # Chờ văn bản ổn định 3 nhịp (khoảng 0.9s - 1.2s)
                if stable_count >= 3:
                    app_logger.success("ChatGPT đã hoàn tất sinh câu trả lời!")
                    return current_text

            time.sleep(0.3)

        if last_seen_text and last_seen_text != prev_clean:
            return last_seen_text

        raise TimeoutError(f"Quá thời gian chờ phản hồi từ ChatGPT Web ({timeout}s không có phản hồi mới).")

    def translate_with_chatgpt(
        self,
        subtitles: List[Dict[str, Any]],
        headless: bool = False,
        timeout: int = 240,
        batch_size: int = 25,
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Mở trình duyệt (ưu tiên Google Chrome thật), gửi prompt dịch theo từng chunk (mặc định 25 câu)
        sang ChatGPT Web và tự động tiếp tục ngay lập tức khi ChatGPT hoàn thành.
        """
        from playwright.sync_api import sync_playwright

        if not subtitles:
            return []

        total_subtitles = len(subtitles)
        total_chunks = (total_subtitles + batch_size - 1) // batch_size
        app_logger.info(f"Bắt đầu dịch {total_subtitles} câu qua ChatGPT Web ({total_chunks} chunk, tối đa {batch_size} câu/chunk)...")

        chrome_exe = get_chrome_executable()
        launch_kwargs = {
            "user_data_dir": str(self.profile_dir),
            "headless": headless,
            "args": [
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars"
            ],
            "viewport": {"width": 1280, "height": 800}
        }
        if chrome_exe:
            launch_kwargs["executable_path"] = chrome_exe

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(**launch_kwargs)

            try:
                page = context.pages[0] if context.pages else context.new_page()
                app_logger.info("Đang truy cập https://chatgpt.com ...")
                page.goto("https://chatgpt.com", wait_until="domcontentloaded", timeout=60000)

                if cancel_check and cancel_check():
                    raise InterruptedError("Người dùng đã hủy tiến trình.")

                # Kiểm tra trạng thái đăng nhập tài khoản ChatGPT
                is_logged_in = self._is_logged_in(page)
                if not is_logged_in:
                    app_logger.warning("⚠️ PHÁT HIỆN: Tài khoản ChatGPT CHƯA ĐĂNG NHẬP!")
                    if headless:
                        raise RuntimeError(
                            "ChatGPT chưa được đăng nhập! Vui lòng vào Tab '🌐 Dịch' bỏ chọn 'Chạy ẩn trình duyệt' "
                            "(hoặc bấm '🔑 Đăng nhập ChatGPT ngay') để đăng nhập tài khoản trên Chrome trước khi chạy."
                        )
                    else:
                        app_logger.info("👉 Vui lòng nhấn 'Log in' trên cửa sổ trình duyệt Chrome đang mở để đăng nhập tài khoản ChatGPT...")
                        # Chờ người dùng đăng nhập trong tối đa 120s
                        login_wait_start = time.time()
                        while time.time() - login_wait_start < 120:
                            if cancel_check and cancel_check():
                                raise InterruptedError("Người dùng đã hủy tiến trình.")
                            if self._is_logged_in(page):
                                app_logger.success("🎉 Đã phát hiện đăng nhập ChatGPT thành công! Tiếp tục tiến trình dịch thuật...")
                                is_logged_in = True
                                time.sleep(2.0)
                                break
                            time.sleep(2.0)

                        if not is_logged_in:
                            app_logger.warning("⚠️ Người dùng chưa đăng nhập sau 120s. Tiếp tục xử lý...")
                else:
                    app_logger.success("✅ Đã xác thực tài khoản ChatGPT đã đăng nhập!")

                # Kiểm tra ô nhập prompt ngay lập tức
                target_input = self._find_prompt_input(page, timeout_ms=5000)
                if not target_input:
                    app_logger.warning("Chưa thấy ô nhập prompt ChatGPT. Có thể cần xác minh CAPTCHA / Cloudflare!")
                    if headless:
                        raise RuntimeError("ChatGPT yêu cầu tương tác giao diện. Hãy tắt chế độ Headless để xác minh trước!")
                    else:
                        app_logger.info("Vui lòng hoàn tất xác thực trên cửa sổ trình duyệt...")
                        target_input = page.wait_for_selector(
                            PROMPT_INPUT_SELECTOR,
                            timeout=90000
                        )

                # Tiến hành dịch lần lượt từng chunk phụ đề
                for chunk_idx in range(total_chunks):
                    if cancel_check and cancel_check():
                        raise InterruptedError("Người dùng đã hủy tiến trình.")

                    start_idx = chunk_idx * batch_size
                    end_idx = min(start_idx + batch_size, total_subtitles)
                    chunk = subtitles[start_idx:end_idx]

                    app_logger.info(
                        f"--- Đang gửi chunk {chunk_idx + 1}/{total_chunks} "
                        f"(câu [{chunk[0]['index']}] -> [{chunk[-1]['index']}]) sang ChatGPT ---"
                    )

                    lines = [f"[{item['index']}] {item['text']}" for item in chunk]
                    content_text = "\n".join(lines)
                    full_prompt = DEFAULT_PROMPT_TEMPLATE.format(content=content_text)

                    prev_resp_text = self._get_current_response_text(page)

                    # Điền nội dung prompt an toàn tuyệt đối (không lỗi element is not visible)
                    injected = False
                    for _ in range(6):
                        injected = self._inject_prompt_text(page, full_prompt)
                        if injected:
                            break
                        time.sleep(0.5)

                    if not injected:
                        # Dự phòng bằng keyboard type nếu JS chưa tìm thấy el
                        target_input = self._find_prompt_input(page, timeout_ms=5000)
                        if target_input:
                            try:
                                target_input.click()
                                page.keyboard.insert_text(full_prompt)
                                injected = True
                            except Exception:
                                pass

                    if not injected:
                        raise RuntimeError(f"Không thể điền prompt vào ô chat ChatGPT tại chunk {chunk_idx + 1}!")

                    time.sleep(0.3)
                    self._click_send(page)
                    app_logger.info(f"Đã gửi chunk {chunk_idx + 1}/{total_chunks}. Đang nhận diện phản hồi...")

                    # Chờ phản hồi tự động
                    raw_response = self._wait_for_response(
                        page=page,
                        prev_text=prev_resp_text,
                        timeout=timeout,
                        cancel_check=cancel_check
                    )

                    # Bóc tách bản dịch cho chunk này
                    self._parse_chunk_response(chunk, raw_response)
                    app_logger.success(f"Hoàn tất dịch chunk {chunk_idx + 1}/{total_chunks} ({len(chunk)} câu)!")

                    # Nghỉ ngắn 0.5s giữa các chunk
                    if chunk_idx + 1 < total_chunks:
                        time.sleep(0.5)

                app_logger.success(f"Đã hoàn thành dịch toàn bộ {total_subtitles} câu phụ đề qua ChatGPT Web!")
                return subtitles

            finally:
                context.close()


    def translate_with_google(
        self,
        subtitles: List[Dict[str, Any]],
        source_lang: str = "zh-CN",
        target_lang: str = "vi",
        cancel_check: Optional[Callable[[], bool]] = None
    ) -> List[Dict[str, Any]]:
        """
        Dịch phụ đề bằng Google Translate API miễn phí (dự phòng nhanh, không phụ thuộc trình duyệt).
        """
        if not subtitles:
            return []

        app_logger.info(f"Đang dịch {len(subtitles)} câu bằng Google Translate (miễn phí, tốc độ cao)...")
        
        for item in subtitles:
            if cancel_check and cancel_check():
                raise InterruptedError("Người dùng đã hủy tiến trình.")

            text = item.get("text", "").strip()
            if not text:
                item["translation"] = ""
                continue

            try:
                encoded = urllib.parse.quote(text)
                url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl={source_lang}&tl={target_lang}&dt=t&q={encoded}"
                resp = requests.get(url, timeout=10)
                if resp.status_code == 200:
                    data = resp.json()
                    translated_parts = [part[0] for part in data[0] if part and part[0]]
                    item["translation"] = "".join(translated_parts).strip()
                else:
                    item["translation"] = text
            except Exception as e:
                app_logger.warning(f"Lỗi dịch câu '{text}': {e}. Giữ nguyên text gốc.")
                item["translation"] = text

            time.sleep(0.08)

        app_logger.success("Đã dịch xong toàn bộ phụ đề bằng Google Translate!")
        return subtitles

    def _parse_chunk_response(self, chunk: List[Dict[str, Any]], raw_text: str) -> None:
        """
        Bóc tách các dòng [ID] Bản dịch và gán vào danh sách câu trong chunk.
        Hỗ trợ nhiều dạng format của ChatGPT ([1], [1]:, 1., **[1]**).
        """
        bracket_pattern = re.compile(r"\[(\d+)\][:\s\*\-]*(.*)")
        number_pattern = re.compile(r"^(\d+)[\.\:\-\s\*]+(.*)")
        translated_map = {}

        for line in raw_text.splitlines():
            line = line.strip()
            if not line or line.startswith("```"):
                continue

            # Ưu tiên mẫu [ID]
            m = bracket_pattern.search(line)
            if m:
                idx = int(m.group(1))
                content = m.group(2).strip().strip("*").strip().lstrip(":").strip()
                content = re.sub(r"\s+", " ", content)
                translated_map[idx] = content
                continue

            # Mẫu số thứ tự ở đầu dòng nếu ChatGPT không bọc ngoặc vuông
            m2 = number_pattern.match(line)
            if m2:
                idx = int(m2.group(1))
                content = m2.group(2).strip().strip("*").strip().lstrip(":").strip()
                content = re.sub(r"\s+", " ", content)
                if idx not in translated_map:
                    translated_map[idx] = content

        for sub in chunk:
            idx = sub["index"]
            if idx in translated_map and translated_map[idx]:
                sub["translation"] = translated_map[idx]
            else:
                # Nếu ChatGPT bỏ sót câu nào, dịch câu đó bằng Google Translate
                app_logger.warning(f"Câu [{idx}] chưa có bản dịch từ ChatGPT, tự động dịch bổ sung qua Google...")
                sub["translation"] = self._single_google_translate(sub["text"])

    def _single_google_translate(self, text: str) -> str:
        try:
            encoded = urllib.parse.quote(text)
            url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=zh-CN&tl=vi&dt=t&q={encoded}"
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                translated_parts = [part[0] for part in data[0] if part and part[0]]
                return "".join(translated_parts).strip()
        except Exception:
            pass
        return text

translator = SubtitleTranslator()
