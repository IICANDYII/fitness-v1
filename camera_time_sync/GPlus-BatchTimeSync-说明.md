# Generalplus 相机批量校时工具

## 先说结论

本工具按照厂家 `G+ TimeUpdater 1.0.2.0` 的实际命令格式重新实现，不再修改存储卡上的 `SETTINGS.txt`。

工具通过 Windows SCSI Pass Through 向匹配的 Generalplus USB 存储设备发送 16 字节 RTC 校时命令：

```text
F0 FF 01 年高字节 年低字节 月 日 时 分 秒 00 00 00 00 47 50
```

这与厂家固件代码从 USB Mass Storage CBW 原始包第 18～24 字节读取年、月、日、时、分、秒，并调用 `cal_time_set()` 的行为一致。

## 安全设计

- 直接双击 BAT 或运行 PS1 时只枚举设备和显示命令预览，不发送命令。
- 只有显式加入 `-Apply` 才会发送。
- 默认只匹配同时含有 `GENPLUS` 和 `USB-MSDC_DISK_A` 标识的 USB 磁盘。
- 不提供“忽略型号强制发送”选项，避免把厂家命令发给普通硬盘。
- 每次发送都会写 JSON Lines 日志。
- 厂家材料没有提供 RTC 回读命令，因此成功结果仅表示设备接受了 SCSI 命令，不能声称已经回读验证 RTC。

## 推荐操作顺序

1. 连接相机并打开安全预览：

```powershell
.\GPlus-BatchTimeSync.ps1 -ShowAllUsbDisks
```

2. 记下目标相机的 `Index`，先只测试一台。请以管理员身份打开 PowerShell：

```powershell
.\GPlus-BatchTimeSync.ps1 -DeviceNumber 3 -Apply
```

3. 断开相机 USB，拍一段测试视频，检查相机显示时间和新文件时间是否正确。

4. 单台验证无误后，同时连接多台相机并批量校时：

```powershell
.\GPlus-BatchTimeSync.ps1 -Apply
```

也可以通过 BAT 传递参数：

```bat
GPlus-BatchTimeSync.bat -DeviceNumber 3 -Apply
GPlus-BatchTimeSync.bat -Apply
```

## 常用参数

```text
-Apply                    实际发送；不加时只预览
-DeviceNumber 3,4         仅处理指定物理磁盘编号
-Repeat 2                 每台发送两次，默认一次
-IntervalMilliseconds 500 重复发送间隔
-ShowAllUsbDisks          显示系统检测到的所有 USB 磁盘
-LogPath <路径>           自定义日志位置
```

## 可能遇到的问题

- “拒绝访问”：以管理员身份运行 PowerShell。
- 找不到设备：先执行 `-ShowAllUsbDisks`，检查设备的 Model 和 PNPDeviceID 是否确实包含厂家标识。
- SCSI 状态非零：设备可能不是对应型号、当前不处于 USB Mass Storage 模式，或者固件不支持该命令。
- “命令已接受”但相机时间没变化：先断开 USB 后重新检查；也可能是同名外壳使用了不同固件。

首次使用应只连接一台可测试的相机，确认型号和行为后再批量运行。
