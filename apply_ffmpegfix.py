# -*- coding: utf-8 -*-
"""Fix unduh ffmpeg: ada progress, timeout, mirror GitHub dulu, bisa gagal dengan pesan jelas."""
import sys

P = "wintweaks.py"
s = open(P, encoding="utf-8").read()
a = s.index("    def get_ffmpeg(self):")
b = s.index("    def p_rec(self, b):", a)

NEW = '''    def _dl(self, url, dest):
        req = urllib.request.Request(url, headers={"User-Agent": "WinTweaks"})
        with urllib.request.urlopen(req, timeout=20) as r, open(dest, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            got, last = 0, 0.0
            while True:
                chunk = r.read(256 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if time.time() - last > 1:
                    last = time.time()
                    pct = f" ({got * 100 // total}%)" if total else ""
                    self.log(f"Mengunduh ffmpeg... {got // 1048576} MB{pct}")
        if total and got < total:
            raise IOError("unduhan terputus")

    def ff_urls(self):  # mirror GitHub dulu (cepat & stabil), gyan.dev cadangan
        urls = []
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/GyanD/codexffmpeg/releases/latest",
                headers={"User-Agent": "WinTweaks"})
            with urllib.request.urlopen(req, timeout=15) as r:
                for a in json.load(r)["assets"]:
                    if a["name"].endswith("essentials_build.zip"):
                        urls.append(a["browser_download_url"])
        except Exception:
            pass
        urls.append(FF_URL)
        return urls

    def get_ffmpeg(self):  # ffmpeg otomatis diunduh sekali, tanpa setup manual
        if self.ffmpeg():
            return self.ffmpeg()
        self.log("Mengunduh ffmpeg otomatis (sekali saja)...")
        os.makedirs(FF_DIR, exist_ok=True)
        zp = os.path.join(FF_DIR, "ff.zip")
        err = None
        for url in self.ff_urls():
            try:
                self._dl(url, zp)
                with zipfile.ZipFile(zp) as z:
                    for n in z.namelist():
                        if n.endswith("bin/ffmpeg.exe"):
                            with z.open(n) as src, open(os.path.join(FF_DIR, "ffmpeg.exe"), "wb") as d:
                                shutil.copyfileobj(src, d)
                if self.ffmpeg():
                    break
                err = "ffmpeg.exe tidak ada di dalam zip"
            except Exception as e:
                err = str(e)
                self.log(f"Unduh gagal ({err}), coba sumber lain...")
            finally:
                try:
                    os.remove(zp)
                except OSError:
                    pass
        if not self.ffmpeg():
            self.log(f"ffmpeg gagal diunduh ({err}). Manual: taruh ffmpeg.exe di folder {FF_DIR}")
            raise RuntimeError("ffmpeg tidak tersedia")
        return self.ffmpeg()

'''
s = s[:a] + NEW + s[b:]
open(P, "w", encoding="utf-8").write(s)
print("OK: unduh ffmpeg diperbaiki")
