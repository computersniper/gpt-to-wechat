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
    def _attach_default_desktop():
        """Ensures the calling thread is attached to the interactive 'Default' desktop on Windows."""
        try:
            import ctypes
            u32 = ctypes.windll.user32
            DESKTOP_ALL = 0x01FF
            hdesk = u32.OpenDesktopW('Default', 0, False, DESKTOP_ALL)
            if hdesk:
                u32.SetThreadDesktop(hdesk)
        except Exception:
            pass

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

        WeChatBridge._attach_default_desktop()
        wechat_hwnds = []

        def enum_cb(hwnd, extra):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                cls = win32gui.GetClassName(hwnd)
                # Typical WeChat window classes and titles
                if any(k in title for k in ['微信', 'WeChat', 'Weixin', '文件传输助手']) or \
                   any(k in cls for k in ['WeChatMainWndForPC', 'ChatWnd', 'Qt51514QWindowIcon', 'Qt5QWindowIcon', 'Qt6QWindowIcon']):
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
    def copy_files_to_clipboard(file_paths: List[str]) -> bool:
        """
        Copies multiple files into Windows clipboard using CF_HDROP format.
        Allows pasting ALL images/files simultaneously into WeChat (Ctrl+V) or Windows Explorer!
        """
        if not HAS_WIN32:
            return False

        WeChatBridge._attach_default_desktop()
        import struct

        abs_paths = [os.path.abspath(p) for p in file_paths if os.path.exists(p)]
        if not abs_paths:
            return False

        # Build DROPFILES structure (20 bytes header + UTF-16LE double-null terminated strings)
        offset = 20
        dropfiles = struct.pack('IIIII', offset, 0, 0, 0, 1)
        file_bytes = ('\0'.join(abs_paths) + '\0\0').encode('utf-16le')
        data = dropfiles + file_bytes

        for attempt in range(5):
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32con.CF_HDROP, data)
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
    def copy_image_to_clipboard(image_input: Union[str, Image.Image]) -> bool:
        """
        Copies an image into the Windows system clipboard using standard DIB,
        registered 'PNG' format, and CF_HDROP file path (if available)
        so that full Alpha transparency is preserved and WeChat accepts it reliably.
        """
        if not HAS_WIN32:
            raise RuntimeError("pywin32 is required on Windows for clipboard operations.")

        WeChatBridge._attach_default_desktop()
        import struct
        import tempfile

        file_path = None
        if isinstance(image_input, str):
            file_path = os.path.abspath(image_input)
            img = Image.open(image_input)
        elif isinstance(image_input, Image.Image):
            img = image_input
            # Save to temporary PNG so CF_HDROP is also available for apps like WeChat 4.x
            try:
                temp_dir = os.path.join(tempfile.gettempdir(), "gpt_to_wechat")
                os.makedirs(temp_dir, exist_ok=True)
                temp_path = os.path.join(temp_dir, f"sticker_{int(time.time()*1000)}.png")
                img.save(temp_path, format="PNG")
                file_path = os.path.abspath(temp_path)
            except Exception:
                file_path = None
        else:
            raise TypeError("Unsupported image_input type")

        # 1. Prepare PNG byte stream (Preserves transparent alpha channel in WeChat)
        png_output = io.BytesIO()
        img.save(png_output, format="PNG")
        png_data = png_output.getvalue()
        png_output.close()

        # 2. Prepare BMP / DIB byte stream (Fallback for legacy apps)
        bmp_output = io.BytesIO()
        if img.mode in ("RGBA", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            bg.paste(img, mask=img.split()[-1])
            bg.save(bmp_output, format="BMP")
        else:
            img.save(bmp_output, format="BMP")
        dib_data = bmp_output.getvalue()[14:]
        bmp_output.close()

        # 3. Prepare CF_HDROP data if file_path is available
        hdrop_data = None
        if file_path and os.path.exists(file_path):
            offset = 20
            dropfiles = struct.pack('IIIII', offset, 0, 0, 0, 1)
            file_bytes = (file_path + '\0\0').encode('utf-16le')
            hdrop_data = dropfiles + file_bytes

        # 4. Write to Windows Clipboard with retry
        for attempt in range(5):
            try:
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()

                # Register and set CF_HDROP (Highest priority for WeChat file send)
                if hdrop_data:
                    win32clipboard.SetClipboardData(win32con.CF_HDROP, hdrop_data)

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
        Brings WeChat window to foreground and sends Ctrl+V key events.
        """
        if not HAS_WIN32:
            return False

        WeChatBridge._attach_default_desktop()
        target_hwnd = hwnd or WeChatBridge.find_wechat_window()
        if not target_hwnd:
            return False

        try:
            import ctypes
            u32 = ctypes.windll.user32
            # Restore and bring window to front
            u32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
            u32.SetForegroundWindow(target_hwnd)
            time.sleep(0.25)

            # Synthesize Ctrl+V (pure keyboard message, zero mouse movement)
            VK_CONTROL = 0x11
            VK_V = 0x56
            KEYEVENTF_KEYUP = 0x0002

            u32.keybd_event(VK_CONTROL, 0, 0, 0)
            u32.keybd_event(VK_V, 0, 0, 0)
            time.sleep(0.05)
            u32.keybd_event(VK_V, 0, KEYEVENTF_KEYUP, 0)
            u32.keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, 0)
            return True
        except Exception:
            return False

    @staticmethod
    def paste_files_to_active_chat(file_paths: List[str], hwnd: Optional[int] = None) -> bool:
        """
        Copies multiple files to clipboard and automatically pastes them into WeChat.
        """
        if not WeChatBridge.copy_files_to_clipboard(file_paths):
            return False
        return WeChatBridge.paste_to_active_chat(hwnd=hwnd)

