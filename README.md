# WinTweaks-RX580

Aplikasi tweak Windows 10/11 dengan GUI bertema AMD Radeon (merah/hitam),
dibuat khusus untuk PC **Intel i3 Gen 8 + AMD RX 580**, tapi tweak umum
(power plan, Game Mode, bersih-bersih) tetap aman untuk PC lain.

## Fitur

**Performa & Power Plan**
- Power plan Ultimate Performance
- Kurangi efek visual (transparansi, delay menu)
- Hilangkan delay startup aplikasi

**Gaming**
- Game Mode otomatis
- Matikan Xbox Game DVR / perekaman latar
- Prioritas CPU/GPU untuk game (MMCSS)
- Matikan akselerasi mouse (opsional)
- Shortcut buka AMD Software (Adrenalin) untuk GPU Scaling / Image
  Sharpening per-game — RX 580 (Polaris) tidak mendukung RSR, jadi ini
  cara resmi paling stabil untuk downscale/sharpen per-game
- Shortcut buka panel Audio Enhancement (Loudness Equalization) sebagai
  equalizer ringan yang stabil

**Sistem (bisa di-undo)**
- Matikan Windows Update
- Matikan Defender real-time protection **sementara** untuk sesi gaming
  (lewat `Set-MpPreference`, API resmi Microsoft — bukan bypass permanen,
  dan langsung ditolak otomatis kalau Tamper Protection aktif)

**Bersih-bersih** (tidak bisa di-undo)
- Temp user & Windows, shader cache DirectX/AMD, Recycle Bin, cache
  Windows Update

Semua tweak registry, power plan, Windows Update, dan Defender disimpan
nilai aslinya di `%APPDATA%\WinTweaks\state.json` dan bisa dikembalikan
penuh lewat tombol **Kembalikan (Undo)**.

## Kenapa tidak ada "matikan antivirus permanen"?

Mematikan proteksi antivirus secara permanen (termasuk menonaktifkan
Tamper Protection lewat kode, menghapus definisi, atau memblokir layanan
Defender secara diam-diam) adalah teknik yang sama persis dipakai malware
untuk bertahan di sistem. Fitur yang tersedia di sini hanya mematikan
real-time protection **sementara** lewat API resmi Windows, dan selalu
bisa dinyalakan lagi lewat tombol Undo.

## Build manual

```powershell
pip install pyinstaller
pyinstaller --onefile --noconsole --uac-admin --name WinTweaks ^
  --icon assets/icon.ico --add-data "assets;assets" wintweaks.py
```

Hasil ada di `dist\WinTweaks.exe`.

## Build otomatis (GitHub Actions)

Push ke branch `main` akan otomatis membuild `WinTweaks.exe` lewat
`.github/workflows/build.yml`. Hasil build bisa diunduh di tab
**Actions > (run terbaru) > Artifacts**. Push tag (misalnya `v1.0.0`)
untuk otomatis membuat GitHub Release berisi `WinTweaks.exe`.

## Menjalankan dari source

```powershell
pip install pyinstaller  # opsional, hanya untuk build
python wintweaks.py
```

Aplikasi akan minta izin Administrator otomatis (UAC) karena sebagian
besar tweak butuh akses registry HKLM dan kontrol service.
