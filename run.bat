@echo off
setlocal
pushd "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
    python crc32_checker.py
) else (
    py -3 crc32_checker.py
)
if errorlevel 1 (
    echo.
    echo Could not start CRC32 Checker. Install Python 3.8+ with Tcl/Tk support.
    pause
)
popd
endlocal
