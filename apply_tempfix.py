# -*- coding: utf-8 -*-
"""Fix suhu: GPU AMD (ADL, tanpa install apa pun) + CPU/GPU lewat LibreHardwareMonitor kalau jalan."""
import sys

P = "wintweaks.py"
s = open(P, encoding="utf-8").read()


def rep(old, new):
    global s
    if s.count(old) != 1:
        sys.exit(f"GAGAL ({s.count(old)}x ketemu):\n" + old[:90])
    s = s.replace(old, new)


HELPERS = '''# ---- suhu tambahan: GPU AMD lewat ADL (driver Adrenalin), CPU/GPU lewat LibreHardwareMonitor
_ADL = {}


def _plausible(v):
    return v if v is not None and 10 < v < 125 else None


def _adl_temp():
    """Suhu GPU AMD (Celsius) lewat atiadlxx.dll bawaan driver. None kalau tidak ada."""
    import ctypes
    from ctypes import c_int, c_void_p, c_size_t, byref, CFUNCTYPE, Structure
    if "dll" not in _ADL:
        _ADL["dll"] = None
        try:
            dll = ctypes.WinDLL("atiadlxx.dll")
            libc = ctypes.cdll.msvcrt
            libc.malloc.restype = c_void_p
            libc.malloc.argtypes = [c_size_t]
            cb = CFUNCTYPE(c_void_p, c_int)(lambda n: libc.malloc(n))
            _ADL["cb"] = cb
            if dll.ADL_Main_Control_Create(cb, 1) == 0:
                n = c_int(0)
                dll.ADL_Adapter_NumberOfAdapters_Get(byref(n))
                _ADL["n"] = n.value
                ctx = c_void_p()
                try:
                    if dll.ADL2_Main_Control_Create(cb, 1, byref(ctx)) == 0:
                        _ADL["ctx"] = ctx
                except Exception:
                    pass
                _ADL["dll"] = dll
        except Exception:
            _ADL["dll"] = None
    dll = _ADL["dll"]
    if dll is None:
        return None

    class ADLTemp(Structure):
        _fields_ = [("iSize", c_int), ("iTemperature", c_int)]

    for i in range(_ADL.get("n", 0)):
        try:  # Overdrive5 (GCN/Polaris: RX 4xx/5xx, Vega)
            t = ADLTemp(8, 0)
            if dll.ADL_Overdrive5_Temperature_Get(i, 0, byref(t)) == 0:
                v = _plausible(t.iTemperature / 1000.0)
                if v:
                    return v
        except Exception:
            pass
        try:  # OverdriveN (RDNA, Radeon baru)
            if "ctx" in _ADL:
                tv = c_int(0)
                if dll.ADL2_OverdriveN_Temperature_Get(_ADL["ctx"], i, 1, byref(tv)) == 0:
                    x = tv.value
                    v = _plausible(x / 1000.0 if x > 200 else float(x))
                    if v:
                        return v
        except Exception:
            pass
    return None


def parse_hw_temps(text):
    """'Nama|Nilai;;Nama|Nilai' (dari LibreHardwareMonitor/OpenHardwareMonitor) -> (cpu, gpu)."""
    cpu, gpu = [], []
    for item in text.split(";;"):
        if "|" not in item:
            continue
        name, val = item.rsplit("|", 1)
        try:
            v = _plausible(float(val.strip().replace(",", ".")))
        except ValueError:
            continue
        if v is None:
            continue
        ln = name.lower()
        if "gpu" in ln and "hot" not in ln:
            gpu.append((("core" in ln or "edge" in ln), v))
        elif "cpu" in ln or "package" in ln or "tctl" in ln or "core" in ln:
            cpu.append(("package" in ln or "tctl" in ln or "average" in ln, v))
    pick = lambda L: (sorted(L, key=lambda x: (not x[0], -x[1]))[0][1] if L else None)
    return pick(cpu), pick(gpu)


def _hw_temps():
    _, out = run_ps(
        "$r = foreach ($ns in 'root/LibreHardwareMonitor','root/OpenHardwareMonitor') { "
        "Get-CimInstance -Namespace $ns -ClassName Sensor -ErrorAction SilentlyContinue | "
        "Where-Object { $_.SensorType -eq 'Temperature' } | "
        "ForEach-Object { $_.Name + '|' + $_.Value } }; $r -join ';;'")
    return parse_hw_temps(out)


'''

NEWLOOP = '''    cpu_t2 = gpu_t2 = None
    _cpu_t = _gpu_t = None

    @property
    def cpu_t(self):
        return self._cpu_t if self._cpu_t is not None else self.cpu_t2

    @cpu_t.setter
    def cpu_t(self, v):
        self._cpu_t = v

    @property
    def gpu_t(self):
        return self._gpu_t if self._gpu_t is not None else self.gpu_t2

    @gpu_t.setter
    def gpu_t(self, v):
        self._gpu_t = v

    def _temp2_loop(self):  # sumber suhu cadangan: ADL (AMD) + LibreHardwareMonitor
        n = 0
        hc = hg = None
        while self.on:
            try:
                g = _adl_temp()
            except Exception:
                g = None
            if n % 5 == 0:  # PowerShell berat, cek tiap ~15 dtk
                try:
                    hc, hg = _hw_temps()
                except Exception:
                    hc = hg = None
            n += 1
            self.gpu_t2 = g if g is not None else hg
            self.cpu_t2 = hc
            time.sleep(3)

    def fps_now(self):'''

rep("class Stats:\n", HELPERS + "class Stats:\n")
rep("for fn in (self._gpu_info, self._loop, self._gpu_loop, self._temp_loop):",
    "for fn in (self._gpu_info, self._loop, self._gpu_loop, self._temp_loop, self._temp2_loop):")
rep("    def fps_now(self):", NEWLOOP)

open(P, "w", encoding="utf-8").write(s)
print("OK: suhu GPU AMD + sumber cadangan terpasang")
