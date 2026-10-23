"""About dialog with a native component table and readable license notices."""

import sys
import tkinter as tk
from pathlib import Path
from tkinter import font, ttk

from app_metadata import APP_NAME, AUTHOR, COPYRIGHT, LICENSE, VERSION


COMPONENTS = (
    ("CPython", "Python и стандартная библиотека", "PSF и исторические лицензии", ("PYTHON.txt",)),
    ("Tcl", "Среда выполнения Tkinter", "Лицензия Tcl", ("TCL.txt",)),
    ("Tk", "Графический интерфейс", "Лицензия Tk", ("TK.txt",)),
    ("zlib / zlib-ng", "CRC32 и распаковка данных", "Лицензия zlib", ("ZLIB.txt", "ZLIB-NG.txt")),
    ("PyInstaller", "Загрузчик и упаковка EXE", "GPL с исключением; Apache-2.0", ("PYINSTALLER.txt",)),
)


def _read_notice(path):
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return "Не удалось открыть текст лицензии: {}".format(path.name)


def _license_view(parent):
    frame = ttk.Frame(parent)
    text = tk.Text(frame, wrap="word", font="TkDefaultFont", padx=12, pady=10,
                   relief="flat", borderwidth=0, height=8, width=1,
                   spacing1=2, spacing3=3)
    scroll = ttk.Scrollbar(frame, command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    text.pack(fill="both", expand=True)
    return frame, text


def _set_text(widget, content):
    widget.configure(state="normal")
    widget.delete("1.0", "end")
    widget.insert("1.0", content)
    widget.configure(state="disabled")
    widget.yview_moveto(0)


def show_about_dialog(parent):
    resource_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    window = tk.Toplevel(parent)
    window.title("О программе")
    window.geometry("800x640")
    window.minsize(700, 560)
    window.transient(parent)
    window.bind("<Escape>", lambda event: window.destroy())
    frame = ttk.Frame(window, padding=16)
    frame.pack(fill="both", expand=True)
    ttk.Label(frame, text="{} {}".format(APP_NAME, VERSION),
              font=("Segoe UI", 16, "bold")).pack(anchor="w")
    ttk.Label(frame, text="Автор: {}\n{}\nЛицензия: {}".format(
        AUTHOR, COPYRIGHT, LICENSE)).pack(anchor="w", pady=(8, 12))
    notebook = ttk.Notebook(frame)
    notebook.pack(fill="both", expand=True)
    mit_tab, mit_text = _license_view(notebook)
    _set_text(mit_text, _read_notice(resource_root / "LICENSE"))
    notebook.add(mit_tab, text="MIT")

    components_tab = ttk.Frame(notebook, padding=12)
    components_tab.columnconfigure(0, weight=1)
    components_tab.rowconfigure(3, weight=1)
    intro = ttk.Label(components_tab, text="В portable-версию включены следующие компоненты.",
                      wraplength=640)
    intro.grid(row=0, column=0, sticky="w", pady=(0, 10))
    style = ttk.Style(window)
    style.configure("Components.Treeview", rowheight=font.nametofont("TkDefaultFont").metrics("linespace") + 12)
    table = ttk.Treeview(components_tab, columns=("component", "purpose", "license"),
                         show="headings", selectmode="browse", height=len(COMPONENTS),
                         style="Components.Treeview")
    for name, title, width in (("component", "Компонент", 120),
                               ("purpose", "Назначение", 250),
                               ("license", "Лицензия", 270)):
        table.heading(name, text=title, anchor="w")
        table.column(name, width=width, minwidth=width, anchor="w", stretch=name != "component")
    table.grid(row=1, column=0, sticky="ew")
    for index, (name, purpose, license_name, filenames) in enumerate(COMPONENTS):
        table.insert("", "end", iid=str(index), values=(name, purpose, license_name))
    selected_license = tk.StringVar(window)
    ttk.Label(components_tab, textvariable=selected_license).grid(
        row=2, column=0, sticky="w", pady=(12, 6))
    license_frame, license_text = _license_view(components_tab)
    license_frame.grid(row=3, column=0, sticky="nsew")

    def select_component(event=None):
        selection = table.selection()
        if not selection:
            return
        name, purpose, license_name, filenames = COMPONENTS[int(selection[0])]
        selected_license.set("Текст лицензии — {}".format(name))
        notices = []
        for filename in filenames:
            content = _read_notice(resource_root / "licenses" / filename)
            notices.append((filename + "\n\n" if len(filenames) > 1 else "") + content)
        _set_text(license_text, "\n\n".join(notices))

    table.bind("<<TreeviewSelect>>", select_component)
    table.selection_set("0")
    table.focus("0")
    select_component()
    notebook.add(components_tab, text="Компоненты")
    ttk.Button(frame, text="Закрыть", command=window.destroy).pack(anchor="e", pady=(12, 0))
    return window
