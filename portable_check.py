"""Diagnostic mode to verify the actual packaged executable and its Tk runtime."""

import json
import sys
import tempfile
import time
import traceback
from pathlib import Path

from app_metadata import AUTHOR, VERSION
from crc32_core import HexFormatError, calculate_intel_hex, calculate_raw


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
            report["ok"] = True
    except Exception:
        report["error"] = traceback.format_exc()
    finally:
        if app is not None:
            app.close()
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1
