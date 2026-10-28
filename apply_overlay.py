# -*- coding: utf-8 -*-
"""Overlay 'Teks kecil' dibuat ala panel HUD (rounded, judul, FPS/CPU/TEMP/GPU/RAM/BAT, grafik)."""
import sys

P = "wintweaks.py"
s = open(P, encoding="utf-8").read()


def rep(old, new):
    global s
    if old not in s:
        sys.exit("GAGAL: potongan kode tidak ketemu:\n" + old[:80])
    s = s.replace(old, new, 1)


# 1. data tambahan di Stats
rep("        self.cpu = self.gpu = self.ram = 0.0\n",
    "        self.cpu = self.gpu = self.ram = 0.0\n"
    "        self.cpu_mhz = self.gpu_mhz = None\n"
    "        self.hist_cpu, self.hist_gpu = [], []\n")

rep("            self.cpu = psutil.cpu_percent(interval=1)\n"
    "            self.ram = psutil.virtual_memory().percent\n",
    "            self.cpu = psutil.cpu_percent(interval=1)\n"
    "            self.ram = psutil.virtual_memory().percent\n"
    "            try:\n"
    "                self.cpu_mhz = psutil.cpu_freq().current\n"
    "            except Exception:\n"
    "                self.cpu_mhz = None\n"
    "            self.hist_cpu = (self.hist_cpu + [self.cpu])[-60:]\n"
    "            self.hist_gpu = (self.hist_gpu + [self.gpu])[-60:]\n")

rep('''                _, out = run(["nvidia-smi", "--query-gpu=temperature.gpu",
                              "--format=csv,noheader,nounits"])
                self.gpu_t = float(out.splitlines()[0].strip())
            except Exception:
                self.gpu_t = None
''', '''                _, out = run(["nvidia-smi", "--query-gpu=temperature.gpu,clocks.gr",
                              "--format=csv,noheader,nounits"])
                a = out.splitlines()[0].split(",")
                self.gpu_t, self.gpu_mhz = float(a[0]), float(a[1])
            except Exception:
                self.gpu_t = self.gpu_mhz = None
''')

# 2. mode teks = jendela transparan (panel digambar di canvas)
rep('self.scales["ov"], self.ov_mode == "Cincin")', 'self.scales["ov"], True)')

# 3. isi overlay mode teks
a = s.index("        else:  # teks kecil: daftar rapi, rata kiri")
b = s.index("        self.ov_msg = tk.Label(f, bg=bgc, fg=DIM", a)
s = s[:a] + '''        else:  # teks kecil: panel HUD (rounded, judul, baris stat, grafik mini)
            try:
                has_bat = psutil.sensors_battery() is not None
            except Exception:
                has_bat = False
            self.ov_s, self.ov_bat = s, has_bat
            n = 5 + (1 if has_bat else 0)
            self.ov_wh = (int(250 * s), int((46 + n * 25 + 62) * s))
            self.ov_cv = tk.Canvas(f, width=self.ov_wh[0], height=self.ov_wh[1], bg=f["bg"],
                                   highlightthickness=0)
            self.ov_cv.pack()
            self.draw_ov()
''' + s[b:]

rep("        bgc = f[\"bg\"]\n        self.ov_rows = None\n",
    "        bgc = f[\"bg\"]\n        self.ov_rows = self.ov_cv = None\n")

# 4. fungsi gambar panel
rep("    # -- overlay rekam (terpisah)\n    def toggle_rov(self):", '''    def draw_ov(self):
        cv = self.ov_cv
        if cv is None:
            return
        st, f, s = self.stats, self.stats.fps_now(), self.ov_s
        W, H = self.ov_wh
        a1, a2, mono = self.acc[0], self.acc[1], "Consolas"
        cv.delete("all")
        r, m = 18 * s, 2
        x1, y1, x2, y2 = m, m, W - m, H - m
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
               x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        cv.create_polygon(pts, smooth=True, fill="#14161b", outline=a1, width=2)
        pad = 18 * s
        cv.create_oval(pad, 17 * s, pad + 8 * s, 25 * s, fill=a1, outline="")
        cv.create_text(pad + 20 * s, 21 * s, text="WINTWEAKS", anchor="w", fill=a1,
                       font=(mono, max(8, int(11 * s)), "bold"))
        ghz = f"{st.cpu_mhz / 1000:.2f}GHz" if st.cpu_mhz else ""
        mhz = f"{st.gpu_mhz:.0f}MHz" if st.gpu_mhz else ""
        tv = st.cpu_t or st.gpu_t
        rows = [("FPS", f"{f}~ fps" if f else "-- fps"),
                ("CPU", f"{st.cpu:.0f}%  {ghz}".strip()),
                ("TEMP", f"{tv:.1f}°C" if tv else "--"),
                ("GPU", f"{st.gpu:.0f}%  {mhz}".strip()),
                ("RAM", f"{st.ram:.0f}%")]
        if self.ov_bat:
            try:
                b = psutil.sensors_battery()
                rows.append(("BAT", f"{b.percent:.0f}%" + ("  ⚡" if b.power_plugged else "")))
            except Exception:
                pass
        fs, y = max(9, int(12 * s)), 46 * s
        for name, val in rows:
            cv.create_text(pad, y, text=name, anchor="w", fill=a1, font=(mono, fs, "bold"))
            cv.create_text(pad + 62 * s, y, text=val, anchor="w", fill=FG, font=(mono, fs, "bold"))
            y += 25 * s
        # grafik mini CPU (a1) + GPU (a2)
        gx1, gx2, gy1, gy2 = pad, W - pad, y + 6 * s, H - 14 * s
        cv.create_line(gx1, gy2, gx2, gy2, fill="#2a2d35")
        for hist, col in ((st.hist_gpu, a2), (st.hist_cpu, a1)):
            if len(hist) > 1:
                dx = (gx2 - gx1) / 59
                xs = gx2 - (len(hist) - 1) * dx
                line = []
                for i, v in enumerate(hist):
                    line += [xs + i * dx, gy2 - (gy2 - gy1) * min(v, 100) / 100]
                cv.create_line(*line, fill=col, width=2, smooth=True)
                cv.create_oval(line[-2] - 3, line[-1] - 3, line[-2] + 3, line[-1] + 3,
                               fill=col, outline="")

    # -- overlay rekam (terpisah)
    def toggle_rov(self):''')

# 5. refresh: gambar ulang panel
rep('''                tmp = lambda v: f"{v:.0f}°C" if v else "--"
                if self.ov_rows:
                    self.ov_rows["cpu"].config(text=f"{st.cpu:.0f}%  {tmp(st.cpu_t)}")
                    self.ov_rows["gpu"].config(text=f"{st.gpu:.0f}%  {tmp(st.gpu_t)}")
                    self.ov_rows["ram"].config(text=f"{st.ram:.0f}%")
                    self.ov_rows["fps"].config(text=f"{f}" if f else "--")
                else:''', '''                tmp = lambda v: f"{v:.0f}°C" if v else "--"
                if self.ov_cv is not None:
                    self.draw_ov()
                else:''')

rep("self.ov_rows = self.ov_fps = self.ov_temp = self.ov_msg = self.ov_rec = self.ov_toast = None",
    "self.ov_rows = self.ov_fps = self.ov_temp = self.ov_msg = self.ov_rec = self.ov_toast = None\n"
    "        self.ov_cv = None")

open(P, "w", encoding="utf-8").write(s)
print("OK: overlay Teks kecil sudah diperbarui")
