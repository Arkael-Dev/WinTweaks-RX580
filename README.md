# WinTweaks CPU GPU Universal

A modern Windows 10/11 tweak utility with animated UI and four color themes, built for any PC. GPU-specific features (AMD Adrenalin shortcuts, AMF encoder) are enabled automatically on AMD hardware.

## Features

- **Dashboard**: live animated rings for CPU, GPU and RAM usage
- **Tweaks**: power plan, Game Mode, MMCSS and system cleanup, all reversible with Undo
- **CPU/GPU Power**: min/max CPU state, Turbo Boost, PCIe power settings, quick access to AMD Software
- **Record & Screenshot**: choose resolution and FPS, with ffmpeg downloaded automatically on first use
- **Game Profiles**: per-game resolution downscale, tweaks and CPU priority, restored automatically when the game closes
- **Overlay**: two separate windows
  - Stats: CPU/GPU/RAM, temperature and FPS (Ring or compact Text mode)
  - Record: REC/STOP and Screenshot buttons, shown automatically while recording
  - Drag to move, pull the ◢ corner to resize. FPS is read through PresentMon automatically
- **Settings**: Indonesian / English language, Telegram community link

## Download

Get the latest `WinTweaks.exe` from the [Releases](../../releases) page.

## Requirements

- Windows 10 or 11
- Administrator rights (the app requests elevation on launch)

## Build from source

```bash
pip install pyinstaller psutil pillow
pyinstaller --onefile --noconsole --uac-admin --name WinTweaks --icon assets/icon.ico --add-data "assets;assets" wintweaks.py
```

The executable is written to `dist/WinTweaks.exe`. Pushing a tag such as `v1.0.0` also builds it on GitHub Actions and publishes it to Releases.

## Disclaimer

This tool changes system settings. A restore point can be created before applying tweaks, and most changes can be reverted with Undo. Use at your own risk.

## Community

Telegram: https://t.me/arkaelkernel

## License

Released under the [MIT License](LICENSE).

---

Developed by [Arkael-Dev](https://github.com/Arkael-Dev)
