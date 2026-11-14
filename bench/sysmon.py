"""Sample the laptop's temperature, CPU / GPU / NPU load and power, without sudo where possible.

Standard library only, so it runs in any venv (the repo's, Studio's backend's).

| Reading | Source | Needs root? |
|---|---|---|
| Package temperature | thermal zone `x86_pkg_temp` | no |
| NPU busy % | `/sys/class/accel/accel0/device/npu_busy_time_us` | no |
| GPU busy % (render/compute) | `gtidle/idle_residency_ms` of the `gt0-rc` tile | no |
| CPU busy % | `/proc/stat` | no |
| Package power (CPU + GPU + NPU) | RAPL `intel-rapl:0/energy_uj` | yes, unless made readable once: `sudo chmod o+r /sys/class/powercap/intel-rapl:0/energy_uj` (until reboot) |
| Whole-laptop power | battery `power_now`, only while running on battery | no |

    mon = SysMon()
    mon.sample()                 # starts the interval
    ... work ...
    reading = mon.sample()       # averages since the previous sample()

    with SysMonThread(interval_s=0.5) as thread:   # background sampling
        ... work ...
    summary = thread.summary()   # mean / max of every reading

    python3 bench/sysmon.py      # print a reading every second
"""

from __future__ import annotations

import glob
import threading
import time
from pathlib import Path


def _read(path: str | Path) -> str | None:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None


def _read_int(path: str | Path | None) -> int | None:
    value = _read(path) if path else None
    try:
        return int(value) if value is not None else None
    except ValueError:
        return None


def _find_thermal_zone(kind: str) -> str | None:
    for zone in sorted(glob.glob("/sys/class/thermal/thermal_zone*")):
        if _read(f"{zone}/type") == kind:
            return f"{zone}/temp"
    return None


def _find_gpu_idle() -> str | None:
    for gt in sorted(glob.glob("/sys/class/drm/card*/device/tile0/gt*/gtidle")):
        if (_read(f"{gt}/name") or "").endswith("-rc"):  # render/compute, not media
            return f"{gt}/idle_residency_ms"
    return None


class SysMon:
    """Interval readings: each sample() averages over the time since the previous one."""

    def __init__(self) -> None:
        self.temp_path = _find_thermal_zone("x86_pkg_temp")
        self.npu_path = next(iter(glob.glob("/sys/class/accel/accel*/device/npu_busy_time_us")), None)
        self.gpu_idle_path = _find_gpu_idle()
        self.rapl_path = "/sys/class/powercap/intel-rapl:0/energy_uj"
        self.rapl_max = _read_int("/sys/class/powercap/intel-rapl:0/max_energy_range_uj")
        self.rapl_ok = _read_int(self.rapl_path) is not None
        self.battery = next(iter(glob.glob("/sys/class/power_supply/BAT*")), None)
        self._last: dict | None = None

    def _raw(self) -> dict:
        cpu = _read("/proc/stat")
        fields = [int(x) for x in cpu.splitlines()[0].split()[1:]] if cpu else None
        return {
            "t": time.monotonic(),
            "cpu_total": sum(fields) if fields else None,
            "cpu_idle": (fields[3] + fields[4]) if fields else None,  # idle + iowait
            "npu_busy_us": _read_int(self.npu_path),
            "gpu_idle_ms": _read_int(self.gpu_idle_path),
            "rapl_uj": _read_int(self.rapl_path) if self.rapl_ok else None,
        }

    def sample(self) -> dict:
        """Return readings averaged since the previous call (instant values on the first call)."""
        now = self._raw()
        prev, self._last = self._last, now
        reading: dict[str, float | None] = {
            "pkg_temp_c": (_read_int(self.temp_path) or 0) / 1000 if self.temp_path else None,
            "cpu_pct": None,
            "gpu_pct": None,
            "npu_pct": None,
            "pkg_w": None,
            "battery_w": None,
        }
        if self.battery and _read(f"{self.battery}/status") == "Discharging":
            power = _read_int(f"{self.battery}/power_now")
            reading["battery_w"] = power / 1e6 if power is not None else None
        if prev is None:
            return reading
        dt = now["t"] - prev["t"]
        if dt <= 0:
            return reading
        if now["cpu_total"] is not None and prev["cpu_total"] is not None:
            total = now["cpu_total"] - prev["cpu_total"]
            idle = now["cpu_idle"] - prev["cpu_idle"]
            reading["cpu_pct"] = 100.0 * (1 - idle / total) if total > 0 else None
        if now["gpu_idle_ms"] is not None and prev["gpu_idle_ms"] is not None:
            idle_s = (now["gpu_idle_ms"] - prev["gpu_idle_ms"]) / 1000
            reading["gpu_pct"] = max(0.0, min(100.0, 100.0 * (1 - idle_s / dt)))
        if now["npu_busy_us"] is not None and prev["npu_busy_us"] is not None:
            busy_s = (now["npu_busy_us"] - prev["npu_busy_us"]) / 1e6
            reading["npu_pct"] = max(0.0, min(100.0, 100.0 * busy_s / dt))
        if now["rapl_uj"] is not None and prev["rapl_uj"] is not None:
            delta = now["rapl_uj"] - prev["rapl_uj"]
            if delta < 0 and self.rapl_max:
                delta += self.rapl_max
            reading["pkg_w"] = delta / 1e6 / dt
        return reading

    def describe(self) -> str:
        parts = [
            f"temp {'yes' if self.temp_path else 'no'}",
            f"NPU {'yes' if self.npu_path else 'no'}",
            f"GPU {'yes' if self.gpu_idle_path else 'no'}",
            "package power " + ("yes" if self.rapl_ok else "no (needs: sudo chmod o+r " + self.rapl_path + ")"),
            "battery power " + ("only while unplugged" if self.battery else "no"),
        ]
        return ", ".join(parts)


class SysMonThread:
    """Samples SysMon in the background; summary() gives mean and max of every reading."""

    def __init__(self, interval_s: float = 0.5) -> None:
        self.mon = SysMon()
        self.interval_s = interval_s
        self.samples: list[dict] = []
        self.latest: dict = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True, name="sysmon")

    def _run(self) -> None:
        self.mon.sample()
        while not self._stop.wait(self.interval_s):
            reading = self.mon.sample()
            self.latest = reading
            self.samples.append(reading)

    def start(self) -> SysMonThread:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        if self._thread.is_alive():
            self._thread.join(timeout=2)

    def __enter__(self) -> SysMonThread:
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.stop()

    def summary(self) -> dict[str, float | None]:
        out: dict[str, float | None] = {}
        keys = ("pkg_temp_c", "cpu_pct", "gpu_pct", "npu_pct", "pkg_w", "battery_w")
        for key in keys:
            values = [s[key] for s in self.samples if s.get(key) is not None]
            out[f"{key}_mean"] = sum(values) / len(values) if values else None
            out[f"{key}_max"] = max(values) if values else None
        return out


def fmt(reading: dict) -> str:
    def f(key: str, unit: str, digits: int = 0) -> str:
        value = reading.get(key)
        return f"{value:.{digits}f}{unit}" if value is not None else "-"

    return (f"temp {f('pkg_temp_c', '°C')}  CPU {f('cpu_pct', '%')}  GPU {f('gpu_pct', '%')}  "
            f"NPU {f('npu_pct', '%')}  package {f('pkg_w', ' W', 1)}  battery {f('battery_w', ' W', 1)}")


if __name__ == "__main__":
    mon = SysMon()
    print("Available:", mon.describe())
    mon.sample()
    try:
        while True:
            time.sleep(1)
            print(fmt(mon.sample()))
    except KeyboardInterrupt:
        pass
