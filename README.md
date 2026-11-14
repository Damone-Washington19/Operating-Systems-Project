# Windows 11 vs. Ubuntu Linux: OS Overhead and File Indexing Benchmarks

**Toech Technologies** · CSC/CIT 3321 Operating Systems · Fall 2026 · Winston-Salem State University
Team: Ibrahim Yakubu (Team Leader), Damone Washington, Kevyn Farmer

This repository holds the code, configuration, and raw data behind our P2 report and P3 presentation. It compares Windows 11 and Ubuntu Linux running as VMware Workstation guests with identical virtual hardware.

## Repository layout

```
scripts/
  make_test_tree.py      seeded synthetic file tree (identical on both OSes)
  benchmark.py           7 cross-platform tests: CPU, memory, disk, file walk, process creation
  search_benchmark.ps1   Windows Search (indexed) vs. directory walk timing
  perfmon_setup.ps1      Performance Monitor counter log (create/start/stop)
results/
  windows/               raw CSVs from the Windows 11 VM
  ubuntu/                raw CSVs from the Ubuntu VM
```

## Virtual machine configuration

| Setting | Windows 11 VM | Ubuntu VM |
|---|---|---|
| Hypervisor | VMware Workstation 26.0.1, hardware version 22 | VMware Workstation |
| Guest OS | Windows 11 Home x64, build 26300 | Ubuntu Desktop (64-bit) |
| vCPUs | 2 (1 socket x 2 cores) | 2 |
| Memory | 4 GB | 4 GB |
| Disk | 30 GB NVMe, NTFS | 30 GB NVMe, ext4 |
| Network | NAT | NAT |
| Python | 3.14.10 | 3.14.10 (must match) |
| Host CPU | Intel Core i7-1255U | Teammate's PC |

Windows 11 VM configuration (`.vmx` excerpt):

```
numvcpus = "2"
cpuid.coresPerSocket = "2"
memsize = "4096"
virtualHW.version = "22"
firmware = "efi"
ethernet0.connectionType = "nat"
sharedFolder0.guestName = "scripts"
sharedFolder0.writeAccess = "FALSE"
```

> **Important:** Windows 11 Home uses only one processor socket. A VM set to 2 sockets x 1 core runs on a single CPU. Configure **1 processor x 2 cores** and confirm inside the guest with `(Get-CimInstance Win32_ComputerSystem).NumberOfLogicalProcessors` (should print 2).

## How to reproduce

Before each session: restore a clean snapshot, pause OS updates, restart the VM, open VS Code on the `scripts` folder only, and wait about 60 seconds.

### Windows 11 (PowerShell as Administrator, from `C:\bench`)

```powershell
Set-ExecutionPolicy -Scope Process Bypass
python scripts\make_test_tree.py C:\bench\tree10k --files 10000
# Add C:\bench\tree10k in Indexing Options (control srchadmin.dll), then:
.\scripts\perfmon_setup.ps1 -Action create
.\scripts\perfmon_setup.ps1 -Action start
.\scripts\search_benchmark.ps1 -Root C:\bench\tree10k -Runs 10 -WaitForIndex -OutCsv C:\bench\results\win11_search_results.csv
.\scripts\perfmon_setup.ps1 -Action stop
python scripts\benchmark.py --root C:\bench\tree10k --runs 10
```

### Ubuntu (terminal, from `~/bench`)

```bash
python3 scripts/make_test_tree.py ~/bench/tree10k --files 10000
python3 scripts/benchmark.py --root ~/bench/tree10k --runs 10
```

Both systems use the default seed (42), so the trees are identical. Run Geekbench 7 (CPU benchmark only) once per VM.

## Script versions (SHA-256)

Matching hashes on both VMs confirm that both teams ran the same code.

| File | SHA-256 |
|---|---|
| benchmark.py | `5b6c28b00ec137f190b8602ab01189965ef3b8b92ff90a2df0419b9d23664165` |
| make_test_tree.py | `b7c0151764b15226b3625a54f139d88af2e5653b76fefddaabd16da712fac0fc` |
| search_benchmark.ps1 | `b8e941ec19e08422b9dc2106b96f267b7d69b15830233be2319acd430831b5c0` |
| perfmon_setup.ps1 | `9e230fb4f81d60284e69947cce7a86c72dc22fb827577aa555d524a07977142f` |

Check on Windows with `Get-FileHash <file>`, on Linux with `sha256sum <file>`.

## Raw data

Every run is kept, including runs excluded from the analysis.

| File | Contents | Used in report |
|---|---|---|
| `results/windows/benchmark_results.csv` | Four benchmark.py sessions, November 13, 2026 | **19:57 session only** (2 CPUs). The 16:35, 17:24, and 18:38 sessions ran on 1 CPU (`cores` = 1) and are excluded. |
| `results/windows/win11_search_results.csv` | Two search_benchmark.ps1 sessions, 10 runs per method | **19:37 session only** (2 CPUs). The 18:26 session ran on 1 CPU and is excluded. |
| `results/windows/win11_11131824.csv` | Performance Monitor log, 1-second samples, 18:24-18:30 | Memory counters only (recorded during the 1-CPU session). |
| `results/ubuntu/` | Ubuntu benchmark.py results | To be added. |

Geekbench 7.1.0, Windows 11 VM: single-core 1,558, multi-core 2,074 ([result](https://browser.geekbench.com/v7/cpu/876122)).

## Summary of Windows 11 results

| Measurement | Result |
|---|---|
| Indexed search by name / by content | 6.27 ms / 6.11 ms (median) |
| Directory walk, 10,000 files | 97.72 ms (median); index is 15.6x and 16.0x faster |
| Process creation (100 processes) | 2.951 s (29.5 ms per process) |
| Committed memory during tests | 78-80% of the commit limit |
