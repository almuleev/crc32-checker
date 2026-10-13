"""CRC-32/ISO-HDLC for raw files and Intel HEX memory images."""

import os
import re
import threading
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List, Optional, Tuple


CHUNK_SIZE = 1024 * 1024
FILL_BYTE = 0xFF
Progress = Optional[Callable[[float], None]]


class HexFormatError(ValueError):
    """Invalid or ambiguous Intel HEX input."""


class CalculationCancelled(Exception):
    pass


@dataclass(frozen=True)
class CRCResult:
    crc32: int
    source_size: int
    calculated_size: int
    data_size: int
    fill_size: int = 0
    start_address: Optional[int] = None
    end_address: Optional[int] = None  # Inclusive.

    @property
    def hexadecimal(self) -> str:
        return "{:08X}".format(self.crc32)


def _check_cancel(cancel: Optional[threading.Event]) -> None:
    if cancel is not None and cancel.is_set():
        raise CalculationCancelled()


def _report(progress: Progress, fraction: float) -> None:
    if progress is not None:
        progress(max(0.0, min(1.0, fraction)))


def _check_unchanged(initial: os.stat_result, current: os.stat_result) -> None:
    if (initial.st_size, initial.st_mtime_ns) != (current.st_size, current.st_mtime_ns):
        raise OSError("Файл изменился во время чтения. Повторите расчёт.")


def calculate_raw(path: Path, cancel: Optional[threading.Event] = None,
                  progress: Progress = None) -> CRCResult:
    """Read bytes in bounded chunks, including for an empty file."""
    crc = 0
    processed = 0
    with Path(path).open("rb") as source:
        initial = os.fstat(source.fileno())
        while True:
            _check_cancel(cancel)
            chunk = source.read(CHUNK_SIZE)
            if not chunk:
                break
            crc = zlib.crc32(chunk, crc)
            processed += len(chunk)
            _report(progress, processed / max(initial.st_size, 1))
        _check_unchanged(initial, os.fstat(source.fileno()))
    _check_cancel(cancel)
    _report(progress, 1.0)
    return CRCResult(crc & 0xFFFFFFFF, initial.st_size, processed, processed)


def _read_intel_hex(path: Path, cancel: Optional[threading.Event],
                    progress: Progress) -> Tuple[List[Tuple[int, bytes]], int]:
    records = []  # type: List[Tuple[int, bytes]]
    base = 0
    eof = False
    with Path(path).open("rb") as source:
        initial = os.fstat(source.fileno())
        line_number = 0
        while True:
            _check_cancel(cancel)
            line = source.readline(1024)
            if not line:
                break
            line_number += 1
            if line_number == 1 and line.startswith(b"\xef\xbb\xbf"):
                line = line[3:]
            line = line.strip()
            _report(progress, 0.25 * source.tell() / max(initial.st_size, 1))
            if not line:
                continue

            def fail(message: str) -> None:
                raise HexFormatError("Строка {}: {}".format(line_number, message))

            if eof:
                fail("обнаружены записи после конца файла (EOF).")
            if not re.fullmatch(rb":[0-9a-fA-F]{10,520}", line) or len(line) % 2 != 1:
                fail("ожидается запись Intel HEX вида :LLAAAATTDD…CC.")
            record = bytes.fromhex(line[1:].decode("ascii"))
            count = record[0]
            address = int.from_bytes(record[1:3], "big")
            kind = record[3]
            data = record[4:-1]
            if len(data) != count:
                fail("длина данных не совпадает с полем LL.")
            if sum(record) & 0xFF:
                fail("неверная контрольная сумма записи Intel HEX.")
            if kind == 0:
                if address + count > 0x10000:
                    fail("данные записи выходят за границу адреса 0xFFFF.")
                absolute = base + address
                if absolute + count > 0x100000000:
                    fail("адрес выходит за пределы 32 бит.")
                if data:
                    records.append((absolute, data))
            elif kind in (1, 2, 3, 4, 5):
                expected = {1: 0, 2: 2, 3: 4, 4: 2, 5: 4}[kind]
                if address != 0 or count != expected:
                    fail("некорректные поля записи типа {:02X}.".format(kind))
                if kind == 1:
                    eof = True
                elif kind == 2:
                    base = int.from_bytes(data, "big") << 4
                elif kind == 4:
                    base = int.from_bytes(data, "big") << 16
                # Start execution addresses (03/05) are metadata, not data bytes.
            else:
                fail("неподдерживаемый тип записи {:02X}.".format(kind))
        _check_unchanged(initial, os.fstat(source.fileno()))
    if not eof:
        raise HexFormatError("Нет обязательной записи конца файла :00000001FF.")
    if not records:
        raise HexFormatError("В Intel HEX нет записей с данными.")
    records.sort(key=lambda item: item[0])
    end = records[0][0]
    for address, data in records:
        _check_cancel(cancel)
        if address < end:
            raise HexFormatError("Перекрывающиеся данные по адресу 0x{:08X}.".format(address))
        end = address + len(data)
    return records, initial.st_size


def calculate_intel_hex(path: Path, cancel: Optional[threading.Event] = None,
                        progress: Progress = None) -> CRCResult:
    """CRC of ascending addresses, filling internal gaps with FF.

    Bytes before the first or after the last data address are excluded. Record
    syntax, checksums, and execution addresses are excluded. Gaps are streamed,
    so even a sparse 32-bit image does not allocate its entire address span.
    """
    records, source_size = _read_intel_hex(Path(path), cancel, progress)
    start = records[0][0]
    stop = records[-1][0] + len(records[-1][1])
    span = stop - start
    cursor = start
    crc = 0
    data_size = 0
    fill = bytes([FILL_BYTE]) * CHUNK_SIZE
    for address, data in records:
        while cursor < address:
            _check_cancel(cancel)
            size = min(address - cursor, CHUNK_SIZE)
            crc = zlib.crc32(fill if size == CHUNK_SIZE else fill[:size], crc)
            cursor += size
            _report(progress, 0.25 + 0.75 * (cursor - start) / span)
        _check_cancel(cancel)
        crc = zlib.crc32(data, crc)
        cursor += len(data)
        data_size += len(data)
        _report(progress, 0.25 + 0.75 * (cursor - start) / span)
    _check_cancel(cancel)
    _report(progress, 1.0)
    return CRCResult(crc & 0xFFFFFFFF, source_size, span, data_size,
                     span - data_size, start, stop - 1)
