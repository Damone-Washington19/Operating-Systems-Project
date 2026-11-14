<#
.SYNOPSIS
  Create, start or stop the Performance Monitor (perfmon) counter log for the Windows 11 VM.

.DESCRIPTION
  Samples memory, CPU, context-switch, disk and SearchIndexer counters once per second
  and writes a CSV to C:\PerfLogs\OSProject. Each start produces a new file with a
  timestamp in its name. Run from an elevated (Administrator) PowerShell inside the VM.
  Counter names assume an English-language Windows install.

.EXAMPLE
  .\perfmon_setup.ps1 -Action create
  .\perfmon_setup.ps1 -Action start     # before an idle / indexing / search run
  .\perfmon_setup.ps1 -Action stop      # after the run
  .\perfmon_setup.ps1 -Action delete    # remove the collector when the project is done
#>
param(
    [Parameter(Mandatory)][ValidateSet('create', 'start', 'stop', 'delete')][string]$Action,
    [string]$OutDir = 'C:\PerfLogs\OSProject',
    [int]$IntervalSeconds = 1
)

$Name = 'OSProject_Win11'
$Counters = @(
    '\Memory\Committed Bytes'
    '\Memory\Commit Limit'
    '\Memory\Available MBytes'
    '\Memory\Page Faults/sec'
    '\Memory\Pages/sec'
    '\Memory\Cache Bytes'
    '\Process(SearchIndexer)\Working Set'
    '\Process(SearchIndexer)\Private Bytes'
    '\Process(SearchIndexer)\% Processor Time'
    '\Process(Memory Compression)\Working Set'
    '\Processor(_Total)\% Processor Time'
    '\Processor(_Total)\% Privileged Time'
    '\Processor(_Total)\% User Time'
    '\System\Context Switches/sec'
    '\System\Processor Queue Length'
    '\PhysicalDisk(_Total)\Disk Transfers/sec'
    '\PhysicalDisk(_Total)\Avg. Disk sec/Transfer'
)

switch ($Action) {
    'create' {
        New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
        $interval = [TimeSpan]::FromSeconds($IntervalSeconds).ToString()
        # -v mmddhhmm appends a timestamp so every start writes a separate CSV
        logman create counter $Name -f csv -si $interval -v mmddhhmm -o (Join-Path $OutDir 'win11') -c $Counters
    }
    'start'  { logman start $Name }
    'stop'   { logman stop $Name; Get-ChildItem $OutDir -Filter *.csv | Sort-Object LastWriteTime | Select-Object -Last 1 }
    'delete' { logman delete $Name }
}
