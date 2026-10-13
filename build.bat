@echo off
setlocal
pushd "%~dp0"
py -3.14 -m PyInstaller --noconfirm --clean CRC32Checker.spec
if errorlevel 1 (
    echo.
    echo Build failed. Install Python 3.14 x64 and run:
    echo py -3.14 -m pip install -r requirements-build.txt
    popd
    exit /b 1
)
echo.
echo Portable executable: dist\CRC32Checker.exe
popd
endlocal
