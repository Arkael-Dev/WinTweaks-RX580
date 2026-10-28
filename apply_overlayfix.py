# -*- coding: utf-8 -*-
import sys, re

P = "wintweaks.py"
try:
    with open(P, "r", encoding="utf-8") as f:
        s = f.read()
except Exception as e:
    sys.exit(f"Gagal membaca {P}: {e}")

# 1. Perbaikan Audio Rekam Layar (Menambahkan audio capture di ffmpeg gdigrab)
old_rec = '''x264 = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "24"]'''
new_rec = '''x264 = ["-f", "dshow", "-i", "audio=virtual-audio-capturer", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "24", "-c:a", "aac", "-b:a", "192k"]'''
amf_rec = '''amf = ["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "24", "-qp_p", "26"]'''
new_amf = '''amf = ["-f", "dshow", "-i", "audio=virtual-audio-capturer", "-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "24", "-qp_p", "26", "-c:a", "aac", "-b:a", "192k"]'''

if old_rec in s:
    s = s.replace(old_rec, new_rec)
if amf_rec in s:
    s = s.replace(amf_rec, new_amf)

# 2. Ubah Teks Dashboard CPU/GPU & Teks Kecil Menjadi Efek Animasi/Marquee ala Radeon
old_dash_cpu = '''if self.cur_page == "Dashboard":
                self.gpu_lbl.config(text=f"CPU: {L(self.stats.cpu_name)}   |   "
                                         f"GPU: {L(self.stats.gpu_name)}")'''

new_dash_cpu = '''if self.cur_page == "Dashboard":
            full_txt = f"  🔥 ARKAEL RADEON ENGINE ACTIVE  ===  CPU: {L(self.stats.cpu_name)}   |   GPU: {L(self.stats.gpu_name)}  ===  OPTIMIZED FOR PERFORMANCE  "
            curr = getattr(self, "_anim_offset", 0)
            curr = (curr + 1) % len(full_txt)
            self._anim_offset = curr
            anim_display = full_txt[curr:] + full_txt[:curr]
            try:
                self.gpu_lbl.config(text=anim_display)
            except Exception:
                pass'''

if old_dash_cpu in s:
    s = s.replace(old_dash_cpu, new_dash_cpu)

with open(P, "w", encoding="utf-8") as f:
    f.write(s)

print("OK: Perbaikan audio rekaman & animasi Radeon dashboard berhasil diterapkan!")
