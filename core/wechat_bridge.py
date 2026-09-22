"""
WeChat Windows Integration Bridge.

Provides zero-mouse-movement clipboard injection and messaging
to bridge generated stickers directly into WeChat Windows.
"""

import io
import os
import time
from typing import Optional, Union, List
from PIL import Image
import psutil

try:
    import win32gui
    import win32con
    import win32clipboard
    import win32process
    import win32api
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class WeChatBridge:
    """
    Bridge utility for communicating with and feeding stickers into WeChat on Windows.
    """

    @staticmethod
    def is_wechat_running() -> bool:
        """Checks if WeChat / Weixin process is currently active."""
        for p in psutil.process_iter(['name']):
            name = (p.info['name'] or '').lower()
            if 'weixin.exe' in name or 'wechat.exe' in name:
                return True
        return False

    @staticmethod
    def get_wechat_pids() -> List[int]:
        """Returns PIDs of active WeChat processes."""
        pids = []
        for p in psutil.process_iter(['pid', 'name']):
            name = (p.info['name'] or '').lower()
            if 'weixin.exe' in name or 'wechat.exe' in name:
                pids.append(p.info['pid'])
        return pids

    @staticmethod
    def find_wechat_window() -> Optional[int]:
        """
        Attempts to locate WeChat's main window handle without disturbing the user.
        """
        if not HAS_WIN32:
            return None

        wechat_hwnds = []

        def enum_cb(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                cls = win32gui.GetClassName(hwnd)
                # Typical WeChat window classes and titles
                if any(k in title for k in ['微信', 'WeChat', '文件传输助手']) or \
                   any(k in cls for k in ['WeChatMainWndForPC', 'ChatWnd', 'Qt5QWindowIcon', 'Qt6QWindowIcon']):
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    extra.append((hwnd, title, cls, pid))
            return True

        try:
            win32gui.EnumWindows(enum_cb, wechat_hwnds)
        except Exception:
            pass

        if wechat_hwnds:
            # Return the first matching visible window
            return wechat_hwnds[0][0]
        return None

    @staticmethod
    def copy_image_to_clipboard(image_input: Union[str, Image.Image]) -> bool:
        """
        Copies an image into the Windows system clipboard using both standard DIB
        and the registered 'PNG' format so that full Alpha transparency is preserved in WeChat.
        """
        if not HAS_WIN32:
            raise RuntimeError("pywin32 is required on Windows for clipboard operations.")

        if isinstance(image_input, str):
            img = Image.open(image_input)
        elif isinstance(image_input, Image.Image):
            img = image_input
        else:
            raise TypeError("Unsupported image_input type")

        # 1. Prepare PNG byte stream (Preserves transparent alpha channel in WeChat)
        png_output = io.BytesIO()
        img.save(png_output, format="PNG")
        png_data = png_output.getvalue()
        png_output.close()

        # 2. Prepare BMP / DIB byte stream (Fallback for legacy apps)
        # Note: BMP requires stripping the 14-byte BITMAPFILEHEADER to get CF_DIB
        bmp_output = io.BytesIO()
        # Convert RGBA to RGB with white background for fallback DIB
        if img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            bg.save(bmp_output, format="BMP")
        else:
            img.save(bmp_output, format="BMP")
        dib_data = bmp_output.getvalue()[14:]
        bmp_output.close()

        # 3. Write to Windows Clipboard with retry
        for attempt in range(5):
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()

                # Register PNG format on Windows clipboard
                png_format = win32clipboard.RegisterClipboardFormat("PNG")
                win32clipboard.SetClipboardData(png_format, png_data)

                # Set CF_DIB fallback
                win32clipboard.SetClipboardData(win32con.CF_DIB, dib_data)

                win32clipboard.CloseClipboard()
                return True
            except Exception:
                time.sleep(0.05)
                try:
                    win32clipboard.CloseClipboard()
                except Exception:
                    pass

        return False

    @staticmethod
    def paste_to_active_chat(hwnd: Optional[int] = None) -> bool:
        """
        Sends paste command without moving or clicking physical mouse cursor.
        """
        if not HAS_WIN32:
            return False

        target_hwnd = hwnd or WeChatBridge.find_wechat_window()
        if not target_hwnd:
            return False

        try:
            # Send WM_PASTE message directly to window
            win32gui.SendMessage(target_hwnd, win32con.WM_PASTE, 0, 0)
            return True
        except Exception:
            return False
