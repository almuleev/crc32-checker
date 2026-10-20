import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from crc32_checker import CRC32App, RAW_MODE
from portable_check import send_windows_file_drop


@unittest.skipUnless(sys.platform == "win32", "Native Explorer file drops require Windows")
class WindowsDropTests(unittest.TestCase):
    def setUp(self):
        self.app = CRC32App()
        self.app.withdraw()
        self.addCleanup(self.app.close)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "прошивка {тест} с пробелами.BIN"
        self.path.write_bytes(b"123456789")
        self.assertIsNotNone(self.app.drop_target)

    def wait_for_drop(self, expected_path):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            self.app.update()
            if self.app.path.get() == str(expected_path) and not self.app.busy:
                break
            time.sleep(0.01)
        self.assertEqual(self.app.path.get(), str(expected_path))
        self.assertFalse(self.app.busy)
        self.assertEqual(self.app.checksum.get(), "CBF43926")

    def test_native_bin_drop_handles_unicode_and_spaces(self):
        send_windows_file_drop(self.app.drop_target.hwnd, [self.path])
        self.wait_for_drop(self.path)

    def test_native_hex_drop_on_child_control(self):
        path = self.path.with_suffix(".HEX")
        path.write_bytes(b":090000003132333435363738391A\n:00000001FF\n")
        send_windows_file_drop(self.app.browse_button.winfo_id(), [path])
        self.wait_for_drop(path)
        self.assertIn("Intel HEX", self.app.details.get())

    def test_drop_preserves_raw_mode(self):
        path = self.path.with_suffix(".hex")
        path.write_bytes(b"123456789")
        self.app.mode.set(RAW_MODE)
        send_windows_file_drop(self.app.drop_target.hwnd, [path])
        self.wait_for_drop(path)
        self.assertIn("Исходные байты", self.app.details.get())

    def test_multiple_files_leave_existing_result_unchanged(self):
        self.app.open_file(self.path)
        self.wait_for_drop(self.path)
        with patch("crc32_checker.messagebox.showinfo") as dialog:
            send_windows_file_drop(self.app.drop_target.hwnd, [self.path, self.path])
            deadline = time.monotonic() + 1
            while not dialog.called and time.monotonic() < deadline:
                self.app.update()
                time.sleep(0.01)
            dialog.assert_called_once()
        self.assertEqual(self.app.checksum.get(), "CBF43926")
        self.assertEqual(self.app.path.get(), str(self.path))

    def test_directory_drop_is_rejected(self):
        with patch("crc32_checker.messagebox.showerror") as dialog:
            self.app._handle_drop([self.directory.name])
            dialog.assert_called_once()
        self.assertEqual(self.app.path.get(), "")
        self.assertFalse(self.app.busy)

    def test_drop_while_busy_keeps_current_file(self):
        self.app.path.set(str(self.path))
        self.app._set_busy(True)
        self.app._handle_drop([str(self.path.with_suffix(".hex"))])
        self.assertEqual(self.app.path.get(), str(self.path))
        self.assertTrue(self.app.busy)

    def test_detach_removes_native_callbacks(self):
        target = self.app.drop_target
        self.assertGreater(len(target._windows), 1)
        target.detach()
        self.assertEqual(target._windows, set())


if __name__ == "__main__":
    unittest.main()
