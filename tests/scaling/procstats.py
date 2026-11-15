"""Read another process's resident memory and CPU time without psutil."""

from __future__ import annotations

import os
import sys


def _windows(pid: int) -> tuple[int, float]:
    import ctypes
    from ctypes import wintypes

    class _MemCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    handle = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)
    if not handle:
        raise OSError(ctypes.get_last_error(), "OpenProcess failed")
    try:
        counters = _MemCounters()
        counters.cb = ctypes.sizeof(_MemCounters)
        if not psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")
        creation, exit_, kernel, user = (wintypes.FILETIME() for _ in range(4))
        if not kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            raise OSError(ctypes.get_last_error(), "GetProcessTimes failed")

        def _seconds(ft: wintypes.FILETIME) -> float:
            return ((ft.dwHighDateTime << 32) | ft.dwLowDateTime) / 10_000_000.0

        return int(counters.WorkingSetSize), _seconds(kernel) + _seconds(user)
    finally:
        kernel32.CloseHandle(handle)


def _linux(pid: int) -> tuple[int, float]:
    with open(f"/proc/{pid}/status", encoding="utf-8") as status:
        rss_kb = next(
            int(line.split()[1]) for line in status if line.startswith("VmRSS:")
        )
    with open(f"/proc/{pid}/stat", encoding="utf-8") as stat:
        fields = stat.read().rsplit(")", 1)[1].split()
    ticks = os.sysconf("SC_CLK_TCK")
    cpu = (int(fields[11]) + int(fields[12])) / ticks
    return rss_kb * 1024, cpu


def rss_and_cpu(pid: int) -> tuple[int, float]:
    """Return (resident bytes, user+system CPU seconds) for ``pid``."""
    if sys.platform == "win32":
        return _windows(pid)
    return _linux(pid)
