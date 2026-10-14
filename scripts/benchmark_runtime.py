from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from comsol_small_model.surrogate_runtime import (  # noqa: E402
    latest_validated_thermal_model,
    predict_validated_surrogate,
)


DEFAULT_INPUTS = {
    "L_m": 0.06,
    "W_m": 0.0225,
    "k_W_mK": 40.0,
    "T_hot_K": 363.15,
    "T_cold_K": 288.15,
}


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _summary(samples_seconds: list[float]) -> dict[str, float | int]:
    samples_ms = [value * 1000.0 for value in samples_seconds]
    return {
        "iterations": len(samples_ms),
        "median_ms": statistics.median(samples_ms),
        "mean_ms": statistics.fmean(samples_ms),
        "p95_ms": _percentile(samples_ms, 0.95),
        "min_ms": min(samples_ms),
        "max_ms": max(samples_ms),
        "stdev_ms": statistics.pstdev(samples_ms),
    }


def _read_comsol_duration(job_id: str) -> float:
    index_path = ROOT / "generated" / "execution_jobs" / "artifact_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8"))
    for job in index.get("records", index.get("jobs", [])):
        if job.get("job_id") != job_id:
            continue
        mph = job.get("mph", {})
        if isinstance(mph, dict) and mph.get("execution_duration_seconds") is not None:
            return float(mph["execution_duration_seconds"])
        for artifact in job.get("artifacts", []):
            value = artifact.get("execution_duration_seconds")
            if value is not None:
                return float(value)
    raise ValueError(f"No execution duration found for {job_id}")


def _http_prediction(endpoint: str, payload: bytes) -> dict[str, object]:
    request = Request(
        f"{endpoint.rstrip('/')}/api/surrogates/thermal-plate/predict",
        data=payload,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _package_versions() -> dict[str, str]:
    names = ["joblib", "numpy", "pandas", "scikit-learn", "scipy", "pypdf"]
    result: dict[str, str] = {}
    for name in names:
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = "not-installed"
    return result


def _write_markdown(report: dict[str, object], path: Path) -> None:
    direct = report["direct_prediction"]
    http = report.get("http_prediction")
    lines = [
        "# Runtime performance benchmark",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "| Measure | Result |",
        "|---|---:|",
        f"| COMSOL queue-equivalent solve median | {report['comsol_reference']['duration_seconds']:.3f} s |",
        f"| Direct surrogate median | {direct['median_ms']:.3f} ms |",
        f"| Direct surrogate p95 | {direct['p95_ms']:.3f} ms |",
        f"| Direct surrogate iterations | {direct['iterations']} |",
        f"| Direct speedup vs COMSOL | {report['speedup_vs_comsol']['direct_median_times']:.0f} x |",
    ]
    if isinstance(http, dict):
        lines.extend(
            [
                f"| Local HTTP median | {http['median_ms']:.3f} ms |",
                f"| Local HTTP p95 | {http['p95_ms']:.3f} ms |",
                f"| Local HTTP iterations | {http['iterations']} |",
                f"| HTTP speedup vs COMSOL | {report['speedup_vs_comsol']['http_median_times']:.0f} x |",
            ]
        )
    lines.extend(
        [
            "",
            "The COMSOL value is the median of repeated queue-equivalent LiveLink solves. "
            "The surrogate values are repeated measurements on the same workstation. "
            "The speedup therefore describes this fixed local case and is not a general COMSOL performance claim.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark validated surrogate prediction latency")
    parser.add_argument("--iterations", type=int, default=300)
    parser.add_argument("--http-iterations", type=int, default=60)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8880")
    parser.add_argument("--job-id", default="job_20261008025812_2aaa3686")
    parser.add_argument(
        "--comsol-repeat-report",
        type=Path,
        default=ROOT / "generated" / "benchmarks" / "comsol_repeat_20261009" / "repeated_comsol_performance.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "generated" / "benchmarks" / "runtime_performance_20261009.json",
    )
    args = parser.parse_args()
    if args.iterations < 10 or args.http_iterations < 0:
        raise ValueError("iterations must be at least 10 and http-iterations cannot be negative")

    model_path = latest_validated_thermal_model(ROOT / "generated" / "execution_jobs")
    for _ in range(10):
        warmup = predict_validated_surrogate(model_path, DEFAULT_INPUTS)
        if not warmup.get("ok"):
            raise RuntimeError(f"Warmup prediction failed: {warmup}")

    tracemalloc.start()
    cpu_start = time.process_time()
    direct_samples: list[float] = []
    last_prediction: dict[str, object] = {}
    for _ in range(args.iterations):
        started = time.perf_counter()
        last_prediction = predict_validated_surrogate(model_path, DEFAULT_INPUTS)
        direct_samples.append(time.perf_counter() - started)
    cpu_seconds = time.process_time() - cpu_start
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    direct = _summary(direct_samples)
    direct["process_cpu_seconds_for_batch"] = cpu_seconds
    direct["python_allocation_peak_mb"] = peak_bytes / (1024 * 1024)

    http: dict[str, float | int] | None = None
    if args.http_iterations:
        payload = json.dumps(DEFAULT_INPUTS).encode("utf-8")
        first_http = _http_prediction(args.endpoint, payload)
        if not first_http.get("ok"):
            raise RuntimeError(f"HTTP warmup prediction failed: {first_http}")
        http_samples: list[float] = []
        for _ in range(args.http_iterations):
            started = time.perf_counter()
            response = _http_prediction(args.endpoint, payload)
            http_samples.append(time.perf_counter() - started)
            if not response.get("ok"):
                raise RuntimeError(f"HTTP benchmark prediction failed: {response}")
        http = _summary(http_samples)

    if args.comsol_repeat_report.is_file():
        repeated = json.loads(args.comsol_repeat_report.read_text(encoding="utf-8"))
        repeated_summary = repeated.get("summary", {})
        comsol_seconds = float(repeated_summary["wall_seconds_median"])
        comsol_reference: dict[str, object] = {
            "kind": "repeated_queue_equivalent_livelink_solve",
            "source_job_id": args.job_id,
            "report_path": str(args.comsol_repeat_report.relative_to(ROOT)),
            "duration_seconds": comsol_seconds,
            "measurement_count": int(repeated_summary["run_count"]),
            "minimum_seconds": float(repeated_summary["wall_seconds_min"]),
            "maximum_seconds": float(repeated_summary["wall_seconds_max"]),
            "p95_seconds": float(repeated_summary["wall_seconds_p95"]),
            "matlab_peak_working_set_mb_max": float(repeated_summary["matlab_peak_working_set_mb_max"]),
            "matlab_peak_private_memory_mb_max": float(repeated_summary["matlab_peak_private_memory_mb_max"]),
            "mphserver_peak_working_set_mb_max": float(repeated_summary["mphserver_peak_working_set_mb_max"]),
            "mphserver_peak_private_memory_mb_max": float(repeated_summary["mphserver_peak_private_memory_mb_max"]),
            "combined_peak_working_set_mb_max": float(repeated_summary["combined_peak_working_set_mb_max"]),
            "combined_peak_private_memory_mb_max": float(repeated_summary["combined_peak_private_memory_mb_max"]),
            "combined_matlab_mphserver_cpu_seconds_median": float(repeated_summary["combined_matlab_mphserver_cpu_seconds_median"]),
            "limitation": "One small validated heat-transfer case on one workstation; operating-system processes outside MATLAB and mphserver are excluded.",
        }
    else:
        comsol_seconds = _read_comsol_duration(args.job_id)
        comsol_reference = {
            "kind": "single_recorded_queue_solve",
            "job_id": args.job_id,
            "duration_seconds": comsol_seconds,
            "measurement_count": 1,
            "limitation": "Single recorded queue solve; used as a local functional reference.",
        }
    speedup: dict[str, float] = {
        "direct_median_times": comsol_seconds / (float(direct["median_ms"]) / 1000.0),
    }
    if http:
        speedup["http_median_times"] = comsol_seconds / (float(http["median_ms"]) / 1000.0)

    report: dict[str, object] = {
        "kind": "local_runtime_performance_benchmark",
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(),
        "scope": "fixed validated two-dimensional thermal-plate surrogate on one Windows workstation",
        "machine": {
            "platform": platform.platform(),
            "processor": platform.processor(),
            "logical_cpu_count": os.cpu_count(),
            "python": sys.version,
            "packages": _package_versions(),
        },
        "model_path": str(model_path.relative_to(ROOT)),
        "inputs": DEFAULT_INPUTS,
        "prediction": last_prediction.get("prediction"),
        "direct_prediction": direct,
        "http_prediction": http,
        "comsol_reference": comsol_reference,
        "speedup_vs_comsol": speedup,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = args.output.with_suffix(".md")
    _write_markdown(report, markdown_path)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"json={args.output}")
    print(f"markdown={markdown_path}")


if __name__ == "__main__":
    main()
