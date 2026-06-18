@echo off
REM Build Lookupper.exe (run on Windows from the project folder).
REM Use "py -m ..." because python/pyinstaller may not be on PATH -
REM only the py launcher is available on this machine.

REM pick a working Python launcher: prefer py, fall back to python
where py >nul 2>nul && (set PY=py) || (set PY=python)

echo == Installing PyInstaller ==
%PY% -m pip install --upgrade pyinstaller
if errorlevel 1 (
  echo [ERROR] Could not install PyInstaller. Aborted.
  pause & exit /b 1
)

set ICON_ARG=
if exist assets\icon.ico set ICON_ARG=--icon assets\icon.ico

echo == Building exe ==
%PY% -m PyInstaller --noconfirm --windowed --name Lookupper %ICON_ARG% --collect-all winrt --hidden-import winrt.windows.media.ocr --hidden-import winrt.windows.globalization --hidden-import winrt.windows.graphics.imaging --hidden-import winrt.windows.storage.streams --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 --hidden-import pyttsx3.drivers --hidden-import pyttsx3.drivers.sapi5 main.py
if errorlevel 1 (
  echo [ERROR] Build failed. See the messages above.
  pause & exit /b 1
)

REM copy assets/ (icons, svg) next to the exe - app_dir() looks for them there
xcopy /E /I /Y assets dist\Lookupper\assets

echo.
if exist dist\Lookupper\Lookupper.exe (
  echo ==========================================================
  echo Done. RUN THIS FILE:  dist\Lookupper\Lookupper.exe
  echo Do NOT run anything inside the build\ folder - those are
  echo intermediate files and will fail with "Failed to load Python DLL".
  echo The data\ folder with your words is created next to the exe on first run.
  echo ==========================================================
  REM open the correct folder so you don't end up in build\ by mistake
  start "" explorer "%CD%\dist\Lookupper"
) else (
  echo [ERROR] Lookupper.exe was not produced - the build did not succeed.
)
pause
