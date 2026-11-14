<#
.SYNOPSIS
  Time indexed (Windows Search) vs. unindexed (directory walk) file searches on NTFS.

.DESCRIPTION
  Methods:
    IndexName    - Windows Search index, file-name match   (indexed lookup)
    IndexContent - Windows Search index, full-text match   (indexed lookup)
    Walk         - Get-ChildItem -Recurse name match        (O(N) baseline, no index)
  Each method runs -Runs times; every run is appended to -OutCsv and the median is printed.
  The tree's folder must already be added under Settings > Privacy & security >
  Searching Windows (or Indexing Options) and indexing must be complete.
  Use -WaitForIndex to measure how long indexing takes after adding the folder.

.EXAMPLE
  .\search_benchmark.ps1 -Root C:\bench\tree_10k -WaitForIndex
  .\search_benchmark.ps1 -Root C:\bench\tree_10k -Runs 10 -OutCsv .\results\win11_search.csv
#>
param(
    [Parameter(Mandatory)][string]$Root,
    [int]$Runs = 10,
    [string]$NamePattern = 'target_needle',
    [string]$ContentWord = 'zebracorn',
    [string]$OutCsv = '.\win11_search_results.csv',
    [switch]$WaitForIndex,
    [int]$PollSeconds = 10
)

$Root = (Resolve-Path $Root).Path
$fileCount = (Get-ChildItem -Path $Root -Recurse -File -Filter '*.txt').Count
$scope = 'file:' + $Root.Replace("'", "''")

function Invoke-IndexQuery([string]$where) {
    $conn = New-Object -ComObject ADODB.Connection
    $rs = New-Object -ComObject ADODB.Recordset
    try {
        $conn.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows';")
        $rs.Open("SELECT System.ItemPathDisplay FROM SYSTEMINDEX WHERE SCOPE='$scope' AND $where", $conn)
        $hits = 0
        while (-not $rs.EOF) { $hits++; $rs.MoveNext() }  # read every row so the timing includes retrieval
        return $hits
    }
    finally {
        if ($rs.State -ne 0) { $rs.Close() }
        if ($conn.State -ne 0) { $conn.Close() }
    }
}

$searches = [ordered]@{
    IndexName    = { Invoke-IndexQuery "System.FileName LIKE '$NamePattern%'" }
    IndexContent = { Invoke-IndexQuery "CONTAINS(*, '$ContentWord')" }
    Walk         = { (Get-ChildItem -Path $Root -Recurse -File -Filter "$NamePattern*").Count }
}

if ($WaitForIndex) {
    Write-Host "Waiting for the index to contain all $fileCount files under $Root ..."
    $sw = [Diagnostics.Stopwatch]::StartNew()
    do {
        $indexed = Invoke-IndexQuery "System.FileExtension = '.txt'"
        Write-Host ("  {0,7:N0}s  {1} / {2} indexed" -f $sw.Elapsed.TotalSeconds, $indexed, $fileCount)
        if ($indexed -ge $fileCount) { break }
        Start-Sleep -Seconds $PollSeconds
    } while ($true)
    Write-Host ("Indexing finished in {0:N1} s (accuracy +/- {1} s)" -f $sw.Elapsed.TotalSeconds, $PollSeconds)
}

$rows = foreach ($method in $searches.Keys) {
    for ($run = 1; $run -le $Runs; $run++) {
        $sw = [Diagnostics.Stopwatch]::StartNew()
        $hits = & $searches[$method]
        $sw.Stop()
        [pscustomobject]@{
            Timestamp = (Get-Date).ToString('s')
            OS        = 'Windows 11'
            Method    = $method
            FileCount = $fileCount
            Run       = $run
            Ms        = [math]::Round($sw.Elapsed.TotalMilliseconds, 2)
            Hits      = $hits
        }
    }
}

$outDir = Split-Path -Parent $OutCsv
if ($outDir) { New-Item -ItemType Directory -Force -Path $outDir | Out-Null }
$rows | Export-Csv -Path $OutCsv -NoTypeInformation -Append

$rows | Group-Object Method | ForEach-Object {
    $ms = $_.Group.Ms | Sort-Object
    $mid = [int][math]::Floor($ms.Count / 2)
    $median = if ($ms.Count % 2) { $ms[$mid] } else { ($ms[$mid - 1] + $ms[$mid]) / 2 }
    [pscustomobject]@{ Method = $_.Name; Files = $fileCount; MedianMs = $median; Hits = $_.Group[0].Hits }
} | Format-Table -AutoSize

$walkHits = ($rows | Where-Object Method -eq 'Walk')[0].Hits
$indexHits = ($rows | Where-Object Method -eq 'IndexName')[0].Hits
if ($indexHits -lt $walkHits) {
    Write-Warning "Index returned $indexHits of $walkHits needles; indexing is incomplete or the folder is not in the index scope."
}
Write-Host "Raw results appended to $OutCsv"
