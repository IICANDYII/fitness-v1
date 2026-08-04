<#
.SYNOPSIS
    限制本机到 NAS 的上传速度(基于 Windows QoS 策略,无需第三方软件)。

.DESCRIPTION
    通过 New-NetQosPolicy 对"目标地址 = NAS IP"的出站流量做限速。
    默认限制 50 MB/s。策略持久生效(重启后仍在),用 -Remove 可随时解除。

.EXAMPLE
    # 以管理员身份运行 PowerShell,然后:
    .\Limit-NasUpload.ps1 -NasIp 192.168.1.100

.EXAMPLE
    # 自定义限速(单位 MB/s):
    .\Limit-NasUpload.ps1 -NasIp 192.168.1.100 -LimitMBps 30

.EXAMPLE
    # 解除限速:
    .\Limit-NasUpload.ps1 -Remove

.EXAMPLE
    # 查看当前策略状态:
    .\Limit-NasUpload.ps1 -Status
#>
[CmdletBinding(DefaultParameterSetName = 'Apply')]
param(
    [Parameter(ParameterSetName = 'Apply', Mandatory = $true, Position = 0)]
    [string]$NasIp,

    [Parameter(ParameterSetName = 'Apply')]
    [ValidateRange(1, 10000)]
    [int]$LimitMBps = 50,

    [Parameter(ParameterSetName = 'Remove')]
    [switch]$Remove,

    [Parameter(ParameterSetName = 'Status')]
    [switch]$Status
)

$PolicyName = 'NAS-Upload-Limit'

# 需要管理员权限
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
           ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin -and -not $Status) {
    Write-Error '请以管理员身份运行 PowerShell 再执行本脚本。'
    exit 1
}

if ($Status) {
    $p = Get-NetQosPolicy -Name $PolicyName -ErrorAction SilentlyContinue
    if ($p) {
        $mbps = [math]::Round($p.ThrottleRateAction / 8MB, 1)
        Write-Host "策略 [$PolicyName] 已启用:目标 $($p.IPDstPrefix),限速 $mbps MB/s"
    } else {
        Write-Host "策略 [$PolicyName] 未启用,当前不限速。"
    }
    exit 0
}

if ($Remove) {
    $p = Get-NetQosPolicy -Name $PolicyName -ErrorAction SilentlyContinue
    if ($p) {
        Remove-NetQosPolicy -Name $PolicyName -Confirm:$false
        Write-Host "已解除限速,策略 [$PolicyName] 已删除。"
    } else {
        Write-Host "策略 [$PolicyName] 不存在,无需删除。"
    }
    exit 0
}

# 校验 IP 格式
if (-not [System.Net.IPAddress]::TryParse($NasIp, [ref]$null)) {
    Write-Error "无效的 IP 地址:$NasIp"
    exit 1
}

# MB/s -> bit/s(1 MB = 1024*1024 字节,乘 8 转成比特)
$bitsPerSecond = [uint64]$LimitMBps * 8MB

# 已存在则先删除再重建,保证参数是最新的
if (Get-NetQosPolicy -Name $PolicyName -ErrorAction SilentlyContinue) {
    Remove-NetQosPolicy -Name $PolicyName -Confirm:$false
}

New-NetQosPolicy -Name $PolicyName `
    -IPDstPrefixMatchCondition "$NasIp/32" `
    -ThrottleRateActionBitsPerSecond $bitsPerSecond `
    -NetworkProfile All | Out-Null

Write-Host "已启用限速:发往 $NasIp 的上传流量上限为 $LimitMBps MB/s。"
Write-Host "解除限速请运行:.\Limit-NasUpload.ps1 -Remove"
