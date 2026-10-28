# -*- coding: utf-8 -*-
"""Fix overlay "Teks kecil" yang diam (tidak ada gerakan/animasi).

Penyebab: mode Cincin punya timer animasi sendiri (Ring, 33 ms), sedangkan Teks kecil cuma
ditulis ulang oleh loop utama tiap 200 ms dengan angka mentah (CPU baru berubah tiap 1 dtk)
-> kelihatan beku, dan ikut mati kalau loop utama kena error.

Sekarang Teks kecil punya timer sendiri (50 ms) yang independen:
  - angka bergerak halus menuju nilai terbaru (bukan loncat),
  - ada bar mini per baris (CPU / GPU / RAM) yang berubah warna mengikuti beban,
  - titik "LIVE" berdenyut sebagai tanda overlay hidup.
Mode Cincin & bagian lain tidak diubah.
"""
import sys

P = "wintweaks.py"
s = open(P, encoding="utf-8").read()


def rep(old, new):
    global s
    if s.count(old) != 1:
        sys.exit(f"GAGAL ({s.count(old)}x ketemu):\n" + old[:100])
    s = s.replace(old, new)


def block(start, end, new):
    """Ganti teks dari penanda `start` sampai sebelum `end`."""
    global s
    a = s.find(start)
    if a < 0:
        sys.exit("GAGAL: penanda tidak ketemu: " + start[:60])
    b = s.find(end, a + len(start))
    if b < 0:
        sys.exit("GAGAL: penanda akhir tidak ketemu: " + end[:60])
    s = s[:a] + new + s[b:]


if "def _ov_tick" in s:
    sys.exit("Sudah pernah dipasang, tidak ada yang diubah.")

import re

# ---------------------------------------------------------------- 1. loop utama tidak lagi menulis baris teks
pat = re.compile(r'^([ \t]+)self\.ov_rows\["\w+"\]\.config\(.*\)[ \t]*\n', re.M)
ms = list(pat.finditer(s))
if not ms:
    sys.exit("GAGAL: baris self.ov_rows[...].config tidak ketemu di refresh_ui")
for i, m in reversed(list(enumerate(ms))):
    s = s[:m.start()] + (m.group(1) + "pass  # baris teks dianimasikan timer sendiri (_ov_tick)\n" if i == 0 else "") + s[m.end():]

# ---------------------------------------------------------------- 2. susunan Teks kecil (cari cabang else di fill_ov)
fa = s.find("    def fill_ov(self, f, s):")
if fa < 0:
    sys.exit("GAGAL: def fill_ov tidak ketemu")
nl = s.index("\n", fa) + 1
em = re.search(r"^        else:[^\n]*\n", s[nl:], re.M)
if not em:
    sys.exit("GAGAL: cabang else (teks kecil) di fill_ov tidak ketemu")
bs = nl + em.start()
ends = [x for x in (s.find("\n        self.ov_msg", bs), s.find("\n    def ", bs)) if x >= 0]
if not ends:
    sys.exit("GAGAL: akhir fill_ov tidak ketemu")
be = min(ends) + 1
BRANCH = '''        else:  # teks kecil: daftar rapi + bar mini, dianimasikan timer sendiri
            bgc = f["bg"]
            fs = max(8, int(11 * s))
            bw, bh = max(40, int(60 * s)), max(5, int(7 * s))
            self.ov_rows, rows = {}, {}
            head = tk.Frame(f, bg=bgc)
            head.pack(fill="x")
            dot = tk.Label(head, text="●", bg=bgc, fg=self.acc[0], font=("Consolas", max(7, int(8 * s))))
            dot.pack(side="left")
            tk.Label(head, text=" LIVE", bg=bgc, fg=DIM,
                     font=("Consolas", max(7, int(8 * s)), "bold")).pack(side="left")
            for name, key in (("CPU", "cpu"), ("GPU", "gpu"), ("RAM", "ram"), ("FPS", "fps")):
                r = tk.Frame(f, bg=bgc)
                r.pack(fill="x")
                tk.Label(r, text=name, width=4, anchor="w", bg=bgc, fg=self.acc[0],
                         font=("Consolas", fs, "bold")).pack(side="left")
                v = tk.Label(r, text="--", width=11, anchor="w", bg=bgc, fg=FG,
                             font=("Consolas", fs, "bold"))
                v.pack(side="left")
                bar = None
                if key != "fps":
                    bar = tk.Canvas(r, width=bw, height=bh, bg=CARD2, highlightthickness=0)
                    bar.pack(side="left", padx=(4, 0))
                    bar.create_rectangle(0, 0, 0, bh, width=0, fill=self.acc[0], tags="b")
                rows[key] = (v, bar)
                self.ov_rows[key] = v
            a = self.ov_anim = {"rows": rows, "cur": {}, "dot": dot, "bw": bw, "bh": bh}
            self.root.after(50, lambda: self._ov_tick(a))
'''
s = s[:bs] + BRANCH + s[be:]
s = s[:nl] + "        self.ov_anim = None  # timer Teks kecil lama berhenti saat dibangun ulang\n" + s[nl:]

# ---------------------------------------------------------------- 3. timer animasi
TICK = '''    def _ov_tick(self, a):
        """Animasi Teks kecil (20x/dtk): angka mengalir halus ke nilai terbaru, bar mini, titik LIVE."""
        if getattr(self, "ov_anim", None) is not a or not self.ov:
            return  # overlay sudah ditutup / dibangun ulang -> timer lama berhenti
        try:
            st = self.stats
            tmp = lambda v: f"{v:.0f}°C" if v else "--"
            fps = st.fps_now()
            tg = {"cpu": st.cpu, "gpu": st.gpu, "ram": st.ram, "fps": fps or 0}
            for k, (lab, bar) in a["rows"].items():
                cur = a["cur"].get(k, 0.0)
                cur += (float(tg[k] or 0) - cur) * .25
                a["cur"][k] = cur
                if k == "cpu":
                    txt = f"{cur:.0f}%  {tmp(st.cpu_t)}"
                elif k == "gpu":
                    txt = f"{cur:.0f}%  {tmp(st.gpu_t)}"
                elif k == "ram":
                    txt = f"{cur:.0f}%"
                else:
                    txt = f"{cur:.0f}" if fps else "--"
                if lab.cget("text") != txt:
                    lab.config(text=txt)
                if bar is not None:
                    bar.coords("b", 0, 0, a["bw"] * max(0.0, min(100.0, cur)) / 100, a["bh"])
                    bar.itemconfig("b", fill=mix(self.acc[0], self.acc[1], min(1, cur / 100)))
            p = (math.sin(time.time() * 4) + 1) / 2  # denyut
            a["dot"].config(fg=mix(DIM, self.acc[0], p))
        except tk.TclError:
            return
        except Exception:
            pass
        self.root.after(50, lambda: self._ov_tick(a))

'''
fa = s.find("    def fill_ov(self, f, s):")
s = s[:fa] + TICK + s[fa:]

open(P, "w", encoding="utf-8").write(s)
print("OK: overlay Teks kecil sekarang beranimasi (timer sendiri)")
