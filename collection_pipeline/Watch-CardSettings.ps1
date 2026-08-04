<#
.SYNOPSIS
    插卡监听：每当插入一张相机卡，自动读取根目录 SETTINGS.txt，
    确认 (1) 相机时间是否正确，(2) 循环录制(RECYCLE)是否已关闭。

.DESCRIPTION
    相机卡根目录有一份 SETTINGS.txt，格式类似：
        2021-05-01 00:00:00  ;[DATE TIME/...]
        RESOLUTION =1;[1:720P,0:1080]
        RECYCLE =1;   [1:Loop Recording ON,0:Loop Recording OFF]
        TIMECYC =1;   [0:5MIN ,1:10min,2:15min]

    - 第 1 行是相机时钟。与本机当前时间比对，偏差超过阈值即报警
      （典型故障：相机时钟被重置成 2021-05-01，会导致视频文件名日期全错）。
    - RECYCLE=1 表示【循环录制开】：卡满会覆盖最早的录像 -> 采集会丢数据。
      采集时应为 RECYCLE=0（循环录制关，卡满即停）。

    默认【只读只报警，绝不写卡】，与视频流水线同一条铁律。
    加 -Fix 才会把 SETTINGS.txt 改成 “当前时间 + RECYCLE=0”（相机开机会读它应用设置）。

.PARAMETER TimeToleranceMinutes
    相机时间与本机时间允许的最大偏差（分钟），超过即判为“时间不对”。默认 10。

.PARAMETER Fix
    发现问题时自动改写卡上的 SETTINGS.txt（写卡！默认关闭）。

.PARAMETER PollSeconds
    轮询间隔秒数。默认 2。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File Watch-CardSettings.ps1
        只监听+检查+报警（推荐，不写卡）。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File Watch-CardSettings.ps1 -Fix
        监听，发现问题时自动改写 SETTINGS.txt（会写卡）。
#>
[CmdletBinding()]
param(
    [int]    $TimeToleranceMinutes = 10,
    [switch] $Fix,
    [int]    $PollSeconds = 2
)

$ErrorActionPreference = 'Stop'
# 控制台按 UTF-8 输出中文（本会话 shell 是 65001）。
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

# SETTINGS.txt 是 GBK(cp936) 编码、CRLF 换行；读写都用它，别破坏中文注释。
$GBK    = [System.Text.Encoding]::GetEncoding(936)
$LogDir = 'E:\01Internship\Relty\diet_balance_baseline\_card_check_logs'
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$LogFile = Join-Path $LogDir ('card_check_{0}.log' -f (Get-Date -Format 'yyyyMMdd'))

function Write-Log([string]$msg) {
    $line = ('{0}  {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg)
    Add-Content -Path $LogFile -Value $line -Encoding UTF8
}

function Beep-Alert {
    # 报警声：三声高音。不阻塞太久。
    for ($i = 0; $i -lt 3; $i++) { [Console]::Beep(1000, 180) }
}

function Get-CameraCards {
    # 只看可移动盘(DriveType=2)，且根目录有 SETTINGS.txt 的，才算相机卡。
    # 跳过热插拔留下的 0GB 幽灵盘符。
    Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=2' |
        Where-Object { $_.Size -gt 0 } |
        ForEach-Object { $_.DeviceID } |            # e.g. "F:"
        Where-Object { Test-Path (Join-Path ($_ + '\') 'SETTINGS.txt') }
}

function Parse-Settings([string]$path) {
    $raw = [System.IO.File]::ReadAllText($path, $GBK)

    $result = [ordered]@{
        Raw          = $raw
        DateTimeText = $null
        DateTime     = $null
        Recycle      = $null   # 0/1 或 $null
        Resolution   = $null
        Timecyc      = $null
    }

    # 第 1 行时间：YYYY-MM-DD HH:MM:SS
    $mDt = [regex]::Match($raw, '(?m)^\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})')
    if ($mDt.Success) {
        $result.DateTimeText = $mDt.Groups[1].Value
        try {
            $result.DateTime = [datetime]::ParseExact(
                $mDt.Groups[1].Value, 'yyyy-MM-dd HH:mm:ss', $null)
        } catch {}
    }

    $mRec = [regex]::Match($raw, '(?m)^\s*RECYCLE\s*=\s*(\d)')
    if ($mRec.Success) { $result.Recycle = [int]$mRec.Groups[1].Value }

    $mRes = [regex]::Match($raw, '(?m)^\s*RESOLUTION\s*=\s*(\d)')
    if ($mRes.Success) { $result.Resolution = [int]$mRes.Groups[1].Value }

    $mTc = [regex]::Match($raw, '(?m)^\s*TIMECYC\s*=\s*(\d)')
    if ($mTc.Success) { $result.Timecyc = [int]$mTc.Groups[1].Value }

    return $result
}

function Fix-Settings([string]$path, $parsed) {
    # 只改两处：第1行时间 -> 当前时间；RECYCLE 的数字 -> 0。其余（含中文注释）原样保留。
    $raw = $parsed.Raw
    $now = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')

    $raw = [regex]::Replace($raw,
        '(?m)^(\s*)\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}',
        ('${1}' + $now), 1)

    $raw = [regex]::Replace($raw,
        '(?m)^(\s*RECYCLE\s*=\s*)\d',
        '${1}0')

    # 写回：GBK 编码，不带 BOM。
    [System.IO.File]::WriteAllText($path, $raw, $GBK)
}

function Check-Card([string]$drive) {
    $path = Join-Path ($drive + '\') 'SETTINGS.txt'
    Start-Sleep -Milliseconds 400   # 等挂载稳定
    if (-not (Test-Path $path)) { return }

    # 卡主人（如果放了 name.txt）：方便你知道是谁的卡。
    $owner = ''
    $nameTxt = Get-ChildItem -Path ($drive + '\') -Filter '*.txt' -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -ne 'SETTINGS.txt' -and $_.Length -lt 200 } |
        Select-Object -First 1
    if ($nameTxt) { $owner = ' 卡主=' + [IO.Path]::GetFileNameWithoutExtension($nameTxt.Name) }

    $p     = Parse-Settings $path
    $now   = Get-Date
    $probs = New-Object System.Collections.Generic.List[string]

    # --- 时间检查 ---
    $timeMsg = ''
    if ($null -eq $p.DateTime) {
        $probs.Add('SETTINGS.txt 里读不到时间行')
        $timeMsg = '时间: 解析失败 (原文: {0})' -f $p.DateTimeText
    } else {
        $diffMin = [math]::Abs(($now - $p.DateTime).TotalMinutes)
        if ($diffMin -gt $TimeToleranceMinutes) {
            $probs.Add(('相机时间偏差 {0:N0} 分钟(卡上={1}, 现在={2})' -f `
                $diffMin, $p.DateTime.ToString('yyyy-MM-dd HH:mm:ss'), $now.ToString('yyyy-MM-dd HH:mm:ss')))
            $timeMsg = '时间: [不对] 卡上={0} 现在={1} 偏差{2:N0}分' -f `
                $p.DateTime.ToString('yyyy-MM-dd HH:mm:ss'), $now.ToString('HH:mm:ss'), $diffMin
        } else {
            $timeMsg = '时间: [OK] 卡上={0} 偏差{1:N1}分' -f `
                $p.DateTime.ToString('yyyy-MM-dd HH:mm:ss'), $diffMin
        }
    }

    # --- 循环录制检查 ---
    $recMsg = ''
    if ($null -eq $p.Recycle) {
        $probs.Add('读不到 RECYCLE 行')
        $recMsg = '循环录制: 解析失败'
    } elseif ($p.Recycle -eq 1) {
        $probs.Add('循环录制是【开】的(RECYCLE=1),卡满会覆盖录像 -> 应关掉')
        $recMsg = '循环录制: [开! 需关闭] RECYCLE=1'
    } else {
        $recMsg = '循环录制: [OK 已关] RECYCLE=0'
    }

    # --- 输出 ---
    $header = ('=== {0} 卡 {1}{2} ===' -f $now.ToString('HH:mm:ss'), $drive, $owner)
    Write-Host ''
    if ($probs.Count -eq 0) {
        Write-Host $header -ForegroundColor Green
        Write-Host ("  " + $timeMsg) -ForegroundColor Green
        Write-Host ("  " + $recMsg)  -ForegroundColor Green
        Write-Host "  => 通过,可以用" -ForegroundColor Green
        Write-Log ('[OK] {0}{1}  {2} | {3}' -f $drive, $owner, $timeMsg, $recMsg)
    } else {
        Beep-Alert
        Write-Host $header -ForegroundColor Red
        Write-Host ("  " + $timeMsg) -ForegroundColor Yellow
        Write-Host ("  " + $recMsg)  -ForegroundColor Yellow
        Write-Host "  !! 有问题:" -ForegroundColor Red
        foreach ($x in $probs) { Write-Host ("     - " + $x) -ForegroundColor Red }

        if ($Fix) {
            try {
                Fix-Settings $path $p
                $verify = Parse-Settings $path
                Write-Host ("  => 已改写 SETTINGS.txt: 时间={0}, RECYCLE={1}" -f `
                    $verify.DateTimeText, $verify.Recycle) -ForegroundColor Cyan
                Write-Host "     (下次相机开机读这张卡时应用。请重新插卡确认)" -ForegroundColor Cyan
                Write-Log ('[FIXED] {0}{1}  时间->{2} RECYCLE->{3}' -f $drive, $owner, $verify.DateTimeText, $verify.Recycle)
            } catch {
                Write-Host ("  => 改写失败: " + $_.Exception.Message) -ForegroundColor Red
                Write-Log ('[FIX-FAIL] {0}{1}  {2}' -f $drive, $owner, $_.Exception.Message)
            }
        } else {
            Write-Host "  => 请到相机上手动改(时间对准 + 循环录制关)。加 -Fix 可自动改写。" -ForegroundColor Red
            Write-Log ('[PROBLEM] {0}{1}  {2}' -f $drive, $owner, ($probs -join '; '))
        }
    }
}

# ---------------- 主循环 ----------------
Write-Host "插卡监听已启动。" -ForegroundColor Cyan
Write-Host ("  时间偏差阈值: {0} 分钟 | 写卡模式: {1} | 日志: {2}" -f `
    $TimeToleranceMinutes, ($(if ($Fix) {'开(会改写SETTINGS.txt)'} else {'关(只读只报警)'})), $LogFile) -ForegroundColor DarkGray
Write-Host "  提示: 本机时间必须准,时间比对才有意义。按 Ctrl+C 退出。" -ForegroundColor DarkGray
Write-Log '监听启动'

# 记录当前已在的卡，避免启动时把已插的老卡当新卡狂刷（也检查一遍现有卡）。
$known = @{}
foreach ($d in (Get-CameraCards)) {
    $known[$d] = $true
    Check-Card $d
}

while ($true) {
    Start-Sleep -Seconds $PollSeconds
    $current = @{}
    try { foreach ($d in (Get-CameraCards)) { $current[$d] = $true } } catch { continue }

    # 新出现的卡 -> 检查
    foreach ($d in $current.Keys) {
        if (-not $known.ContainsKey($d)) { Check-Card $d }
    }
    # 更新已知集合（拔掉的自动移除，下次再插还会触发）
    $known = $current
}
