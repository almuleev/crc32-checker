# Third-party notices

CRC32 Checker application code is Copyright (c) 2026 Aleksandr Muleev and
licensed under MIT. This license does not replace the licenses of bundled
third-party components.

The portable Windows executable contains these components:

| Component | Purpose | License / notice |
| --- | --- | --- |
| CPython | Embedded Python runtime and standard library | PSF license and historical notices in `licenses/PYTHON.txt` |
| Tcl | Tkinter scripting runtime | Tcl license in `licenses/TCL.txt` |
| Tk | Desktop widgets | Tk license in `licenses/TK.txt` |
| zlib / zlib-ng | CRC32 calculation and decompression | zlib notices in `licenses/ZLIB.txt` and `licenses/ZLIB-NG.txt` |
| PyInstaller bootloader and runtime hooks | Self-contained executable packaging | GPL with bootloader exception; runtime hooks under Apache-2.0, in `licenses/PYINSTALLER.txt` |

The complete notices are included in the source repository, the portable ZIP,
and the executable's bundled resources. The PyInstaller bootloader exception
permits distributing the combined application under the application's license.

Upstream projects: [Python](https://www.python.org/), [Tcl/Tk](https://www.tcl.tk/),
[zlib](https://zlib.net/), [PyInstaller](https://pyinstaller.org/).
