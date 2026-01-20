#!/usr/bin/env python3
"""
Benchmark script for running comex on all .c files in the projects folder.
Tracks CPU, RAM, and other resource usage for each comex invocation.
"""

import csv
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import psutil


@dataclass
class ResourceMetrics:
    """Stores resource metrics for a single comex run."""
    file_path: str
    start_time: str = ""
    end_time: str = ""
    duration_seconds: float = 0.0
    exit_code: int = 0

    # Memory metrics (in MB)
    peak_rss_mb: float = 0.0
    avg_rss_mb: float = 0.0
    peak_vms_mb: float = 0.0

    # CPU metrics
    peak_cpu_percent: float = 0.0
    avg_cpu_percent: float = 0.0

    # I/O metrics (bytes)
    read_bytes: int = 0
    write_bytes: int = 0

    # Additional info
    num_samples: int = 0
    error_message: str = ""

    # Internal tracking
    _rss_samples: list = field(default_factory=list, repr=False)
    _cpu_samples: list = field(default_factory=list, repr=False)


class ResourceMonitor:
    """Monitors resource usage of a subprocess."""

    def __init__(self, pid: int, sample_interval_ms: int = 50):
        self.pid = pid
        self.sample_interval = sample_interval_ms / 1000.0
        self.metrics = ResourceMetrics(file_path="")
        self._stop_event = threading.Event()
        self._monitor_thread = None
        self._process = None

    def start(self):
        """Start monitoring the process."""
        try:
            self._process = psutil.Process(self.pid)
            # Initialize I/O counters if available
            try:
                io_counters = self._process.io_counters()
                self._initial_read_bytes = io_counters.read_bytes
                self._initial_write_bytes = io_counters.write_bytes
            except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                self._initial_read_bytes = 0
                self._initial_write_bytes = 0

            self._monitor_thread = threading.Thread(target=self._monitor_loop)
            self._monitor_thread.daemon = True
            self._monitor_thread.start()
        except psutil.NoSuchProcess:
            pass

    def stop(self):
        """Stop monitoring and finalize metrics."""
        self._stop_event.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        self._finalize_metrics()

    def _monitor_loop(self):
        """Main monitoring loop - runs in separate thread."""
        while not self._stop_event.is_set():
            try:
                if not self._process.is_running():
                    break

                # Sample memory
                mem_info = self._process.memory_info()
                rss_mb = mem_info.rss / (1024 * 1024)
                vms_mb = mem_info.vms / (1024 * 1024)
                self.metrics._rss_samples.append(rss_mb)
                self.metrics.peak_vms_mb = max(self.metrics.peak_vms_mb, vms_mb)

                # Sample CPU
                cpu_percent = self._process.cpu_percent(interval=None)
                self.metrics._cpu_samples.append(cpu_percent)

                # Sample I/O
                try:
                    io_counters = self._process.io_counters()
                    self.metrics.read_bytes = io_counters.read_bytes - self._initial_read_bytes
                    self.metrics.write_bytes = io_counters.write_bytes - self._initial_write_bytes
                except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
                    pass

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break

            time.sleep(self.sample_interval)

    def _finalize_metrics(self):
        """Calculate final metrics from samples."""
        if self.metrics._rss_samples:
            self.metrics.peak_rss_mb = max(self.metrics._rss_samples)
            self.metrics.avg_rss_mb = sum(self.metrics._rss_samples) / len(self.metrics._rss_samples)
            self.metrics.num_samples = len(self.metrics._rss_samples)

        if self.metrics._cpu_samples:
            self.metrics.peak_cpu_percent = max(self.metrics._cpu_samples)
            self.metrics.avg_cpu_percent = sum(self.metrics._cpu_samples) / len(self.metrics._cpu_samples)


def run_comex_with_monitoring(c_file: Path, sample_interval_ms: int = 50) -> ResourceMetrics:
    """Run comex on a single .c file and monitor resource usage."""

    metrics = ResourceMetrics(file_path=str(c_file))
    metrics.start_time = datetime.now().isoformat()

    cmd = [
        "comex",
        "--lang", "c",
        "--code-file", str(c_file),
        "--graphs", "cfg,dfg,ast"
    ]

    start = time.perf_counter()

    try:
        # Start the subprocess
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        # Start monitoring
        monitor = ResourceMonitor(process.pid, sample_interval_ms)
        monitor.start()

        # Wait for process to complete
        stdout, stderr = process.communicate()

        # Stop monitoring
        monitor.stop()

        # Copy metrics from monitor
        metrics.peak_rss_mb = monitor.metrics.peak_rss_mb
        metrics.avg_rss_mb = monitor.metrics.avg_rss_mb
        metrics.peak_vms_mb = monitor.metrics.peak_vms_mb
        metrics.peak_cpu_percent = monitor.metrics.peak_cpu_percent
        metrics.avg_cpu_percent = monitor.metrics.avg_cpu_percent
        metrics.read_bytes = monitor.metrics.read_bytes
        metrics.write_bytes = monitor.metrics.write_bytes
        metrics.num_samples = monitor.metrics.num_samples

        metrics.exit_code = process.returncode
        if process.returncode != 0:
            metrics.error_message = stderr.decode('utf-8', errors='replace').strip()[:500]

    except Exception as e:
        metrics.error_message = str(e)[:500]
        metrics.exit_code = -1

    metrics.end_time = datetime.now().isoformat()
    metrics.duration_seconds = time.perf_counter() - start

    return metrics


def find_c_files(projects_dir: Path) -> list[Path]:
    """Find all .c files in the projects directory."""
    if not projects_dir.exists():
        print(f"Error: Directory '{projects_dir}' does not exist")
        sys.exit(1)

    c_files = sorted(projects_dir.rglob("*.c"))
    return c_files


def write_csv(metrics_list: list[ResourceMetrics], output_file: Path):
    """Write metrics to CSV file."""
    fieldnames = [
        'file_path',
        'start_time',
        'end_time',
        'duration_seconds',
        'exit_code',
        'peak_rss_mb',
        'avg_rss_mb',
        'peak_vms_mb',
        'peak_cpu_percent',
        'avg_cpu_percent',
        'read_bytes',
        'write_bytes',
        'num_samples',
        'error_message'
    ]

    with open(output_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for m in metrics_list:
            writer.writerow({
                'file_path': m.file_path,
                'start_time': m.start_time,
                'end_time': m.end_time,
                'duration_seconds': round(m.duration_seconds, 3),
                'exit_code': m.exit_code,
                'peak_rss_mb': round(m.peak_rss_mb, 2),
                'avg_rss_mb': round(m.avg_rss_mb, 2),
                'peak_vms_mb': round(m.peak_vms_mb, 2),
                'peak_cpu_percent': round(m.peak_cpu_percent, 2),
                'avg_cpu_percent': round(m.avg_cpu_percent, 2),
                'read_bytes': m.read_bytes,
                'write_bytes': m.write_bytes,
                'num_samples': m.num_samples,
                'error_message': m.error_message
            })


def main():
    # Configuration
    script_dir = Path(__file__).parent
    projects_dir = script_dir / "projects"
    output_file = script_dir / f"comex_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    sample_interval_ms = 50

    print(f"Looking for .c files in: {projects_dir}")
    c_files = find_c_files(projects_dir)

    if not c_files:
        print("No .c files found in the projects directory")
        sys.exit(1)

    print(f"Found {len(c_files)} .c files")
    print(f"Sample interval: {sample_interval_ms}ms")
    print(f"Output will be saved to: {output_file}")
    print("-" * 60)

    all_metrics = []

    for i, c_file in enumerate(c_files, 1):
        print(f"[{i}/{len(c_files)}] Processing: {c_file.name}...", end=" ", flush=True)

        metrics = run_comex_with_monitoring(c_file, sample_interval_ms)
        all_metrics.append(metrics)

        status = "OK" if metrics.exit_code == 0 else f"FAILED (exit={metrics.exit_code})"
        print(f"{status} | {metrics.duration_seconds:.2f}s | Peak RAM: {metrics.peak_rss_mb:.1f}MB | Peak CPU: {metrics.peak_cpu_percent:.1f}%")

    # Write results
    write_csv(all_metrics, output_file)
    print("-" * 60)
    print(f"Results saved to: {output_file}")

    # Summary statistics
    successful = [m for m in all_metrics if m.exit_code == 0]
    failed = [m for m in all_metrics if m.exit_code != 0]

    print(f"\nSummary:")
    print(f"  Total files: {len(all_metrics)}")
    print(f"  Successful: {len(successful)}")
    print(f"  Failed: {len(failed)}")

    if successful:
        total_duration = sum(m.duration_seconds for m in successful)
        avg_duration = total_duration / len(successful)
        max_ram = max(m.peak_rss_mb for m in successful)
        avg_ram = sum(m.peak_rss_mb for m in successful) / len(successful)

        print(f"  Total time: {total_duration:.2f}s")
        print(f"  Avg time per file: {avg_duration:.2f}s")
        print(f"  Max peak RAM: {max_ram:.1f}MB")
        print(f"  Avg peak RAM: {avg_ram:.1f}MB")


if __name__ == "__main__":
    main()
