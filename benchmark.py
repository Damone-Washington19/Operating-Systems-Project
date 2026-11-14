"""
Cross-platform OS benchmark: CPU, memory, disk I/O, file search, process creation.
Run the SAME script, with the SAME Python version, on the Windows 11 VM and the
Ubuntu VM (both 2 vCPU / 4 GB / 30 GB NVMe).

The CPU tests are pure Python, so a different Python version on each OS would
measure the interpreter instead of the OS. The script records the Python version
in every CSV row so mismatches are visible.

The file-search test must walk the identical synthetic tree on both systems
(built by make_test_tree.py with the same --files and --seed), not a home folder.

Usage:
    Windows 11:  python  C:\\bench\\scripts\\benchmark.py --root C:\\bench\\tree10k --runs 10
    Ubuntu:      python3 ~/bench/scripts/benchmark.py --root ~/bench/tree10k --runs 10

Results print to the screen and append to ../results/benchmark_results.csv
(relative to this script's folder) unless --out is given.
"""
import argparse
import csv
import datetime
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time

DISK_MB = 100


# ---------- tests ----------
def test_cpu_primes(n=200_000):
    count = 0
    for num in range(2, n):
        is_prime = True
        i = 2
        while i * i <= num:
            if num % i == 0:
                is_prime = False
                break
            i += 1
        if is_prime:
            count += 1
    return count


def test_cpu_matmul(size=120):
    a = [[float(i + j) for j in range(size)] for i in range(size)]
    b = [[float(i - j) for j in range(size)] for i in range(size)]
    return [[sum(a[i][k] * b[k][j] for k in range(size)) for j in range(size)]
            for i in range(size)]


def test_memory(mb=200):
    n = mb * 1024 * 1024
    buf = bytearray(n)
    for i in range(0, n, 4096):      # touch every page so it is really allocated
        buf[i] = 1
    copy = bytes(buf)                # forces a full memory copy
    return len(copy)


def test_disk(mb=DISK_MB):
    """Return (write_seconds, read_seconds).

    write = write + fsync, so the data really reaches the virtual disk.
    read  = immediately re-reading the same file, which is normally served from
            the OS file cache (page cache on Linux, system cache on Windows), so
            it measures cached-read speed, not raw disk reads.
    """
    data = os.urandom(1024 * 1024)
    fd, path = tempfile.mkstemp(prefix="osbench_")
    try:
        t0 = time.perf_counter()
        with os.fdopen(fd, "wb") as f:
            for _ in range(mb):
                f.write(data)
            f.flush()
            os.fsync(f.fileno())
        t1 = time.perf_counter()
        with open(path, "rb") as f:
            while f.read(1024 * 1024):
                pass
        t2 = time.perf_counter()
    finally:
        os.remove(path)
    return t1 - t0, t2 - t1


def test_file_search(root, needle):
    """Walk the whole tree and count file names containing `needle`."""
    hits = total = 0
    for _, _, files in os.walk(root):
        for name in files:
            total += 1
            if needle in name.lower():
                hits += 1
    return total, hits


def test_process_spawn(n=100):
    for _ in range(n):
        subprocess.run([sys.executable, "-c", "pass"], check=True)


# ---------- harness ----------
def run_timed(fn, args, runs, warmup=True):
    """Run fn(*args) `runs` times; return (list_of_seconds, last_result)."""
    if warmup:
        fn(*args)
    times, result = [], None
    for _ in range(runs):
        t = time.perf_counter()
        result = fn(*args)
        times.append(time.perf_counter() - t)
    return times, result


def sysinfo():
    info = {"os": platform.platform(), "cpu": platform.processor() or platform.machine(),
            "cores": os.cpu_count(), "python": platform.python_version()}
    try:
        import psutil
        vm = psutil.virtual_memory()
        info["ram_total_mb"] = vm.total // 2**20
        info["ram_used_at_start_mb"] = (vm.total - vm.available) // 2**20
    except ImportError:
        info["ram_total_mb"] = info["ram_used_at_start_mb"] = "n/a (pip install psutil)"
    return info


def summarize(times):
    return (statistics.mean(times), statistics.median(times),
            statistics.stdev(times) if len(times) > 1 else 0.0, min(times))


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    default_out = os.path.join(os.path.dirname(here), "results", "benchmark_results.csv")

    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", required=True,
                    help="synthetic tree from make_test_tree.py (same on both OSes)")
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--needle", default="target_needle",
                    help="file-name substring for the search test")
    ap.add_argument("--out", default=default_out)
    args = ap.parse_args()

    if args.runs < 2:
        ap.error("--runs must be at least 2 (needed for standard deviation)")
    if not os.path.isdir(args.root):
        ap.error(f"--root folder not found: {args.root}")

    info = sysinfo()
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    print("System:", info)
    print(f"Runs per test: {args.runs}   Search root: {os.path.abspath(args.root)}")
    print("Reminder: use the same Python version on both OSes.\n")

    # (name, times, files, hits)
    results = []

    for name, fn, a in [("cpu_primes", test_cpu_primes, ()),
                        ("cpu_matmul", test_cpu_matmul, ()),
                        ("memory_200MB", test_memory, ())]:
        times, _ = run_timed(fn, a, args.runs)
        results.append((name, times, "", ""))

    # disk: no warm-up; one call gives one write time and one read time
    w_times, r_times = [], []
    for _ in range(args.runs):
        w, r = test_disk()
        w_times.append(w)
        r_times.append(r)
    results.append((f"disk_write_fsync_{DISK_MB}MB", w_times, "", ""))
    results.append((f"disk_read_cached_{DISK_MB}MB", r_times, "", ""))

    times, (search_files, search_hits) = run_timed(
        test_file_search, (args.root, args.needle.lower()), args.runs)
    results.append(("file_search_walk", times, search_files, search_hits))

    times, _ = run_timed(test_process_spawn, (), args.runs)
    results.append(("process_spawn_100", times, "", ""))

    print(f"{'test':<26}{'mean(s)':>10}{'median(s)':>12}{'stdev(s)':>10}{'min(s)':>9}")
    rows = []
    for name, times, files, hits in results:
        mean, med, sd, mn = summarize(times)
        extra = f"   files={files} hits={hits}" if files != "" else ""
        print(f"{name:<26}{mean:>10.3f}{med:>12.3f}{sd:>10.3f}{mn:>9.3f}{extra}")
        rows.append([stamp, info["os"], info["python"], info["cores"], info["ram_total_mb"],
                     name, args.runs, round(mean, 4), round(med, 4), round(sd, 4),
                     round(mn, 4), files, hits])

    if search_hits == 0:
        print(f"\nWARNING: file search found 0 names containing '{args.needle}'. "
              "Is --root the synthetic tree?")

    out = os.path.abspath(args.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    new = not os.path.exists(out)
    with open(out, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["timestamp", "os", "python", "cores", "ram_total_mb", "test", "runs",
                        "mean_s", "median_s", "stdev_s", "min_s", "files", "hits"])
        w.writerows(rows)
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
