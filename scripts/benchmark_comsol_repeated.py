from __future__ import annotations

import argparse
import csv
import ctypes
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import time
from ctypes import wintypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SOURCE_JOB_ID = "job_20261008025812_2aaa3686"
SOURCE_JOB_DIR = ROOT / "generated" / "execution_jobs" / SOURCE_JOB_ID
SOURCE_BUILDER = SOURCE_JOB_DIR / "generated_build_one_dimensional_heat_conduction.m"
SOURCE_RUNNER = SOURCE_JOB_DIR / f"run_{SOURCE_JOB_ID}.m"


class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", wintypes.DWORD), ("dwHighDateTime", wintypes.DWORD)]


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
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
        ("PrivateUsage", ctypes.c_size_t),
    ]


class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", ctypes.c_long),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]


def _quote_matlab(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").replace("'", "''")


def _filetime_seconds(value: FILETIME) -> float:
    ticks = (int(value.dwHighDateTime) << 32) | int(value.dwLowDateTime)
    return ticks / 10_000_000.0


def _process_snapshot() -> dict[int, tuple[int, str]]:
    if sys.platform != "win32":
        return {}
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    invalid_handle = ctypes.c_void_p(-1).value
    if not snapshot or snapshot == invalid_handle:
        return {}
    processes: dict[int, tuple[int, str]] = {}
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(entry)
    try:
        ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            processes[int(entry.th32ProcessID)] = (
                int(entry.th32ParentProcessID),
                str(entry.szExeFile),
            )
            ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel32.CloseHandle(snapshot)
    return processes


def _find_process_pids(image_names: Iterable[str]) -> set[int]:
    wanted = {name.lower() for name in image_names}
    return {
        pid
        for pid, (_, image_name) in _process_snapshot().items()
        if image_name.lower() in wanted
    }


class WindowsProcessTreeMonitor:
    def __init__(self, pid: int | Iterable[int]) -> None:
        self.root_pids = {int(pid)} if isinstance(pid, int) else {int(value) for value in pid}
        self.peak_working_set = 0
        self.peak_private = 0
        self.peak_process_count = 0
        self.current_working_set = 0
        self.current_private = 0
        self.current_process_count = 0
        self._cpu_by_pid: dict[int, float] = {}

    def _tree_pids(self) -> set[int]:
        if sys.platform != "win32":
            return set(self.root_pids)
        parents = {pid: parent for pid, (parent, _) in _process_snapshot().items()}
        tree = set(self.root_pids)
        changed = True
        while changed:
            changed = False
            for pid, parent in parents.items():
                if parent in tree and pid not in tree:
                    tree.add(pid)
                    changed = True
        return tree

    def sample(self) -> None:
        if sys.platform != "win32":
            return
        kernel32 = ctypes.windll.kernel32
        kernel32.OpenProcess.restype = wintypes.HANDLE
        current_working_set = 0
        current_private = 0
        sampled_count = 0
        for pid in self._tree_pids():
            handle = kernel32.OpenProcess(0x1000 | 0x0010, False, pid)
            if not handle:
                continue
            try:
                counters = PROCESS_MEMORY_COUNTERS_EX()
                counters.cb = ctypes.sizeof(counters)
                if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                    current_working_set += int(counters.WorkingSetSize)
                    current_private += int(counters.PrivateUsage)
                    sampled_count += 1
                creation, exit_time, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
                if kernel32.GetProcessTimes(
                    handle,
                    ctypes.byref(creation),
                    ctypes.byref(exit_time),
                    ctypes.byref(kernel),
                    ctypes.byref(user),
                ):
                    cpu = _filetime_seconds(kernel) + _filetime_seconds(user)
                    self._cpu_by_pid[pid] = max(self._cpu_by_pid.get(pid, 0.0), cpu)
            finally:
                kernel32.CloseHandle(handle)
        self.peak_working_set = max(self.peak_working_set, current_working_set)
        self.peak_private = max(self.peak_private, current_private)
        self.peak_process_count = max(self.peak_process_count, sampled_count)
        self.current_working_set = current_working_set
        self.current_private = current_private
        self.current_process_count = sampled_count

    def cpu_seconds(self) -> float | None:
        return sum(self._cpu_by_pid.values()) if self._cpu_by_pid else None

    def close(self) -> None:
        return


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _runner_for(output_dir: Path, run_id: str) -> str:
    text = SOURCE_RUNNER.read_text(encoding="utf-8")
    source_prefix = _quote_matlab(SOURCE_JOB_DIR)
    target_prefix = _quote_matlab(output_dir)
    text = text.replace(source_prefix, target_prefix)
    text = text.replace(SOURCE_JOB_ID, run_id)
    return text


def _read_temperature(path: Path) -> float:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 1 or rows[0].get("name") != "T_max":
        raise ValueError(f"Unexpected COMSOL result table: {path}")
    return float(rows[0]["value"])


def _run_once(
    *,
    matlab: Path,
    mli: Path,
    host: str,
    port: int,
    output_root: Path,
    index: int,
    timeout_seconds: float,
    mphserver_pids: set[int],
) -> dict[str, object]:
    run_id = f"repeat_{index:02d}"
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_BUILDER, run_dir / SOURCE_BUILDER.name)
    runner = run_dir / f"run_{run_id}.m"
    runner.write_text(_runner_for(run_dir, run_id), encoding="utf-8")
    log_path = run_dir / f"{run_id}.log"
    mph_path = run_dir / f"{run_id}.mph"
    csv_path = run_dir / f"{run_id}_results.csv"
    preview_path = run_dir / f"{run_id}_preview.png"
    for stale_path in (mph_path, csv_path, preview_path):
        stale_path.unlink(missing_ok=True)
    startup = f"addpath('{_quote_matlab(mli)}'); run('{_quote_matlab(runner)}')"
    env = dict(os.environ)
    env["COMSOL_MPH_HOST"] = host
    env["COMSOL_MPH_PORT"] = str(port)
    prefdir = ROOT / "generated" / "matlab_prefs" / "performance_benchmark"
    prefdir.mkdir(parents=True, exist_ok=True)
    env["MATLAB_PREFDIR"] = str(prefdir)

    server_monitor = WindowsProcessTreeMonitor(mphserver_pids)
    server_monitor.sample()
    server_cpu_baseline = server_monitor.cpu_seconds() or 0.0
    server_working_set_baseline = server_monitor.current_working_set
    server_private_baseline = server_monitor.current_private
    flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)
    started = time.perf_counter()
    with log_path.open("w", encoding="utf-8", errors="replace") as log:
        process = subprocess.Popen(
            [str(matlab), "-batch", startup],
            cwd=run_dir,
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            creationflags=flags if sys.platform == "win32" else 0,
        )
        monitor = WindowsProcessTreeMonitor(process.pid)
        combined_peak_working_set = 0
        combined_peak_private = 0
        combined_peak_process_count = 0
        timed_out = False
        while process.poll() is None:
            monitor.sample()
            server_monitor.sample()
            combined_peak_working_set = max(
                combined_peak_working_set,
                monitor.current_working_set + server_monitor.current_working_set,
            )
            combined_peak_private = max(
                combined_peak_private,
                monitor.current_private + server_monitor.current_private,
            )
            combined_peak_process_count = max(
                combined_peak_process_count,
                monitor.current_process_count + server_monitor.current_process_count,
            )
            if time.perf_counter() - started > timeout_seconds:
                timed_out = True
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    process.kill()
                break
            time.sleep(0.25)
        process.wait(timeout=30)
        monitor.sample()
        server_monitor.sample()
        cpu_seconds = monitor.cpu_seconds()
        server_cpu_seconds = max(0.0, (server_monitor.cpu_seconds() or 0.0) - server_cpu_baseline)
        monitor.close()
        server_monitor.close()
    wall_seconds = time.perf_counter() - started
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    passed = (
        not timed_out
        and process.returncode == 0
        and "COMSOL_EXECUTION_SUCCESS" in log_text
        and mph_path.is_file()
        and mph_path.stat().st_size > 0
        and csv_path.is_file()
    )
    temperature = _read_temperature(csv_path) if passed else None
    result = {
        "run": index,
        "run_id": run_id,
        "passed": bool(passed and temperature is not None and abs(temperature - 373.15) < 1e-6),
        "return_code": process.returncode,
        "timed_out": timed_out,
        "wall_seconds": wall_seconds,
        "matlab_process_cpu_seconds": cpu_seconds,
        "matlab_peak_working_set_mb": monitor.peak_working_set / (1024 * 1024),
        "matlab_peak_private_memory_mb": monitor.peak_private / (1024 * 1024),
        "matlab_process_tree_peak_count": monitor.peak_process_count,
        "mphserver_root_pids": sorted(mphserver_pids),
        "mphserver_process_cpu_seconds_during_run": server_cpu_seconds,
        "mphserver_baseline_working_set_mb": server_working_set_baseline / (1024 * 1024),
        "mphserver_peak_working_set_mb": server_monitor.peak_working_set / (1024 * 1024),
        "mphserver_working_set_increase_mb": max(0, server_monitor.peak_working_set - server_working_set_baseline) / (1024 * 1024),
        "mphserver_baseline_private_memory_mb": server_private_baseline / (1024 * 1024),
        "mphserver_peak_private_memory_mb": server_monitor.peak_private / (1024 * 1024),
        "mphserver_private_memory_increase_mb": max(0, server_monitor.peak_private - server_private_baseline) / (1024 * 1024),
        "mphserver_process_tree_peak_count": server_monitor.peak_process_count,
        "combined_matlab_mphserver_cpu_seconds": (cpu_seconds or 0.0) + server_cpu_seconds,
        "combined_peak_working_set_mb": combined_peak_working_set / (1024 * 1024),
        "combined_peak_private_memory_mb": combined_peak_private / (1024 * 1024),
        "combined_incremental_peak_working_set_mb": max(0, combined_peak_working_set - server_working_set_baseline) / (1024 * 1024),
        "combined_incremental_peak_private_memory_mb": max(0, combined_peak_private - server_private_baseline) / (1024 * 1024),
        "combined_process_tree_peak_count": combined_peak_process_count,
        "temperature_max_K": temperature,
        "mph_size_bytes": mph_path.stat().st_size if mph_path.is_file() else 0,
        "log_path": str(log_path.relative_to(ROOT)),
        "mph_path": str(mph_path.relative_to(ROOT)) if mph_path.is_file() else None,
        "csv_path": str(csv_path.relative_to(ROOT)) if csv_path.is_file() else None,
    }
    if not result["passed"]:
        raise RuntimeError(f"COMSOL repeated benchmark run failed: {json.dumps(result, ensure_ascii=False)}")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Repeat one validated COMSOL queue-equivalent solve")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "generated" / "benchmarks" / "comsol_repeat_20261009",
    )
    args = parser.parse_args()
    if args.runs < 3:
        raise ValueError("At least three runs are required for the repeated benchmark")
    config = json.loads((ROOT / "configs" / "execution_node.json").read_text(encoding="utf-8"))
    matlab = Path(config["matlab_executable"])
    mli = Path(config["livelink_matlab_path"])
    if not matlab.is_file() or not mli.is_dir():
        raise FileNotFoundError("Configured MATLAB executable or LiveLink directory is missing")
    mphserver_pids = _find_process_pids({"comsolmphserver.exe"})
    if not mphserver_pids:
        raise RuntimeError("No running comsolmphserver.exe process was found; start the configured server first")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    for index in range(1, args.runs + 1):
        print(f"comsol_benchmark_run={index}/{args.runs} state=starting", flush=True)
        result = _run_once(
            matlab=matlab,
            mli=mli,
            host=str(config.get("comsol_server_host", "localhost")),
            port=int(config.get("comsol_server_port", 2036)),
            output_root=args.output_dir,
            index=index,
            timeout_seconds=args.timeout_seconds,
            mphserver_pids=mphserver_pids,
        )
        results.append(result)
        print(
            f"comsol_benchmark_run={index}/{args.runs} state=completed "
            f"wall_seconds={float(result['wall_seconds']):.3f}",
            flush=True,
        )
    wall = [float(item["wall_seconds"]) for item in results]
    cpu = [float(item["matlab_process_cpu_seconds"]) for item in results if item["matlab_process_cpu_seconds"] is not None]
    server_cpu = [float(item["mphserver_process_cpu_seconds_during_run"]) for item in results]
    combined_cpu = [float(item["combined_matlab_mphserver_cpu_seconds"]) for item in results]
    report = {
        "kind": "repeated_comsol_queue_equivalent_performance_benchmark",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "source_job_id": SOURCE_JOB_ID,
        "scope": "Repeated end-to-end MATLAB LiveLink execution of the validated one-dimensional heat conduction runner",
        "runs": results,
        "summary": {
            "run_count": len(results),
            "all_passed": all(bool(item["passed"]) for item in results),
            "wall_seconds_median": statistics.median(wall),
            "wall_seconds_mean": statistics.fmean(wall),
            "wall_seconds_min": min(wall),
            "wall_seconds_max": max(wall),
            "wall_seconds_p95": _percentile(wall, 0.95),
            "wall_seconds_stdev": statistics.pstdev(wall),
            "matlab_process_cpu_seconds_median": statistics.median(cpu) if cpu else None,
            "matlab_peak_working_set_mb_max": max(float(item["matlab_peak_working_set_mb"]) for item in results),
            "matlab_peak_private_memory_mb_max": max(float(item["matlab_peak_private_memory_mb"]) for item in results),
            "mphserver_process_cpu_seconds_median": statistics.median(server_cpu),
            "mphserver_peak_working_set_mb_max": max(float(item["mphserver_peak_working_set_mb"]) for item in results),
            "mphserver_working_set_increase_mb_max": max(float(item["mphserver_working_set_increase_mb"]) for item in results),
            "mphserver_peak_private_memory_mb_max": max(float(item["mphserver_peak_private_memory_mb"]) for item in results),
            "mphserver_private_memory_increase_mb_max": max(float(item["mphserver_private_memory_increase_mb"]) for item in results),
            "combined_matlab_mphserver_cpu_seconds_median": statistics.median(combined_cpu),
            "combined_peak_working_set_mb_max": max(float(item["combined_peak_working_set_mb"]) for item in results),
            "combined_peak_private_memory_mb_max": max(float(item["combined_peak_private_memory_mb"]) for item in results),
            "combined_incremental_peak_working_set_mb_max": max(float(item["combined_incremental_peak_working_set_mb"]) for item in results),
            "combined_incremental_peak_private_memory_mb_max": max(float(item["combined_incremental_peak_private_memory_mb"]) for item in results),
            "temperature_max_K_values": [item["temperature_max_K"] for item in results],
        },
        "limitations": [
            "Counters include the launched MATLAB process tree and the persistent comsolmphserver process tree; other operating-system processes are excluded.",
            "Persistent-server memory increase is measured relative to the sampled idle baseline immediately before each run.",
            "This benchmark represents one small validated heat-transfer case on one workstation.",
        ],
    }
    report_path = args.output_dir / "repeated_comsol_performance.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"report={report_path}")


if __name__ == "__main__":
    main()
