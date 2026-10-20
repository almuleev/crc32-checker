"""Windows Explorer file drops for Tk, using only the standard library.

Native callbacks only enqueue events; Tk work happens in its regular event loop.
Subclass callbacks are retained until detached from every live window.
"""

import ctypes
import sys
from ctypes import wintypes


WM_DROPFILES = 0x0233
WM_NCDESTROY = 0x0082


class WindowsFileDrop:
    def __init__(self, tk_window_id, on_drop, on_error):
        if sys.platform != "win32":
            raise OSError("File drops require Windows")
        self._on_drop = on_drop
        self._on_error = on_error
        self._windows = set()
        self._subclass_id = id(self)
        self._user32 = ctypes.WinDLL("user32", use_last_error=True)
        self._shell32 = ctypes.WinDLL("shell32", use_last_error=True)
        self._comctl32 = ctypes.WinDLL("comctl32", use_last_error=True)
        self._proc_type = ctypes.WINFUNCTYPE(
            ctypes.c_ssize_t, wintypes.HWND, wintypes.UINT,
            wintypes.WPARAM, wintypes.LPARAM, ctypes.c_size_t, ctypes.c_size_t)
        self._enum_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        self._configure_api()
        self.hwnd = self._user32.GetAncestor(tk_window_id, 2)  # GA_ROOT: Tk's wrapper HWND.
        if not self.hwnd:
            raise ctypes.WinError(ctypes.get_last_error())
        self._callback = self._proc_type(self._window_proc)
        handles = [self.hwnd]

        def collect(hwnd, _):
            handles.append(hwnd)
            return True

        self._user32.EnumChildWindows(self.hwnd, self._enum_type(collect), 0)
        try:
            for hwnd in set(handles):
                if not self._comctl32.SetWindowSubclass(hwnd, self._callback, self._subclass_id, 0):
                    raise OSError("Не удалось включить перетаскивание файлов.")
                self._windows.add(hwnd)
            self.set_enabled(True)
        except Exception:
            self.detach()
            raise

    def _configure_api(self):
        self._user32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
        self._user32.GetAncestor.restype = wintypes.HWND
        self._user32.EnumChildWindows.argtypes = [wintypes.HWND, self._enum_type, wintypes.LPARAM]
        self._user32.EnumChildWindows.restype = wintypes.BOOL
        self._user32.IsWindow.argtypes = [wintypes.HWND]
        self._user32.IsWindow.restype = wintypes.BOOL
        self._shell32.DragAcceptFiles.argtypes = [wintypes.HWND, wintypes.BOOL]
        self._shell32.DragAcceptFiles.restype = None
        self._shell32.DragQueryFileW.argtypes = [wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT]
        self._shell32.DragQueryFileW.restype = wintypes.UINT
        self._shell32.DragFinish.argtypes = [wintypes.HANDLE]
        self._shell32.DragFinish.restype = None
        self._comctl32.SetWindowSubclass.argtypes = [wintypes.HWND, self._proc_type, ctypes.c_size_t, ctypes.c_size_t]
        self._comctl32.SetWindowSubclass.restype = wintypes.BOOL
        self._comctl32.RemoveWindowSubclass.argtypes = [wintypes.HWND, self._proc_type, ctypes.c_size_t]
        self._comctl32.RemoveWindowSubclass.restype = wintypes.BOOL
        self._comctl32.DefSubclassProc.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        self._comctl32.DefSubclassProc.restype = ctypes.c_ssize_t

    def _window_proc(self, hwnd, message, wparam, lparam, subclass_id, ref_data):
        if message == WM_DROPFILES:
            try:
                paths = []
                try:
                    count = self._shell32.DragQueryFileW(wparam, 0xFFFFFFFF, None, 0)
                    for index in range(count):
                        length = self._shell32.DragQueryFileW(wparam, index, None, 0)
                        buffer = ctypes.create_unicode_buffer(length + 1)
                        if not self._shell32.DragQueryFileW(wparam, index, buffer, length + 1):
                            raise OSError("Не удалось прочитать путь перетаскиваемого файла.")
                        paths.append(buffer.value)
                finally:
                    self._shell32.DragFinish(wparam)
                self._on_drop(paths)
            except Exception as error:
                self._on_error(str(error))
            return 0
        if message == WM_NCDESTROY:
            self._comctl32.RemoveWindowSubclass(hwnd, self._callback, self._subclass_id)
            self._windows.discard(hwnd)
        return self._comctl32.DefSubclassProc(hwnd, message, wparam, lparam)

    def set_enabled(self, enabled):
        for hwnd in tuple(self._windows):
            self._shell32.DragAcceptFiles(hwnd, enabled)

    def detach(self):
        for hwnd in tuple(self._windows):
            if self._user32.IsWindow(hwnd):
                self._shell32.DragAcceptFiles(hwnd, False)
                self._comctl32.RemoveWindowSubclass(hwnd, self._callback, self._subclass_id)
        self._windows.clear()
