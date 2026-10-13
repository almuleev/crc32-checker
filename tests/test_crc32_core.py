import tempfile
import threading
import unittest
import zlib
from pathlib import Path

from crc32_core import (
    CHUNK_SIZE, CalculationCancelled, HexFormatError,
    calculate_intel_hex, calculate_raw,
)


def record(kind, address=0, data=b""):
    content = bytes([len(data)]) + address.to_bytes(2, "big") + bytes([kind]) + data
    return ":" + (content + bytes([(-sum(content)) & 0xFF])).hex().upper()


class CRC32Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "прошивка.hex"

    def write_hex(self, *lines):
        self.path.write_text("\n".join(lines) + "\n", encoding="ascii")
        return self.path

    def test_standard_check_value_and_unicode_path(self):
        self.path.write_bytes(b"123456789")
        result = calculate_raw(self.path)
        self.assertEqual(result.hexadecimal, "CBF43926")
        self.assertEqual(result.calculated_size, 9)

    def test_empty_raw_file(self):
        self.path.write_bytes(b"")
        self.assertEqual(calculate_raw(self.path).hexadecimal, "00000000")

    def test_multiple_chunks_and_progress(self):
        data = bytes(range(256)) * ((CHUNK_SIZE * 2 // 256) + 1)
        self.path.write_bytes(data)
        progress = []
        result = calculate_raw(self.path, progress=progress.append)
        self.assertEqual(result.crc32, zlib.crc32(data))
        self.assertEqual(result.calculated_size, len(data))
        self.assertEqual(progress[-1], 1.0)
        self.assertEqual(progress, sorted(progress))

    def test_hex_matches_binary_data(self):
        result = calculate_intel_hex(self.write_hex(record(0, 0x100, b"123456789"), record(1)))
        self.assertEqual(result.hexadecimal, "CBF43926")
        self.assertEqual((result.start_address, result.end_address), (0x100, 0x108))
        self.assertEqual(result.fill_size, 0)

    def test_unordered_records_and_ff_gap(self):
        result = calculate_intel_hex(self.write_hex(
            record(0, 0x104, b"B"), record(0, 0x100, b"A"), record(1)))
        self.assertEqual(result.crc32, zlib.crc32(b"A\xff\xff\xffB"))
        self.assertEqual(result.calculated_size, 5)
        self.assertEqual(result.data_size, 2)
        self.assertEqual(result.fill_size, 3)

    def test_extended_linear_address_and_execution_metadata(self):
        result = calculate_intel_hex(self.write_hex(
            record(4, data=b"\x08\x00"), record(0, 0x10, b"123456789"),
            record(5, data=b"\x08\x00\x00\x10"), record(1)))
        self.assertEqual(result.start_address, 0x08000010)
        self.assertEqual(result.hexadecimal, "CBF43926")

    def test_segment_address_and_start_segment_metadata(self):
        result = calculate_intel_hex(self.write_hex(
            record(2, data=b"\x12\x34"), record(0, 0x56, b"123456789"),
            record(3, data=b"\x12\x34\x00\x56"), record(1)))
        self.assertEqual(result.start_address, 0x12396)
        self.assertEqual(result.hexadecimal, "CBF43926")

    def test_switch_address_modes(self):
        result = calculate_intel_hex(self.write_hex(
            record(4, data=b"\x00\x01"), record(0, 0, b"B"),
            record(2, data=b"\x10\x00"), record(0, 1, b"C"), record(1)))
        self.assertEqual(result.crc32, zlib.crc32(b"BC"))
        self.assertEqual(result.start_address, 0x10000)

    def test_maximum_address_and_maximum_record_length(self):
        result = calculate_intel_hex(self.write_hex(
            record(4, data=b"\xff\xff"), record(0, 0xff01, bytes(range(255))), record(1)))
        self.assertEqual(result.end_address, 0xffffffff)
        self.assertEqual(result.crc32, zlib.crc32(bytes(range(255))))

    def test_gap_exceeding_chunk_size(self):
        offset = CHUNK_SIZE + 3
        result = calculate_intel_hex(self.write_hex(
            record(0, 0, b"A"), record(4, data=(offset >> 16).to_bytes(2, "big")),
            record(0, offset & 0xffff, b"B"), record(1)))
        self.assertEqual(result.crc32, zlib.crc32(b"A" + b"\xff" * (offset - 1) + b"B"))
        self.assertEqual(result.fill_size, offset - 1)

    def test_bom_crlf_lowercase_and_blank_lines(self):
        content = "\ufeff\r\n" + record(0, data=b"123456789").lower() + "\r\n\r\n" + record(1) + "\r\n"
        self.path.write_bytes(content.encode("utf-8"))
        self.assertEqual(calculate_intel_hex(self.path).hexadecimal, "CBF43926")

    def test_raw_hex_includes_syntax_and_newlines(self):
        self.write_hex(record(0, data=b"123456789"), record(1))
        result = calculate_raw(self.path)
        self.assertEqual(result.crc32, zlib.crc32(self.path.read_bytes()))
        self.assertNotEqual(result.hexadecimal, "CBF43926")

    def test_invalid_inputs(self):
        valid = record(0, data=b"A")
        cases = {
            "checksum": [valid[:-2] + "00", record(1)],
            "length": [":0200000041BD", record(1)],
            "missing_eof": [valid],
            "after_eof": [valid, record(1), valid],
            "no_data": [record(1)],
            "unknown_type": [record(6), record(1)],
            "overlap": [record(0, 0x10, b"AB"), record(0, 0x11, b"B"), record(1)],
            "invalid_address_record": [record(4, address=1, data=b"\0\1"), valid, record(1)],
            "invalid_metadata_length": [record(3, data=b"\0\1"), valid, record(1)],
            "address_wrap": [record(0, 0xffff, b"AB"), record(1)],
            "text_dump": ["AA BB CC"],
            "odd_hex": [":100", record(1)],
            "invalid_character": [":00000001FG"],
            "very_long_line": [":" + "0" * 2000],
        }
        for name, lines in cases.items():
            with self.subTest(name=name):
                self.write_hex(*lines)
                with self.assertRaises(HexFormatError):
                    calculate_intel_hex(self.path)

    def test_cancellation(self):
        cancel = threading.Event()
        cancel.set()
        self.write_hex(record(0, data=b"A"), record(1))
        for calculate in (calculate_raw, calculate_intel_hex):
            with self.subTest(mode=calculate.__name__):
                with self.assertRaises(CalculationCancelled):
                    calculate(self.path, cancel=cancel)

    def test_cancellation_while_filling_gap(self):
        self.write_hex(record(0, data=b"A"), record(4, data=b"\x10\x00"),
                       record(0, data=b"B"), record(1))
        cancel = threading.Event()

        def progress(fraction):
            if fraction > 0.25:
                cancel.set()

        with self.assertRaises(CalculationCancelled):
            calculate_intel_hex(self.path, cancel, progress)

    def test_file_modified_during_read(self):
        self.path.write_bytes(b"A" * (CHUNK_SIZE + 1))
        modified = False

        def progress(fraction):
            nonlocal modified
            if not modified:
                modified = True
                with self.path.open("ab") as output:
                    output.write(b"B")

        with self.assertRaisesRegex(OSError, "изменился"):
            calculate_raw(self.path, progress=progress)

    def test_missing_file(self):
        with self.assertRaises(FileNotFoundError):
            calculate_raw(self.path)


if __name__ == "__main__":
    unittest.main()
