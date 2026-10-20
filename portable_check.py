"""Diagnostic mode to verify the actual packaged executable and its Tk runtime."""

import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

from app_metadata import AUTHOR, VERSION
from crc32_core import HexFormatError, calculate_intel_hex, calculate_raw


def send_windows_file_drop(window_id, paths):
    """Exercise the native Explorer HDROP message, including UTF-16 filenames.

    Diagnostic/test helper: the destination must be an enabled WindowsFileDrop
    window, which takes ownership of the allocated handle via DragFinish.
    """
    import ctypes
    from ctypes import wintypes

    class DROPFILES(ctypes.Structure):
        _fields_ = [("pFiles", wintypes.DWORD), ("pt", wintypes.POINT),
                    ("fNC", wintypes.BOOL), ("fWide", wintypes.BOOL)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HANDLE
    kernel32.GlobalLock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HANDLE]
    kernel32.GlobalUnlock.restype = wintypes.BOOL
    kernel32.GlobalFree.argtypes = [wintypes.HANDLE]
    kernel32.GlobalFree.restype = wintypes.HANDLE
    user32.SendMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    user32.SendMessageW.restype = ctypes.c_ssize_t
    header = DROPFILES()
    header.pFiles = ctypes.sizeof(header)
    header.fWide = True
    data = ("\0".join(str(path) for path in paths) + "\0\0").encode("utf-16-le")
    handle = kernel32.GlobalAlloc(0x0042, ctypes.sizeof(header) + len(data))
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    pointer = kernel32.GlobalLock(handle)
    if not pointer:
        kernel32.GlobalFree(handle)
        raise ctypes.WinError(ctypes.get_last_error())
    ctypes.memmove(pointer, ctypes.byref(header), ctypes.sizeof(header))
    ctypes.memmove(pointer + ctypes.sizeof(header), data, len(data))
    kernel32.GlobalUnlock(handle)
    user32.SendMessageW(window_id, 0x0233, handle, 0)


def run_self_test(app_factory, report_path):
    report_path = Path(report_path).resolve()
    report = {"ok": False, "frozen": bool(getattr(sys, "frozen", False)),
              "python": sys.version, "version": VERSION, "author": AUTHOR, "checks": []}
    app = None
    try:
        with tempfile.TemporaryDirectory(dir=str(report_path.parent)) as directory:
            raw = Path(directory) / "sample.bin"
            hex_file = Path(directory) / "sample.hex"
            raw.write_bytes(b"123456789")
            hex_file.write_bytes(b":090000003132333435363738391A\n:00000001FF\n")
            if calculate_raw(raw).hexadecimal != "CBF43926":
                raise AssertionError("Incorrect binary CRC32")
            if calculate_intel_hex(hex_file).hexadecimal != "CBF43926":
                raise AssertionError("Incorrect Intel HEX CRC32")
            report["checks"].extend(["binary_crc32", "intel_hex_crc32"])
            raw.write_bytes(b"")
            if calculate_raw(raw).hexadecimal != "00000000":
                raise AssertionError("Incorrect empty file CRC32")
            report["checks"].append("empty_file")
            raw.write_bytes(b"invalid hex")
            try:
                calculate_intel_hex(raw)
            except HexFormatError:
                report["checks"].append("invalid_hex_rejected")
            else:
                raise AssertionError("Invalid HEX accepted")
            app = app_factory()
            app.withdraw()
            app.update()
            report["checks"].append("tk_window_created")
            if report["frozen"]:
                resource_root = Path(sys._MEIPASS)
                for filename in ("LICENSE", "THIRD_PARTY_NOTICES.md", "licenses/PYTHON.txt",
                                 "licenses/TCL.txt", "licenses/TK.txt", "licenses/ZLIB.txt",
                                 "licenses/ZLIB-NG.txt", "licenses/PYINSTALLER.txt"):
                    if not (resource_root / filename).is_file():
                        raise AssertionError("Missing bundled notice: " + filename)
                report["checks"].append("bundled_licenses")
            about = app.show_about()
            about.update()
            about.destroy()
            report["checks"].append("about_window")
            app.path.set(str(hex_file))
            app.calculate()
            deadline = time.monotonic() + 10
            while app.busy and time.monotonic() < deadline:
                app.update()
                time.sleep(0.01)
            if app.busy or app.checksum.get() != "CBF43926":
                raise AssertionError("GUI calculation did not produce expected CRC32")
            report["checks"].append("gui_background_calculation")
            app.copy()
            if app.clipboard_get() != "CBF43926":
                raise AssertionError("Incorrect clipboard value")
            report["checks"].append("clipboard")
            if sys.platform == "win32":
                if app.drop_target is None:
                    raise AssertionError("Native file drop registration failed")
                dropped_file = Path(directory) / "прошивка с пробелами {1}.bin"
                dropped_file.write_bytes(b"123456789")
                send_windows_file_drop(app.drop_target.hwnd, [dropped_file])
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    app.update()
                    if app.path.get() == str(dropped_file) and not app.busy:
                        break
                    time.sleep(0.01)
                if app.busy or app.path.get() != str(dropped_file) or app.checksum.get() != "CBF43926":
                    raise AssertionError("Native Windows file drop did not calculate CRC32")
                report["checks"].append("windows_file_drop")
            report["ok"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if app is not None:
            app.close()
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1
