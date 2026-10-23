import tempfile
import time
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

from crc32_checker import CRC32App


class GUITests(unittest.TestCase):
    def setUp(self):
        try:
            self.app = CRC32App()
        except tk.TclError as error:
            self.skipTest("Tk window unavailable: {}".format(error))
        self.app.withdraw()
        self.addCleanup(self.app.close)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "sample.hex"

    def wait_for_result(self):
        deadline = time.monotonic() + 5
        while self.app.busy and time.monotonic() < deadline:
            self.app.update()
            time.sleep(0.01)
        self.assertFalse(self.app.busy, "Background calculation did not finish")

    def test_calculate_display_copy_and_switch_files(self):
        self.path.write_bytes(b":090000003132333435363738391A\n:00000001FF\n")
        self.app.path.set(str(self.path))
        self.app.calculate()
        self.assertTrue(self.app.busy)
        self.assertEqual(str(self.app.browse_button["state"]), "disabled")
        self.wait_for_result()
        self.assertEqual(self.app.checksum.get(), "CBF43926")
        self.assertIn("0x00000000–0x00000008", self.app.details.get())
        self.assertEqual(str(self.app.browse_button["state"]), "normal")
        self.app.copy()
        self.assertEqual(self.app.clipboard_get(), "CBF43926")
        binary_path = self.path.with_suffix(".bin")
        binary_path.write_bytes(b"123456789")
        self.app.path.set(str(binary_path))
        self.app._reset_result()
        self.assertEqual(self.app.checksum.get(), "—")
        self.assertEqual(str(self.app.copy_button["state"]), "disabled")
        self.app.calculate()
        self.wait_for_result()
        self.assertEqual(self.app.checksum.get(), "CBF43926")
        self.assertIn("Исходные байты", self.app.details.get())

    def test_error_clears_result_and_restores_controls(self):
        self.path.write_bytes(b"broken hex")
        self.app.path.set(str(self.path))
        with patch("crc32_checker.messagebox.showerror") as dialog:
            self.app.calculate()
            self.wait_for_result()
            dialog.assert_called_once()
        self.assertEqual(self.app.checksum.get(), "—")
        self.assertEqual(self.app.status.get(), "Ошибка расчёта")
        self.assertEqual(str(self.app.calculate_button["state"]), "normal")
        self.assertEqual(str(self.app.copy_button["state"]), "disabled")

    def test_cancel_restores_controls(self):
        self.path = self.path.with_suffix(".bin")
        self.path.write_bytes(b"123456789")
        self.app.path.set(str(self.path))
        self.app.calculate()
        self.app.cancel()
        self.wait_for_result()
        self.assertEqual(self.app.status.get(), "Расчёт отменён")
        self.assertEqual(self.app.checksum.get(), "—")
        self.assertEqual(str(self.app.calculate_button["state"]), "normal")


if __name__ == "__main__":
    unittest.main()
