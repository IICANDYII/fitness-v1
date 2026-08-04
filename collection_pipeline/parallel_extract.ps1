# 并行抽帧编排器：对 NAS 上所有"有 video 但没抽帧产物"的天目录并行抽帧。
# 用法:  powershell -ExecutionPolicy Bypass -File parallel_extract.ps1 [-N 5] [-Rounds 3]
# - 每个 worker = extract_one_day.py（video 从 NAS 读、帧写本地 scratch、processed 回传 NAS）。
# - 每天 scratch 按 人/日 隔离 → 多 worker 天然互不干扰；不写 manifest（看板由下次正常 [1]/backfill 自愈）。
# - 每轮扫描待抽天、最多 N 条并行；重扫最多 Rounds 轮（捕捉新上传的卡 + 重试瞬时失败）。
# 注意：跑此脚本前，确保没有 [1]/backfill 正在往同一天的 NAS 目录写（否则会和抽帧撞）。
param([int]$N = 5, [int]$Rounds = 3)

$pydir = 'E:\01Internship\Relty\diet_balance_baseline'
$py    = "$pydir\extract_one_day.py"
$root  = 'Z:\Processed Videos'

function PendingDays {
  $t = New-Object System.Collections.ArrayList
  foreach ($od in (Get-ChildItem $root -Directory -ErrorAction SilentlyContinue | Where-Object { $_.Name -notmatch '^_' })) {
    foreach ($dd in (Get-ChildItem $od.FullName -Directory -ErrorAction SilentlyContinue)) {
      $p = $dd.FullName
      $done = (Test-Path "$p\processed\preprocess_complete.json") -and (Test-Path "$p\processed\frames_low.zip")
      if ((Test-Path "$p\video") -and -not $done -and @(Get-ChildItem "$p\video" -File -Filter *.avi -ErrorAction SilentlyContinue).Count -gt 0) {
        # 封口闸门:该人未出现「次日 02:00 后」的数据的天不入队(可能还没传完)。
        # 判定逻辑在 python 里(day_sealed_for_extract),此处只按退出码取舍,保证单一真源。
        & python "$py" --check-sealed "$p" | Out-Null
        if ($LASTEXITCODE -eq 0) { [void]$t.Add($p) }
      }
    }
  }
  return $t
}

Write-Output ("[{0}] 并行抽帧编排器启动: N={1} Rounds={2}" -f (Get-Date -f 'HH:mm:ss'), $N, $Rounds)
for ($round = 1; $round -le $Rounds; $round++) {
  $pending = @(PendingDays)
  Write-Output ("[{0}] 第{1}轮: 待抽 {2} 天, 并行度 {3}" -f (Get-Date -f 'HH:mm:ss'), $round, $pending.Count, $N)
  if ($pending.Count -eq 0) { Write-Output "★ 全部抽完!"; break }
  $queue = New-Object System.Collections.Queue
  foreach ($d in $pending) { $queue.Enqueue($d) }
  $running = New-Object System.Collections.ArrayList
  while ($queue.Count -gt 0 -or $running.Count -gt 0) {
    while ($running.Count -lt $N -and $queue.Count -gt 0) {
      $d = $queue.Dequeue()
      $p = Start-Process python -ArgumentList "`"$py`" `"$d`"" -PassThru -WindowStyle Hidden -WorkingDirectory $pydir
      [void]$running.Add([pscustomobject]@{ d = $d; proc = $p })
      Write-Output ("  [{0}] 启动 {1}" -f (Get-Date -f 'HH:mm:ss'), $d)
    }
    Start-Sleep -Seconds 10
    $keep = New-Object System.Collections.ArrayList
    foreach ($j in $running) {
      if ($j.proc.HasExited) { Write-Output ("  [{0}] 完成 {1} exit={2}" -f (Get-Date -f 'HH:mm:ss'), $j.d, $j.proc.ExitCode) }
      else { [void]$keep.Add($j) }
    }
    $running = $keep
  }
}
Write-Output ("[{0}] ===== 并行抽帧结束 =====" -f (Get-Date -f 'HH:mm:ss'))
