# Installing on Windows

How to download, install and use the Windows installer of the logger. The installer is in the [releases](https://github.com/jongsu-king/band-heater-pid/releases/latest). What was and was not checked for a given version is written in that release's description. The program's features are listed in the [README](../README.en.md#logger).

[한국어](INSTALL.md)

## Requirements

| Item | Details |
|---|---|
| Operating system | Windows 10 or 11, 64-bit. The installer is for x64. On Windows 11 for ARM the installer is allowed to run under x64 emulation, but that was not tried |
| Window component | Microsoft Edge WebView2 Runtime. Part of Windows 11 and of up-to-date Windows 10. If it is missing, the installer says so at the end and can open the Microsoft download page |
| Python | Not needed. Python 3.12 and the packages are inside the install folder |
| Administrator rights | Not needed for the default per-user install. Needed if you choose "all users" |
| Disk | The size of the installed folder given under "Build details" in the release description. Records are stored separately in the Documents folder |
| Board connection | The Arduino Nano's USB. It must show up as a COM port under "Ports (COM & LPT)" in Device Manager. If it does not, install the driver for the board's USB-serial chip (FTDI, CH340, ...) |
| Firmware | The firmware in this repository. With v1.4 or later, program runs move the setpoint with `spt`, which does not write the EEPROM. Older firmware gets `sp`, which stores every change on the board |
| Internet | Not needed to install or run. The program's code does not contact any outside server |

## Installing

The sequence of pages follows from the settings in `packaging/windows/installer.iss`. The automated tests only used silent installs.

1. Download `Band-Heater-Logger-<version>-windows-x64-setup.exe` from the releases. To check the download, see "Checking the download".
2. Double-click it. The file is not code-signed, so "Windows protected your PC" (SmartScreen) appears. Choose `More info`, then `Run anyway`.
3. Choose who to install for. "Current user" (recommended) needs no administrator rights. "All users" asks for them.
4. Accept the licence (MIT).
5. Choose the folder. The default is `C:\Users\<user>\AppData\Local\Programs\Band Heater PID Logger` for the current user, or `C:\Program Files\Band Heater PID Logger` for all users.
6. Choose whether to create a desktop icon. Off by default.
7. Click `Install`. Leave "Launch" ticked and click `Finish` to start the program.

The installer follows the Windows display language: Korean on Korean Windows, English otherwise.

## What gets installed

| What | Where |
|---|---|
| Program | `HeaterLog.exe` and the `_internal` folder (Python runtime, pywebview, pyserial, the page `heater_log.html`, the virtual board `sim\sim_bin.exe`) in the install folder. Full list in `BUILD-INFO.txt` |
| Start menu shortcut | `Band Heater PID Logger`, or `밴드 히터 PID 기록` when installed in Korean |
| Desktop shortcut | Only if chosen; same name |
| Uninstaller | `unins000.exe` in the install folder. Listed as `Band Heater PID Logger` in Settings → Apps |
| Registration | `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\{AED7B226-0390-4D06-9414-BBF97850FE7D}_is1` for the current user, the same path under `HKLM` for all users |

No services, start-up entries, file associations, firewall rules or drivers are installed, and no environment variables are changed.

## First run

1. Start the program first. Opening the port resets the Nano (normal Arduino behaviour), so starting the program during a run turns the heater off. Start the run after the program is up.
2. Plug in the board. The program finds the port itself: it prefers ports whose USB vendor ID is FTDI (0403), CH340 (1A86), CP210x (10C4), Arduino (2341, 2A03) or Prolific (067B), at 115200 baud. With several ports, pick one from the port list in the left panel.
3. Once connected, the line the board sends every second goes to the chart and to the files. Every 3 s the program sends `show` to read the state and settings; `show` does not write the EEPROM.
4. Without a board, click `Practice mode` in the left panel. A virtual board (the firmware compiled as-is for the PC) runs at 30× speed. No real heater is switched. Its temperature curve comes from an arbitrary thermal model, not from the real heater.
5. The language (Korean or English) is chosen from the toolbar. It starts in Korean.

The window opens at 1280 × 880 and cannot be made smaller than 1000 × 700. The page is served only on this computer, at `127.0.0.1` port 8765 (the next ports up to 8784 if that one is taken). It cannot be reached from another computer, and requests that send commands are accepted only with a token that is new on every start. While the program is running it keeps the PC from going to sleep; it does not keep the display on.

The features (toolbar, chart, statistics, response, fit, model, analysis, temperature program, PC alarms, stability check, record list, report, settings, shortcuts) are listed in the [README](../README.en.md#logger).

## Record files

Records go to `밴드히터_기록` in the Documents folder. The location of Documents is asked from Windows, so if it has been moved to OneDrive the folder is created there. `Record folder` in the left panel opens it in Explorer. Practice-mode records go to the `연습` subfolder.

Each record has four files whose names start with `heater_date_time_name`.

| File | Contents |
|---|---|
| `.csv` | One row per second. Columns: `time, elapsed_s, PV_degC, SP_degC, OUT_pct, T1_degC, T2_degC, T3_degC, T4_degC, mode` |
| `_events.txt` | Run, stop, alarms, setting changes, commands sent, markers |
| `_raw.log` | Every line from the board, with the time it arrived |
| `_meta.json` | Experiment name, sample, notes, channel names, firmware version, PID settings at the start, column descriptions |

Saving from the screen adds `_stats.tsv` (range statistics), `_part_*.csv` (a range only), `_graph_*.png` (image) and `_report_*.html` (report) with the same name stem. Program steps, alarm limits and the language are kept in `설정.json` in the record folder. A record with no data rows and no markers is deleted when it is closed.

## Uninstalling, reinstalling, new versions

- Uninstall: Settings → Apps → Installed apps → `Band Heater PID Logger`. The program folder, shortcuts and registration are removed. **The record folder (`밴드히터_기록`) is not touched.**
- Reinstall: run the same installer again; it installs over the same place.
- New version: a newer installer is meant to install over the old one (it empties the old `_internal` folder first). 1.5 is the first release, so an upgrade install has not been tested yet.
- There is no automatic update. New versions appear in this repository's releases.

## Command line

Installer (silent install). The automated tests used all of these except `/ALLUSERS`.

```bat
Band-Heater-Logger-<version>-windows-x64-setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /CURRENTUSER
```

| Switch | Meaning |
|---|---|
| `/VERYSILENT` | Install without showing anything |
| `/SUPPRESSMSGBOXES`, `/NORESTART` | No questions, no restart |
| `/CURRENTUSER` or `/ALLUSERS` | For the current user or for all users |
| `/DIR="path"` | Install folder |
| `/LANG=ko` or `/LANG=en` | Installer language (the shortcut name follows it) |
| `/TASKS=desktopicon` | Also create the desktop icon |
| `/LOG="file"` | Write an install log |

Silent uninstall: `unins000.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART` in the install folder.

Program (`HeaterLog.exe`). The options can be appended to the shortcut's target.

| Option | Meaning |
|---|---|
| `--port COM5` | Use this port (automatic if omitted) |
| `--out "folder"` | Record folder |
| `--name "name"` | Experiment name, added to the file names |
| `--lang ko` or `--lang en` | Language (the last choice if omitted) |
| `--sim 30` | Start with the virtual board at 30× instead of a real board |
| `--http-port 8765` | First port to try for the page |

## Known limitations

- Not code-signed. SmartScreen warns, and some antivirus products block unsigned programs or slow the first start while scanning.
- Notification-centre alerts (stable, program finished, alarm, connection lost) are macOS only. On Windows these are shown on screen, by the alarm sound and in the event log.
- No automatic update.
- Temperature programs and PC alarms work only while the PC and this program are running. If either stops, the board keeps the last setpoint and protection is left to the firmware and hardware (over-temperature cut-off, safety relay, thermostat).
- No tool for uploading the firmware is included. Upload it with the Arduino IDE or avrdude.

## Troubleshooting

| Symptom | What to check |
|---|---|
| "Windows protected your PC" | The file is unsigned. `More info` → `Run anyway` |
| The window is white or empty | The WebView2 Runtime may be missing or broken. Install the Evergreen runtime from Microsoft's WebView2 page |
| It stays at "Looking for the board (plug in the USB cable)" | See whether the board appears under "Ports (COM & LPT)" in Device Manager. If not, install the USB-serial driver or change the cable (charge-only cables do not work). If it does, pick that COM port in the left panel |
| "in use by another program" | Close the Arduino IDE serial monitor or any other terminal program. It also appears if this program is started twice |
| The heater went off when the program started | Opening the port resets the Nano. Start the program first, then the run |
| There is no `Practice mode` button | The build has no virtual board. The installers in the releases include it |
| Where are the records? | Click `Record folder` in the left panel. The path of the current file is shown at the bottom of the window |

If that does not help, open an [issue](https://github.com/jongsu-king/band-heater-pid/issues) with the Windows version, what happened, and the `_events.txt` and `_raw.log` of the record.

## Checking the download

The hash of the downloaded file must equal the value in `SHA256SUMS.txt` (also in the "Files" table of the release description).

```powershell
Get-FileHash .\Band-Heater-Logger-<version>-windows-x64-setup.exe -Algorithm SHA256
```

```bat
certutil -hashfile Band-Heater-Logger-<version>-windows-x64-setup.exe SHA256
```

On macOS or Linux, put both files in one folder and run `shasum -a 256 -c SHA256SUMS.txt`.

## Building it yourself

On a Windows PC, run `build_windows.bat` from the repository. It leaves the program folder and the installer in `dist\`.

| Needed | For |
|---|---|
| [uv](https://docs.astral.sh/uv/) | Fetches Python, PyInstaller, pywebview and pyserial and runs the build |
| g++ (MinGW-w64), optional | Compiles the virtual board for practice mode. Without it the build has no virtual board |
| [Inno Setup 6](https://jrsoftware.org/isinfo.php), optional | Builds the installer. Without it only the program folder is built |

The installer in a release is built by the `Windows installer` workflow on GitHub Actions, which runs the same file. After the build it runs the firmware simulation tests, the self-test with the virtual board, a silent install and uninstall, and an install in Korean; for a `v<version>` tag it uploads the installer, `SHA256SUMS.txt` and `BUILD-INFO.txt` to the release. The release description is the text in `docs/release-notes/<version>.md` with that build's hash, tool versions and test results filled in (`packaging/release_notes.py`).

## Caution

This project switches 220 V. Keep the residual-current breaker, fuse, earth and over-temperature thermostat. Wire with the power unplugged. The alarms in this program do not replace the protection in the board and hardware. MIT licence, provided without warranty.
