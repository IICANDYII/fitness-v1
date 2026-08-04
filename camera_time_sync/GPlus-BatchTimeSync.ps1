[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch] $Apply,
    [int[]] $DeviceNumber,
    [string] $Vendor = 'GENPLUS',
    [string] $Product = 'USB-MSDC_DISK_A',
    [ValidateRange(1, 10)]
    [int] $Repeat = 1,
    [ValidateRange(0, 5000)]
    [int] $IntervalMilliseconds = 300,
    [string] $LogPath,
    [switch] $ShowAllUsbDisks
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
if (-not $LogPath) {
    $LogPath = Join-Path $PSScriptRoot 'GPlus-TimeSync.log'
}

function ConvertTo-NormalizedDeviceText {
    param([AllowNull()][string] $Text)
    if ($null -eq $Text) { return '' }
    return ($Text.ToUpperInvariant() -replace '[^A-Z0-9]', '')
}

function New-GPlusRtcCdb {
    param([Parameter(Mandatory = $true)][datetime] $DateTime)

    # Generalplus vendor CDB recovered from G+ TimeUpdater 1.0.2.0:
    # F0 FF 01 YYYY_hi YYYY_lo MM DD hh mm ss 00 00 00 00 47 50
    $year = [int]$DateTime.Year
    return [byte[]]@(
        0xF0, 0xFF, 0x01,
        (($year -shr 8) -band 0xFF), ($year -band 0xFF),
        $DateTime.Month, $DateTime.Day,
        $DateTime.Hour, $DateTime.Minute, $DateTime.Second,
        0x00, 0x00, 0x00, 0x00,
        0x47, 0x50
    )
}

function Format-HexBytes {
    param([byte[]] $Bytes)
    return (($Bytes | ForEach-Object { $_.ToString('X2') }) -join ' ')
}

function Test-IsAdministrator {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Write-ResultLog {
    param([Parameter(Mandatory = $true)] $Record)
    $parent = Split-Path -Parent $LogPath
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    $Record | ConvertTo-Json -Compress | Add-Content -LiteralPath $LogPath -Encoding UTF8
}

if (-not ('GPlusRtc.Native' -as [type])) {
    Add-Type -Language CSharp -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;

namespace GPlusRtc
{
    [StructLayout(LayoutKind.Sequential)]
    internal struct SCSI_PASS_THROUGH
    {
        public ushort Length;
        public byte ScsiStatus;
        public byte PathId;
        public byte TargetId;
        public byte Lun;
        public byte CdbLength;
        public byte SenseInfoLength;
        public byte DataIn;
        public uint DataTransferLength;
        public uint TimeOutValue;
        public UIntPtr DataBufferOffset;
        public uint SenseInfoOffset;

        [MarshalAs(UnmanagedType.ByValArray, SizeConst = 16)]
        public byte[] Cdb;
    }

    public sealed class SendResult
    {
        public bool Success { get; set; }
        public int Win32Error { get; set; }
        public byte ScsiStatus { get; set; }
        public string SenseHex { get; set; }
        public string Message { get; set; }
    }

    public static class Native
    {
        private const uint GENERIC_READ = 0x80000000;
        private const uint GENERIC_WRITE = 0x40000000;
        private const uint FILE_SHARE_READ = 0x00000001;
        private const uint FILE_SHARE_WRITE = 0x00000002;
        private const uint OPEN_EXISTING = 3;
        private const uint IOCTL_SCSI_PASS_THROUGH = 0x0004D004;
        private const byte SCSI_IOCTL_DATA_UNSPECIFIED = 2;

        [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
        private static extern SafeFileHandle CreateFile(
            string fileName,
            uint desiredAccess,
            uint shareMode,
            IntPtr securityAttributes,
            uint creationDisposition,
            uint flagsAndAttributes,
            IntPtr templateFile);

        [DllImport("kernel32.dll", SetLastError = true)]
        [return: MarshalAs(UnmanagedType.Bool)]
        private static extern bool DeviceIoControl(
            SafeFileHandle device,
            uint controlCode,
            IntPtr inBuffer,
            uint inBufferSize,
            IntPtr outBuffer,
            uint outBufferSize,
            out uint bytesReturned,
            IntPtr overlapped);

        public static SendResult Send(string devicePath, byte[] cdb, uint timeoutSeconds)
        {
            if (cdb == null || cdb.Length != 16)
                throw new ArgumentException("The Generalplus CDB must contain exactly 16 bytes.", "cdb");

            using (SafeFileHandle handle = CreateFile(
                devicePath,
                GENERIC_READ | GENERIC_WRITE,
                FILE_SHARE_READ | FILE_SHARE_WRITE,
                IntPtr.Zero,
                OPEN_EXISTING,
                0,
                IntPtr.Zero))
            {
                if (handle.IsInvalid)
                {
                    int error = Marshal.GetLastWin32Error();
                    return new SendResult {
                        Success = false,
                        Win32Error = error,
                        Message = "Cannot open device: " + new Win32Exception(error).Message
                    };
                }

                int structureSize = Marshal.SizeOf(typeof(SCSI_PASS_THROUGH));
                const int senseLength = 32;
                int totalSize = structureSize + senseLength;
                IntPtr buffer = Marshal.AllocHGlobal(totalSize);

                try
                {
                    Marshal.Copy(new byte[totalSize], 0, buffer, totalSize);
                    SCSI_PASS_THROUGH packet = new SCSI_PASS_THROUGH {
                        Length = (ushort)structureSize,
                        CdbLength = 16,
                        SenseInfoLength = senseLength,
                        DataIn = SCSI_IOCTL_DATA_UNSPECIFIED,
                        DataTransferLength = 0,
                        TimeOutValue = timeoutSeconds,
                        DataBufferOffset = UIntPtr.Zero,
                        SenseInfoOffset = (uint)structureSize,
                        Cdb = (byte[])cdb.Clone()
                    };

                    Marshal.StructureToPtr(packet, buffer, false);
                    uint returned;
                    bool ok = DeviceIoControl(
                        handle,
                        IOCTL_SCSI_PASS_THROUGH,
                        buffer,
                        (uint)totalSize,
                        buffer,
                        (uint)totalSize,
                        out returned,
                        IntPtr.Zero);

                    int error = ok ? 0 : Marshal.GetLastWin32Error();
                    packet = (SCSI_PASS_THROUGH)Marshal.PtrToStructure(buffer, typeof(SCSI_PASS_THROUGH));

                    byte[] sense = new byte[senseLength];
                    Marshal.Copy(IntPtr.Add(buffer, structureSize), sense, 0, sense.Length);
                    string senseHex = BitConverter.ToString(sense).Replace('-', ' ').TrimEnd(' ', '0');
                    bool success = ok && packet.ScsiStatus == 0;

                    return new SendResult {
                        Success = success,
                        Win32Error = error,
                        ScsiStatus = packet.ScsiStatus,
                        SenseHex = senseHex,
                        Message = success
                            ? "The device accepted the SCSI command."
                            : (ok
                                ? "The device returned SCSI status 0x" + packet.ScsiStatus.ToString("X2") + "."
                                : "DeviceIoControl failed: " + new Win32Exception(error).Message)
                    };
                }
                finally
                {
                    Marshal.FreeHGlobal(buffer);
                }
            }
        }
    }
}
'@
}

try {
    $allDisks = @(Get-CimInstance Win32_DiskDrive | Where-Object {
        $_.InterfaceType -eq 'USB' -or $_.PNPDeviceID -like 'USBSTOR\*'
    })
} catch {
    throw "无法枚举磁盘设备：$($_.Exception.Message)。请尝试以管理员身份运行 PowerShell。"
}

if ($ShowAllUsbDisks) {
    $allDisks |
        Select-Object Index, DeviceID, Model, InterfaceType, PNPDeviceID, Size |
        Format-Table -AutoSize
}

$vendorKey = ConvertTo-NormalizedDeviceText $Vendor
$productKey = ConvertTo-NormalizedDeviceText $Product
$matches = @($allDisks | Where-Object {
    $deviceText = ConvertTo-NormalizedDeviceText ("{0} {1} {2}" -f $_.Model, $_.Caption, $_.PNPDeviceID)
    $vendorMatches = (-not $vendorKey) -or $deviceText.Contains($vendorKey)
    $productMatches = (-not $productKey) -or $deviceText.Contains($productKey)
    $numberMatches = (-not $DeviceNumber) -or ([int]$_.Index -in $DeviceNumber)
    $vendorMatches -and $productMatches -and $numberMatches
})

if ($matches.Count -eq 0) {
    Write-Warning "没有找到同时匹配 Vendor='$Vendor'、Product='$Product' 的 USB 磁盘设备。"
    if ($allDisks.Count -gt 0) {
        Write-Host ("当前检测到 {0} 个其他 USB 存储设备：" -f $allDisks.Count) -ForegroundColor Yellow
        $allDisks |
            Select-Object Index, DeviceID, Model, Size |
            Format-Table -AutoSize
    }
    Write-Host '如果连接的是 SD 卡或读卡器，这是正常现象：SD 卡没有相机 RTC。' -ForegroundColor Yellow
    Write-Host '请用 USB 线连接相机本体，并让相机进入 USB 存储模式后重试。' -ForegroundColor Yellow
    exit 2
}

Write-Host "找到 $($matches.Count) 个 Generalplus 设备：" -ForegroundColor Cyan
$matches |
    Select-Object Index, DeviceID, Model, PNPDeviceID |
    Format-Table -AutoSize

$previewTime = Get-Date
Write-Host ("命令预览：{0}" -f (Format-HexBytes (New-GPlusRtcCdb $previewTime))) -ForegroundColor DarkGray
Write-Host ("对应时间：{0}" -f $previewTime.ToString('yyyy-MM-dd HH:mm:ss')) -ForegroundColor DarkGray

if (-not $Apply) {
    Write-Host ''
    Write-Host '当前是安全预览模式，没有向设备发送任何命令。' -ForegroundColor Yellow
    Write-Host '先指定单台测试：.\GPlus-BatchTimeSync.ps1 -DeviceNumber <编号> -Apply' -ForegroundColor Yellow
    Write-Host '确认后批量处理：.\GPlus-BatchTimeSync.ps1 -Apply' -ForegroundColor Yellow
    exit 0
}

if (-not $WhatIfPreference -and -not (Test-IsAdministrator)) {
    throw '发送 SCSI Pass Through 命令通常需要管理员权限。请以管理员身份打开 PowerShell 后重试。'
}

$results = New-Object System.Collections.Generic.List[object]
foreach ($disk in $matches) {
    for ($attempt = 1; $attempt -le $Repeat; $attempt++) {
        $now = Get-Date
        $cdb = New-GPlusRtcCdb $now
        $target = "{0} ({1})" -f $disk.DeviceID, $disk.Model

        if ($PSCmdlet.ShouldProcess($target, "发送 Generalplus RTC 校时命令")) {
            $sendResult = [GPlusRtc.Native]::Send([string]$disk.DeviceID, $cdb, 10)
            $record = [pscustomobject]@{
                Timestamp       = (Get-Date).ToString('o')
                DeviceNumber    = [int]$disk.Index
                DevicePath      = [string]$disk.DeviceID
                Model           = [string]$disk.Model
                PNPDeviceID     = [string]$disk.PNPDeviceID
                Attempt         = $attempt
                RequestedTime   = $now.ToString('yyyy-MM-dd HH:mm:ss')
                Cdb             = Format-HexBytes $cdb
                CommandAccepted = [bool]$sendResult.Success
                ScsiStatus      = ('0x{0:X2}' -f $sendResult.ScsiStatus)
                Win32Error      = [int]$sendResult.Win32Error
                Sense           = [string]$sendResult.SenseHex
                Message         = [string]$sendResult.Message
                RtcReadBack     = 'Not available in supplied protocol'
            }
            $results.Add($record)
            Write-ResultLog $record

            if ($sendResult.Success) {
                Write-Host ("[已接受] 设备 {0}，发送时间 {1}" -f $disk.Index, $record.RequestedTime) -ForegroundColor Green
            } else {
                Write-Host ("[失败] 设备 {0}：{1}" -f $disk.Index, $sendResult.Message) -ForegroundColor Red
            }
        }

        if ($attempt -lt $Repeat -and $IntervalMilliseconds -gt 0) {
            Start-Sleep -Milliseconds $IntervalMilliseconds
        }
    }
}

Write-Host ''
Write-Host '注意：“已接受”只表示设备返回 SCSI 成功状态；厂家材料没有提供 RTC 回读命令。' -ForegroundColor Yellow
Write-Host ("日志：{0}" -f $LogPath) -ForegroundColor DarkGray
$results
