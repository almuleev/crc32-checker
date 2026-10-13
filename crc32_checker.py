"""A small Russian-language desktop CRC32 viewer (Python 3.8+)."""

import queue
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from app_metadata import APP_NAME, AUTHOR, COPYRIGHT, LICENSE, VERSION
from crc32_core import CalculationCancelled, calculate_intel_hex, calculate_raw


AUTO_MODE = "Авто: .hex — Intel HEX, .bin — байты файла"
RAW_MODE = "Исходные байты файла (включая текст .hex)"


def format_size(size):
    return "{:,} байт".format(size).replace(",", " ")


class CRC32App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        icon_path = resource_root / "assets" / "icon.ico"
        if sys.platform == "win32" and icon_path.exists():
            self.iconbitmap(str(icon_path))
        self.geometry("780x530")
        self.minsize(690, 510)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.events = queue.Queue()
        self.cancel_event = threading.Event()
        self.busy = False
        self.closing = False
        self.result = None
        self.path = tk.StringVar()
        self.mode = tk.StringVar(value=AUTO_MODE)
        self.checksum = tk.StringVar(value="—")
        self.details = tk.StringVar(value="Выберите файл .hex или .bin для расчёта CRC32.")
        self.status = tk.StringVar(value="Готово")
        self._build_ui()
        menu = tk.Menu(self)
        help_menu = tk.Menu(menu, tearoff=False)
        help_menu.add_command(label="О программе…", command=self.show_about)
        menu.add_cascade(label="Справка", menu=help_menu)
        self.configure(menu=menu)
        self.bind("<Control-o>", lambda event: self.choose_file())
        self.bind("<Escape>", lambda event: self.cancel())
        self.poll_id = self.after(80, self._poll_events)

    def _build_ui(self):
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        frame = ttk.Frame(self, padding=20)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        ttk.Label(frame, text="CRC32 Checker", font=("Segoe UI", 20, "bold")).grid(
            row=0, column=0, sticky="w")
        ttk.Label(frame, text="Контрольная сумма файлов .hex и .bin").grid(
            row=1, column=0, sticky="w", pady=(2, 16))
        file_row = ttk.Frame(frame)
        file_row.grid(row=2, column=0, sticky="ew")
        file_row.columnconfigure(0, weight=1)
        ttk.Entry(file_row, textvariable=self.path, state="readonly").grid(
            row=0, column=0, sticky="ew", padx=(0, 10))
        self.browse_button = ttk.Button(file_row, text="Выбрать файл…", command=self.choose_file)
        self.browse_button.grid(row=0, column=1)
        ttk.Label(frame, text="Данные для расчёта").grid(row=3, column=0, sticky="w", pady=(16, 5))
        self.mode_box = ttk.Combobox(frame, textvariable=self.mode,
                                    values=(AUTO_MODE, RAW_MODE), state="readonly")
        self.mode_box.grid(row=4, column=0, sticky="ew")
        self.mode_box.bind("<<ComboboxSelected>>", lambda event: self._reset_result())
        hint = ttk.Label(frame, text="Intel HEX: адреса по возрастанию; промежутки — FF;"
                         " служебные записи исключены.", wraplength=710)
        hint.grid(row=5, column=0, sticky="w", pady=(5, 12))
        actions = ttk.Frame(frame)
        actions.grid(row=6, column=0, sticky="w")
        self.calculate_button = ttk.Button(actions, text="Вычислить CRC32", command=self.calculate)
        self.calculate_button.pack(side="left")
        self.cancel_button = ttk.Button(actions, text="Отмена", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=10)
        self.progress = ttk.Progressbar(frame, maximum=100, mode="determinate")
        self.progress.grid(row=7, column=0, sticky="ew", pady=(14, 10))
        result_frame = ttk.LabelFrame(frame, text="CRC-32/ISO-HDLC", padding=(14, 8))
        result_frame.grid(row=8, column=0, sticky="ew")
        result_frame.columnconfigure(0, weight=1)
        ttk.Label(result_frame, textvariable=self.checksum,
                  font=("Consolas", 30, "bold")).grid(row=0, column=0, sticky="w")
        self.copy_button = ttk.Button(result_frame, text="Копировать", command=self.copy, state="disabled")
        self.copy_button.grid(row=0, column=1, padx=(10, 0))
        details_label = ttk.Label(frame, textvariable=self.details, wraplength=710, justify="left")
        details_label.grid(row=9, column=0, sticky="nw", pady=(12, 8))
        frame.bind("<Configure>", lambda event: (
            hint.configure(wraplength=max(200, event.width - 40)),
            details_label.configure(wraplength=max(200, event.width - 40))))
        frame.rowconfigure(9, weight=1)
        ttk.Label(frame, textvariable=self.status).grid(row=10, column=0, sticky="w")

    def _reset_result(self):
        self.result = None
        self.checksum.set("—")
        self.copy_button.configure(state="disabled")
        self.progress["value"] = 0
        self.details.set("Нажмите «Вычислить CRC32»." if self.path.get()
                         else "Выберите файл .hex или .bin для расчёта CRC32.")
        self.status.set("Готово")

    def choose_file(self):
        if self.busy:
            return
        filename = filedialog.askopenfilename(title="Выберите HEX или BIN файл",
                    filetypes=[("HEX и BIN", "*.hex *.bin"), ("Intel HEX", "*.hex"),
                               ("Binary", "*.bin"), ("Все файлы", "*.*")])
        if filename:
            self.path.set(filename)
            self._reset_result()
            self.calculate()

    def _set_busy(self, busy):
        self.busy = busy
        state = "disabled" if busy else "normal"
        self.browse_button.configure(state=state)
        self.calculate_button.configure(state=state)
        self.mode_box.configure(state="disabled" if busy else "readonly")
        self.cancel_button.configure(state="normal" if busy else "disabled")

    def calculate(self):
        if self.busy:
            return
        if not self.path.get():
            self.choose_file()
            return
        path = Path(self.path.get())
        use_hex = self.mode.get() == AUTO_MODE and path.suffix.lower() == ".hex"
        self._reset_result()
        self.cancel_event = threading.Event()
        self._set_busy(True)
        self.status.set("Чтение Intel HEX и расчёт…" if use_hex else "Чтение файла и расчёт…")
        self.details.set("Обработка: {}".format(path.name))
        threading.Thread(target=self._worker, args=(path, use_hex, self.cancel_event), daemon=True).start()

    def _worker(self, path, use_hex, cancel):
        last_report = 0.0

        def progress(fraction):
            nonlocal last_report
            now = time.monotonic()
            if now - last_report >= 0.08 or fraction == 1.0:
                self.events.put(("progress", fraction))
                last_report = now

        try:
            calculate = calculate_intel_hex if use_hex else calculate_raw
            result = calculate(path, cancel, progress)
            self.events.put(("done", (result, use_hex)))
        except CalculationCancelled:
            self.events.put(("cancelled", None))
        except Exception as error:
            self.events.put(("error", str(error)))

    def _poll_events(self):
        if self.closing:
            return
        try:
            while True:
                event, payload = self.events.get_nowait()
                if event == "progress":
                    self.progress["value"] = payload * 100
                else:
                    self._set_busy(False)
                    if event == "done" and not self.cancel_event.is_set():
                        self._show_result(*payload)
                    elif event == "cancelled" or (event == "done" and self.cancel_event.is_set()):
                        self._reset_result()
                        self.status.set("Расчёт отменён")
                    elif event == "error":
                        self._reset_result()
                        self.status.set("Ошибка расчёта")
                        self.details.set(payload)
                        messagebox.showerror("Не удалось вычислить CRC32", payload, parent=self)
        except queue.Empty:
            pass
        self.poll_id = self.after(80, self._poll_events)

    def _show_result(self, result, use_hex):
        self.result = result
        self.checksum.set(result.hexadecimal)
        self.copy_button.configure(state="normal")
        self.progress["value"] = 100
        if use_hex:
            self.details.set(
                "Intel HEX • файл: {} • данные: {}\n"
                "Адреса: 0x{:08X}–0x{:08X} • рассчитано: {}\n"
                "Заполнение промежутков: {} (FF)".format(
                    format_size(result.source_size), format_size(result.data_size),
                    result.start_address, result.end_address,
                    format_size(result.calculated_size), format_size(result.fill_size)))
        else:
            self.details.set("Исходные байты файла • размер: {}\n"
                             "Рассчитано по всем байтам от начала до конца файла.".format(
                                 format_size(result.calculated_size)))
        self.status.set("Расчёт завершён")

    def copy(self):
        if self.result is not None:
            self.clipboard_clear()
            self.clipboard_append(self.result.hexadecimal)
            self.status.set("CRC32 скопирован")

    def cancel(self):
        if self.busy:
            self.cancel_event.set()
            self.cancel_button.configure(state="disabled")
            self.status.set("Отмена…")

    def show_about(self):
        resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        window = tk.Toplevel(self)
        window.title("О программе")
        window.geometry("660x460")
        window.minsize(500, 340)
        window.transient(self)
        frame = ttk.Frame(window, padding=16)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="{} {}".format(APP_NAME, VERSION),
                  font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(frame, text="Автор: {}\n{}\nЛицензия: {}".format(
            AUTHOR, COPYRIGHT, LICENSE)).pack(anchor="w", pady=(8, 12))
        notebook = ttk.Notebook(frame)
        notebook.pack(fill="both", expand=True)
        for title, filename in (("MIT", "LICENSE"), ("Компоненты", "THIRD_PARTY_NOTICES.md")):
            tab = ttk.Frame(notebook)
            text = tk.Text(tab, wrap="word", font=("Consolas", 10), padx=8, pady=8)
            scroll = ttk.Scrollbar(tab, command=text.yview)
            text.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
            text.pack(fill="both", expand=True)
            license_path = resource_root / filename
            content = license_path.read_text(encoding="utf-8") if license_path.exists() else "Текст доступен в репозитории проекта."
            text.insert("1.0", content)
            text.configure(state="disabled")
            notebook.add(tab, text=title)
        ttk.Button(frame, text="Закрыть", command=window.destroy).pack(anchor="e", pady=(12, 0))
        return window

    def close(self):
        self.closing = True
        self.cancel_event.set()
        self.after_cancel(self.poll_id)
        self.destroy()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--self-test":
        from portable_check import run_self_test
        sys.exit(run_self_test(CRC32App, Path(sys.argv[2])))
    CRC32App().mainloop()
