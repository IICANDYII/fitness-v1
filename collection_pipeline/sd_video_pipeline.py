#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
SD 卡视频采集流水线(Windows 单机单人)
====================================================================
把插在读卡器/拓展坞上的多张 SD 卡的视频,按「人 + 逻辑日」整理、抽帧、
上传 NAS、清卡。以「稳健、不丢数据」为最高优先级。

【每次运行做什么】
  1. 每张卡上的每段视频:【卡 -> NAS 直传】(限速+校验),校验通过才删卡上原件。
     本地【不落 video】(硬盘容量小,video 只经 NAS)。任一步失败 -> 报警保留卡上原件。
  2. 对【已拍完】的逻辑日(日期<今天,且最后一段距现在已隔跨夜大间隔):
     抽帧:video 从 NAS 读、帧 churn 用 --out 写本地 scratch 快盘(海量小帧图不落 NAS),
     audio 直接写 NAS;抽完把本地 processed(frames_low.zip+索引+标记)传回 NAS,删 scratch。
     还在拍/刚跨零点的先只拷不抽,等它拍完再抽。
     默认只处理【卡在位的人】(插谁的卡处理谁,单轮快、可连续换卡);
     搁置满 STALE_PROCESS_DAYS 天未归档的自动补处理;--all 一次全处理。
     归档后若又混入同一天的新片段(如另一张卡隔天才交),自动打回重抽重传。
  3. 归档校验:确认 NAS 上 processed\preprocess_complete.json 存在且 audio\ 非空,即视为归档。
     不再有"本地日文件夹"的概念;老版本的本地遗留在保留期过后自动清理。

【认卡】卡的卷序列号是 0000-0000、读卡器硬件序列号又共享,都无法唯一标识。
  故归属完全靠卡上一个【以人名命名的 txt】(如 yidan.txt):每次运行读文件名当主人。
  脚本【绝不往卡里写任何东西】,只读与删视频。相机自带 SETTINGS.txt 等自动忽略。

【抽帧】调用本地预处理工具 localpreprocess 的 HTTP 接口(本地网页服务,双击 exe 后
  监听 127.0.0.1)。★该工具即使报「成功」也可能没真产出★,故上传前额外验证
  processed\、audio\ 存在且帧数>0,否则算失败、不上传不清理。

命令行
--------------------------------------------------------------------
  python sd_video_pipeline.py            默认:先拷贝+打总表,输 y 才执行 清卡/抽帧/上传
  python sd_video_pipeline.py --yes      跳过确认(日常无人值守用)
  python sd_video_pipeline.py --dry-run  只看总表,任何情况下都不拷/不删/不传
  python sd_video_pipeline.py --register  仅列出各卡与检测到的归属

使用前:双击 localpreprocess-win-x64.exe(黑窗口开着);每张卡根目录放一个 人名.txt。

依赖: 仅标准库(ctypes 枚举卷, urllib 调接口)。Windows, Python 3.10+。
====================================================================
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.wintypes as wt
import hashlib
import json
import logging
import concurrent.futures
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from datetime import time as dtime  # 与内置 time 模块区分

# ====================================================================
#  配置区(集中在此,便于修改)
# ====================================================================

# 本地工作目录(视频先落地到这里)。本地、不进 OneDrive(避免几十GB视频+海量帧图上云)。
# 桌面上的「采集录像」是指向这里的快捷方式。
DESKTOP_ROOT = r"C:\Users\maxga\Desktop\采集录像"

# NAS 归档根。真实结构: NAS_ROOT\{人名}\{拍摄日YYYYMMDD}\{processed,audio}\
# 日期用【拍摄当天】(与本地文件夹一致),同一拍摄日永远进同一个 NAS 文件夹,便于迟到补传合并。
# 现用【映射网络驱动器 Z:】(旧地址 \\Relty\homes\Processed Videos 已停用)。
# 注意:映射盘是【按登录会话】生效的,若脚本换用户/计划任务/新会话跑而 Z: 没映射到,
#   会判 NAS 不可达(本轮只拷不传,不丢数据)。届时先把 Z: 重新映射到该共享即可:
#   net use Z: \\<新主机或IP>\<共享名> /persistent:yes  (需要账号密码时再带 /user)
NAS_ROOT = r"Z:\Processed Videos"

# ---- 认卡(卡上以人名命名的 txt)----
# 下面这些文件名会被当作相机/系统文件忽略(小写比较);dot 开头的文件也忽略。
OWNER_TXT_IGNORE = {
    "settings.txt", "setting.txt", "readme.txt", "read me.txt", "log.txt",
    "logs.txt", "version.txt", "info.txt", "config.txt", "desktop.ini",
}

# ---- 抽帧工具(localpreprocess)----
# 【命令行模式】把「NAS 上某天文件夹」当参数传给 exe,并用 --out 把帧产物写到本地 scratch:
#     exe "Z:\...\人名\日期" --out "<本地scratch>\人名\日期\processed" --fps 2 --frame-max-edge 1280
# 为什么这么干:抽帧会产出成千上万张松散小帧图(打 zip 后删),这套海量小文件 churn 若直接
#   落在 NAS(SMB)上会奇慢无比。--out 把 processed/ 的 churn 甩到本地快盘(只~8GB/天,抽完即删),
#   video 仍从 NAS 读、audio 仍写 NAS(audio 只有几十个小文件,不是瓶颈),抽完把本地
#   processed(一个 frames_low.zip + 几个索引 + 完成标记)传回 NAS。
# 工具自身幂等:未抽的抽、抽一半的续、已完成的天跳过;--force 强制整天重抽。
# 退出码:0=全部成功;1=有段失败;2=参数/环境错误(仅 0 视为成功)。
PREPROCESS_EXE = r"C:\Users\maxga\OneDrive\Desktop\localpreprocess-win(2)\localpreprocess-win-x64.exe"
PREPROCESS_FPS = 2               # 低频归档帧率(每 0.5s 一帧)
PREPROCESS_FRAME_MAX_EDGE = 1280  # 抽帧长边最大像素
PREPROCESS_JOB_TIMEOUT_SEC = 6 * 3600  # 单日抽帧最长等待,超时视为失败
# 抽帧本地临时工位(存放松散帧+zip 的 churn)。放本地快盘,抽完即删,只占~8GB/天。
# 抽帧+上传成功后自动清空;上传失败则保留,下轮可跳过重抽直接续传。
SCRATCH_ROOT = r"E:\_pipeline_scratch"

# 从文件名解析拍摄时间:(正则, strptime 格式)。
# 已对真实视频名确认: A09999_20260707111225_0001.avi -> 中段 14 位 = 年月日时分秒。
FILENAME_TIME_PATTERN = (r"(\d{14})", "%Y%m%d%H%M%S")

# 被视为视频的扩展名(小写,含点)。
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mts", ".m4v", ".avi", ".insv", ".lrv"}

# 逻辑日切分。
GAP_THRESHOLD_MIN = 240      # 判定「跨日大间隔」的最小分钟数(4 小时)
NIGHT_WINDOW = (1, 7)        # 夜间时段(起始小时, 结束小时)
VERIFY_METHOD = "hash"       # "hash"(sha256) 或 "size"

# 本地日期文件夹保留天数;满这么多天且已归档 NAS 才删。
DESKTOP_RETENTION_DAYS = 2

# ---- 上传后归档目录改名(便于一眼看出哪些天已传)----
# 上传+校验通过后,把 桌面\人名\20260713 改名成 桌面\人名\20260713(已上传)。
# 扫描时两种名字都认作同一逻辑日;迟到补传会先改回无后缀名再处理。
ARCHIVED_SUFFIX = "(已上传)"

# ---- 删本地原视频 video\ 的「封口」门槛(两道门槛之一,比上传保守得多)----
# 因为同一人同一天可能分散在多张卡上,只要还可能有卡没插进来,就不删 raw:
# 删了 raw,迟到的卡就只能拿部分片段重抽、覆盖 NAS 丢掉旧帧(危险)。
# 满足【全部】条件才删该日 raw:已上传归档 + 该天已够老 + 最近没再出现新片段 + 覆盖无异常。
DELETE_RAW_AFTER_ARCHIVE = True   # 关掉则永不自动删 raw(最保守,最费磁盘)
RAW_DELETE_MIN_AGE_DAYS = 3       # 拍摄日距今至少这么多天(给忘带卡的人留补交时间)
RAW_DELETE_STABLE_DAYS = 1        # 且距该日「最后一次新增片段」至少这么多天没再动过
RAW_DELETE_FORCE_AGE_DAYS = 14    # 超过这么多天则强制封口删本地(防一张永远回不来的卡占死磁盘)

# ---- 覆盖异常检测(帮你发现「可能缺段/有人忘带卡」)----
# 仅用于【报警提示 + 暂缓自动删本地】,绝不阻止上传(宁可先把已有的传上去)。
# 两个信号:①当天首尾跨度太短(缺头或缺尾);②中间有超大空档(缺中间一张卡)。
# 开拍/收工的绝对时间因人而异,故【不】按固定时段判断,免得天天误报。
COVERAGE_MIN_SPAN_HOURS = 6       # 当天首尾片段跨度小于此小时数 -> 疑似只采到半天
COVERAGE_GAP_WARN_MIN = 300       # 当天内部相邻片段空档超此分钟数(5h)-> 疑似中间缺卡
                                  # (逻辑日切分本就允许日内 4h 空档,故这里设 5h 免误报午休)

# 上传 NAS:robocopy 多线程数;上传后 processed 帧文件 sha256 抽检数(audio 全量哈希)。
# 帧是海量小文件,逐个哈希读回会被网络延迟拖死(实测 3 文件/秒,一天要 4 小时+);
# 改为 robocopy 批量 + 全量大小核对 + 抽样哈希。原始视频仍在本地保留 2 天,产物可重建。
UPLOAD_MT_THREADS = 8
UPLOAD_HASH_SAMPLE = 30
# 上传限速(MB/s):防止把 NAS 缓存打爆。全局令牌桶,8 线程共享,总速率不超过该值。
# (robocopy 的 /IPG 与 /MT 互斥、限不了速,故上传用脚本自带的多线程+限速拷贝。)
# 设 0 = 不限速。
UPLOAD_MAX_MBPS = 50

# 写 NAS 卡死保护(治本):单文件「拷贝+fsync」若在 (文件MB / NAS_WRITE_MIN_MBPS + NAS_WRITE_GRACE_S)
# 秒内仍未完成,判定为 NAS 一过性卡死(如 SMB fsync 迟迟不返回),弃当前句柄 + 清半成品 + 重试。
# 这样 NAS 抽风时只是该段慢一下/自动重来,不会再像以前那样整条流水线无限冻死、清卡停摆。
# 设 NAS_WRITE_RETRIES=0 可关闭此保护(退回旧行为)。
NAS_WRITE_MIN_MBPS = 4.0     # 低于此均速视为卡死(正常 50+;实测 fsync 正常仅几秒)
NAS_WRITE_GRACE_S = 60       # 额外宽限秒数(给 fsync 落盘留足时间,避免误杀正常慢写)
NAS_WRITE_RETRIES = 2        # 判定卡死后的重试次数

# 抽帧「封口」闸门(见 day_sealed_for_extract):防止把「当天还没传完」的半天
# 提前抽帧、写下完成标记而永久封口(之后晚到的片段进不去,只能强制整天重抽)。
# 规则:某人一旦出现「次日 DAY_SEAL_NEXT_DAY_HOUR:00 之后」的数据,即判其前一天已拍完齐了
#   (人已进入次日拍摄)。阈值取 2 点是为了排除跨零点连拍到 0-2 点、其实仍属前一天那段。
#   例:max 出现 0725 02:00 后的片段 -> 判 max/0724 已齐,可抽。
# 结果:最新一天永远要等到「次日凌晨有人开拍」才会被抽,不会抽没拍完的当天。
# 设 DAY_SEAL_ENABLE=False 可关闭(退回「有 video 没帧就抽」的旧行为)。
DAY_SEAL_ENABLE = True
DAY_SEAL_NEXT_DAY_HOUR = 2

# 永久跳过抽帧的「人/日」名单(数据已知损坏/无法抽等)。格式 "人名/YYYYMMDD",大小写不敏感。
# 这些天不论封口与否、有没有 video,抽帧一律跳过(不影响其 video 归档,只是不抽帧)。
# 例:yancy/20260724 —— 段 0025 时长正好卡在帧边界,抽帧工具生不出末帧、整天失败(工具级 bug),故跳过。
EXTRACT_SKIP_DAYS = {"yancy/20260724"}

# 抽帧+上传默认只处理「卡在位的人」的完整日(插谁的卡处理谁,单轮快、可连续换卡)。
# 但某人的完整日搁置满这么多天仍未归档时,不管其卡在不在都自动补处理(防遗忘)。
STALE_PROCESS_DAYS = 2

# 内部状态账本 / 日志 / 看板:全部放在 NAS 的 _pipeline\ 目录里,和数据同源。
# 好处:换电脑也能看到历史账本和日志;缺点:NAS 掉线时会丢失当轮日志(下面有本地应急目录)。
NAS_STATE_ROOT = os.path.join(NAS_ROOT, "_pipeline")
MANIFEST_FILE = os.path.join(NAS_STATE_ROOT, ".pipeline_manifest.json")
LOG_DIR = os.path.join(NAS_STATE_ROOT, "logs")
ROSTER_FILE = os.path.join(NAS_STATE_ROOT, "花名册看板.txt")
# 应急:NAS 不可达时日志退回本地,避免完全没日志可查。
LOG_DIR_FALLBACK = os.path.join(DESKTOP_ROOT, "logs")

# 视为「SD 卡」的驱动器类型。2 = DRIVE_REMOVABLE(少数读卡器报固定盘 3,可临时加)。
CONSIDER_DRIVE_TYPES = {2}

# ====================================================================
#  日志
# ====================================================================

log = logging.getLogger("pipeline")


def setup_logging() -> None:
    log.setLevel(logging.DEBUG)
    log.handlers.clear()
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    log.addHandler(ch)
    # 日志优先写 NAS(LOG_DIR);NAS 掉线时退回本地应急目录,避免完全无日志可查。
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for target in (LOG_DIR, LOG_DIR_FALLBACK):
        try:
            os.makedirs(target, exist_ok=True)
            fh = logging.FileHandler(os.path.join(target, f"pipeline_{stamp}.log"), encoding="utf-8")
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(fmt)
            log.addHandler(fh)
            if target != LOG_DIR:
                log.warning("★NAS 日志目录不可达,本轮日志写到本地应急目录: %s", target)
            return
        except OSError:
            continue
    log.warning("日志目录都写不了,仅输出到控制台。")


class PipelineError(Exception):
    """预期内的、需要停机让人处理的错误。"""


# ---- 互斥锁(两把,细粒度)----
#   local 锁: 拷卡/清卡/抽帧等本地操作      nas 锁: 上传 NAS/删原视频
#   完整流程拿双锁(独占);「只拷卡抽帧」拿 local;「只上传」拿 nas。
#   -> 上传 NAS 的同时,可以并行跑「拷卡+抽帧」,互不干扰。
_HELD_LOCKS: list[str] = []


def _pid_alive(pid: int) -> bool:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    h = _kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return False
    code = wt.DWORD(0)
    ok = _kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    _kernel32.CloseHandle(h)
    return bool(ok) and code.value == 259  # STILL_ACTIVE


def _try_lock_file(path: str) -> bool:
    for _ in range(2):
        try:
            fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            return True
        except FileExistsError:
            try:
                pid = int(open(path).read().strip() or 0)
            except (OSError, ValueError):
                pid = 0
            if pid and _pid_alive(pid):
                log.error("锁 %s 被运行中的进程(PID %d)持有。等它跑完即可。",
                          os.path.basename(path), pid)
                return False
            try:  # 残留死锁(上次崩溃/断电),清掉重试
                os.remove(path)
            except OSError:
                return False
    return False


def acquire_lock(kind: str = "all") -> bool:
    """kind: 'local' | 'nas' | 'all'。失败时已释放拿到的一半,返回 False。"""
    os.makedirs(DESKTOP_ROOT, exist_ok=True)
    kinds = ("local", "nas") if kind == "all" else (kind,)
    got: list[str] = []
    for k in kinds:
        path = os.path.join(DESKTOP_ROOT, f".pipeline_{k}.lock")
        if _try_lock_file(path):
            got.append(path)
        else:
            for p in got:
                try:
                    os.remove(p)
                except OSError:
                    pass
            return False
    _HELD_LOCKS.extend(got)
    return True


def release_lock() -> None:
    for p in _HELD_LOCKS:
        try:
            os.remove(p)
        except OSError:
            pass
    _HELD_LOCKS.clear()


def die(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    log.error(msg)
    log.error("已停止,未执行任何破坏性操作。请处理后重跑。")
    sys.exit(2)


# ====================================================================
#  Windows 卷枚举 / 认卡
# ====================================================================

_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


def _get_volume_info(root: str) -> tuple[str | None, str | None]:
    serial = wt.DWORD(0)
    max_comp = wt.DWORD(0)
    fs_flags = wt.DWORD(0)
    vol_buf = ctypes.create_unicode_buffer(261)
    fs_buf = ctypes.create_unicode_buffer(261)
    ok = _kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root),
        vol_buf, ctypes.sizeof(vol_buf) // ctypes.sizeof(ctypes.c_wchar),
        ctypes.byref(serial), ctypes.byref(max_comp), ctypes.byref(fs_flags),
        fs_buf, ctypes.sizeof(fs_buf) // ctypes.sizeof(ctypes.c_wchar),
    )
    if not ok:
        return None, None
    return f"{serial.value:08X}", vol_buf.value


def enumerate_card_volumes() -> list[tuple[str, str]]:
    """返回候选卡卷 [(root, label)]。"""
    cards = []
    mask = _kernel32.GetLogicalDrives()
    for i in range(26):
        if not (mask & (1 << i)):
            continue
        root = f"{chr(ord('A') + i)}:\\"
        dtype = _kernel32.GetDriveTypeW(ctypes.c_wchar_p(root))
        if dtype not in CONSIDER_DRIVE_TYPES:
            continue
        _serial, label = _get_volume_info(root)
        cards.append((root, label or ""))
    return cards


def _read_first_line(path: str) -> str | None:
    try:
        raw = open(path, "rb").read()
    except OSError:
        return None
    for enc in ("utf-8-sig", "gbk", "utf-16"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        return None
    for line in text.splitlines():
        if line.strip():
            return line.strip()
    return None


def read_owner_marker(card_root: str) -> str | None:
    """卡根目录里【以人名命名】的单个 .txt -> 人名(小写)。见文件头说明。"""
    try:
        entries = os.listdir(card_root)
    except OSError:
        return None
    txts = []
    for f in entries:
        if not f.lower().endswith(".txt") or f.startswith("."):
            continue
        if f.lower() in OWNER_TXT_IGNORE:
            continue
        if os.path.isfile(os.path.join(card_root, f)):
            txts.append(f)
    if not txts:
        return None
    if len(txts) > 1:
        log.warning("卡 %s 根目录有多个候选 .txt(%s),无法判定归属;请只保留一个以人名命名的 txt。",
                    card_root, ", ".join(sorted(txts)))
        return None
    fname = txts[0]
    stem = os.path.splitext(fname)[0]
    if stem.lower() == "owner":
        content = _read_first_line(os.path.join(card_root, fname))
        return content.lower() if content else None
    return stem.strip().lower()


# ====================================================================
#  文件时间解析
# ====================================================================

_time_re = re.compile(FILENAME_TIME_PATTERN[0])
_time_fmt = FILENAME_TIME_PATTERN[1]


def parse_shot_time(filename: str) -> datetime:
    m = _time_re.search(filename)
    if not m:
        raise PipelineError(
            f"文件名无法匹配时间正则,无法确定拍摄时间: {filename}\n"
            f"    请修正 FILENAME_TIME_PATTERN 正则: {FILENAME_TIME_PATTERN[0]!r}")
    joined = "".join(g for g in m.groups() if g is not None) if m.groups() else m.group(0)
    try:
        return datetime.strptime(joined, _time_fmt)
    except ValueError as e:
        raise PipelineError(
            f"从 {filename!r} 提取到 {joined!r},但按格式 {_time_fmt!r} 解析失败: {e}\n"
            f"    请修正 FILENAME_TIME_PATTERN。")


def find_videos(root: str) -> list[str]:
    out = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.startswith("."):
                continue  # Mac AppleDouble(._xxx.avi)等隐藏垃圾,不是真视频
            if os.path.splitext(name)[1].lower() in VIDEO_EXTENSIONS:
                out.append(os.path.join(dirpath, name))
    return out


def owner_latest_shot_time(owner: str) -> "datetime | None":
    """扫 NAS 上该人【所有天】的 video 文件名,返回能解析到的最大拍摄时间;无则 None。
    只读文件名(不读内容),很快。用于判断该人是否已进入「次日」拍摄(见 day_sealed_for_extract)。
    注意:只看 video\\ 文件名;若某天 video 已被归档删除,该天时间无法从这里取到,但我们只关心
    「最新」时间,最新的天通常 video 还在,故足够。"""
    owner_dir = os.path.join(NAS_ROOT, owner)
    latest: "datetime | None" = None
    try:
        labels = os.listdir(owner_dir)
    except OSError:
        return None
    for label in labels:
        vdir = os.path.join(owner_dir, label, "video")
        if not os.path.isdir(vdir):
            continue
        try:
            names = os.listdir(vdir)
        except OSError:
            continue
        for name in names:
            if name.startswith("."):
                continue
            if os.path.splitext(name)[1].lower() not in VIDEO_EXTENSIONS:
                continue
            try:
                st = parse_shot_time(name)
            except PipelineError:
                continue
            if latest is None or st > latest:
                latest = st
    return latest


def day_in_skiplist(owner: str, label: str) -> bool:
    """该「人/日」是否在永久跳过名单 EXTRACT_SKIP_DAYS 里(大小写不敏感)。"""
    key = f"{owner}/{label}".lower()
    return key in {s.lower() for s in EXTRACT_SKIP_DAYS}


def day_sealed_for_extract(owner: str, label: str) -> "tuple[bool, str]":
    """抽帧闸门:判断某人某天 D(label=YYYYMMDD)是否「已拍完齐、可以抽」。
    规则(见配置 DAY_SEAL_*):该人名下一旦出现 shot 时间 >= (D+1) 的 DAY_SEAL_NEXT_DAY_HOUR:00
    的数据,即判 D 已齐(人已进入次日拍摄);否则判「未封口」,本轮不抽,留到以后。
    label 非法日期时放行(不因判定逻辑挡住无法解析的目录)。返回 (是否可抽, 原因)。"""
    if not DAY_SEAL_ENABLE:
        return True, "封口判定已关闭(DAY_SEAL_ENABLE=False),放行"
    try:
        day = datetime.strptime(label, "%Y%m%d")
    except ValueError:
        return True, f"标签 {label!r} 非日期,跳过封口判定,放行"
    threshold = day + timedelta(days=1, hours=DAY_SEAL_NEXT_DAY_HOUR)
    latest = owner_latest_shot_time(owner)
    if latest is None:
        return False, f"{owner} 在 NAS 上无可解析数据,暂不抽"
    if latest >= threshold:
        return True, (f"已见 {owner} 最新数据 {latest:%Y-%m-%d %H:%M} "
                      f">= 次日 {DAY_SEAL_NEXT_DAY_HOUR:02d}:00 阈值,判定 {label} 已齐")
    return False, (f"{owner} 最新数据仅到 {latest:%Y-%m-%d %H:%M},"
                   f"未过 {label} 次日 {DAY_SEAL_NEXT_DAY_HOUR:02d}:00,暂不抽")


# ====================================================================
#  校验
# ====================================================================

def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _run_with_timeout(fn, timeout_s: float):
    """在 daemon 线程里跑 fn(),返回 (status, value):
    status = "ok"(value=结果) / "timeout"(疑似 NAS 无响应) / "error"(value=异常)。
    超时的 daemon 线程随进程退出,不阻塞主流程;用于给"读 NAS"这类可能卡死的操作兜底。"""
    box: dict = {}

    def _run():
        try:
            box["v"] = fn()
        except BaseException as e:  # noqa: BLE001 (连 OSError 一起兜住交上层判断)
            box["e"] = e

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout_s)
    if t.is_alive():
        return "timeout", None
    if "e" in box:
        return "error", box["e"]
    return "ok", box.get("v")


def files_match(src: str, dst: str) -> tuple[bool, str]:
    if not os.path.isfile(dst):
        return False, "目标不存在"
    if VERIFY_METHOD == "size":
        s, d = os.path.getsize(src), os.path.getsize(dst)
        return (s == d), f"size {s} vs {d}"
    if os.path.getsize(src) != os.path.getsize(dst):
        return False, "大小不同(hash 前置检查)"
    hs = _sha256(src)                         # 本地,快,不会卡
    # 读 NAS 文件算 sha256 在 NAS 一过性卡死时会无限期挂起(backfill 就卡在这)→ 加超时,
    # 超时抛 TimeoutError(OSError 子类),上层 copy_clip/upload 已 except OSError → 保留卡上原件、下次重试。
    to = os.path.getsize(dst) / (1024 * 1024) / max(0.1, NAS_WRITE_MIN_MBPS) + NAS_WRITE_GRACE_S
    st, hd = _run_with_timeout(lambda: _sha256(dst), to)
    if st == "timeout":
        raise TimeoutError(f"读 NAS 校验超时 {to:.0f}s(疑似 NAS 无响应): {dst}")
    if st == "error":
        raise hd
    return (hs == hd), f"sha256 {hs[:12]}.. vs {hd[:12]}.."


# ====================================================================
#  Manifest 账本
# ====================================================================

def _atomic_replace_with_retry(src: str, dst: str, attempts: int = 6) -> None:
    """
    os.replace(src, dst) 的带重试版。
    NAS(SMB)上覆盖已存在文件的原子替换会偶发 ACCESS_DENIED(WinError 5)/
    共享冲突(WinError 32)——NAS 对刚写过的文件句柄释放有延迟。重试几次基本必成。
    """
    delay = 0.3
    for i in range(attempts):
        try:
            os.replace(src, dst)
            return
        except PermissionError as e:  # WinError 5
            last = e
        except OSError as e:          # WinError 32 等共享冲突
            if getattr(e, "winerror", None) not in (5, 32):
                raise
            last = e
        if i < attempts - 1:
            log.warning("账本写入被 NAS 短暂拒绝(第%d次,%s),%.1fs 后重试…",
                        i + 1, getattr(last, "winerror", "?"), delay)
            time.sleep(delay)
            delay = min(delay * 2, 4.0)
    # 全部重试失败:抛出让上层报警(数据本身已在 NAS,重跑会据 NAS 现状自愈)。
    raise last


@dataclass
class Manifest:
    clips: dict = field(default_factory=dict)
    days: dict = field(default_factory=dict)
    demoted_days: set = field(default_factory=set)  # 本进程主动打回 pending 的日(合并时本方赢)

    @classmethod
    def load(cls) -> "Manifest":
        if os.path.isfile(MANIFEST_FILE):
            try:
                with open(MANIFEST_FILE, "r", encoding="utf-8-sig") as f:
                    d = json.load(f)
                return cls(clips=d.get("clips", {}), days=d.get("days", {}))
            except (OSError, json.JSONDecodeError) as e:
                die(f"manifest 损坏,无法解析: {MANIFEST_FILE}: {e}")
        return cls()

    def save(self) -> None:
        """
        合并式保存:并行的另一流程(如 NAS 上传器)可能已更新磁盘账本。
        以磁盘为底、叠加本进程的修改,并保留对方的「只进不退」标记:
          - clip 的 raw_deleted=True 一旦写入不回退;
          - day 的 status=archived 保留,除非本进程明确打回(demoted_days)。
        """
        os.makedirs(os.path.dirname(MANIFEST_FILE), exist_ok=True)
        disk: dict = {}
        if os.path.isfile(MANIFEST_FILE):
            try:
                with open(MANIFEST_FILE, "r", encoding="utf-8-sig") as f:
                    disk = json.load(f)
            except (OSError, json.JSONDecodeError):
                disk = {}
        dclips, ddays = disk.get("clips", {}), disk.get("days", {})

        out_clips = dict(dclips)
        for cid, rec in self.clips.items():
            merged = dict(rec)
            if dclips.get(cid, {}).get("raw_deleted"):
                merged["raw_deleted"] = True
            out_clips[cid] = merged

        out_days = dict(ddays)
        for k, rec in self.days.items():
            drec = ddays.get(k)
            if (drec and drec.get("status") == "archived"
                    and rec.get("status") != "archived" and k not in self.demoted_days):
                out_days[k] = drec  # 对方已归档,本方信息旧 -> 保留归档
            else:
                out_days[k] = rec

        tmp = MANIFEST_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"clips": out_clips, "days": out_days}, f, ensure_ascii=False, indent=2)
        _atomic_replace_with_retry(tmp, MANIFEST_FILE)
        # 合并结果同步回内存,后续判断以最新为准。
        self.clips, self.days = out_clips, out_days


def day_key(owner: str, label: str) -> str:
    return f"{owner}/{label}"


# ====================================================================
#  本地日文件夹:命名/归档改名 + 「封口」判定 + 覆盖异常检测
# ====================================================================
#  一个逻辑日在本地的文件夹有两种名字:
#     采集录像\人名\20260713          <- 未归档/正在处理(可写)
#     采集录像\人名\20260713(已上传)   <- 已上传 NAS 并校验通过(冻结,勿动)
#  凡是要往某天写片段/重抽帧,先 reopen_day_folder 改回无后缀名再操作。
# ====================================================================

def _plain_dir(owner: str, label: str) -> str:
    return os.path.join(DESKTOP_ROOT, owner, label)


def _archived_dir(owner: str, label: str) -> str:
    return os.path.join(DESKTOP_ROOT, owner, label + ARCHIVED_SUFFIX)


def day_folder(owner: str, label: str) -> str:
    """
    返回该逻辑日在【本地】现存的文件夹路径(供 seal 清理老遗留用)。
    新流程下 video/processed/audio 都在 NAS 上,本地一般不存在这个目录;
    若本地有历史遗留,seal_and_cleanup 会按保留期规则清掉。
    """
    plain, arch = _plain_dir(owner, label), _archived_dir(owner, label)
    if os.path.isdir(plain):
        return plain
    if os.path.isdir(arch):
        return arch
    return plain


def nas_day_folder(owner: str, label: str) -> str:
    """
    NAS 上该逻辑日的文件夹路径(供抽帧、归档校验用)。
    新流程下 video/processed/audio 全在这里,不再本地。
    """
    return os.path.join(NAS_ROOT, owner, label)


def reopen_day_folder(owner: str, label: str) -> str:
    """新流程下 NAS 目录不改名,此函数为 no-op,返回 NAS 上该日路径。"""
    return nas_day_folder(owner, label)


def mark_day_archived(owner: str, label: str) -> None:
    """新流程下归档判定完全依赖 manifest.status + NAS 上 processed/audio 存在与否,不再改名。"""
    return


def _age_days(label: str, now: datetime) -> int:
    try:
        return (now.date() - datetime.strptime(label, "%Y%m%d").date()).days
    except ValueError:
        return -1


def coverage_issues(clips: list["Clip"]) -> list[str]:
    """
    返回该逻辑日「覆盖异常」的说明(空列表=看起来正常)。
    仅用于【报警提示 + 暂缓自动删本地】,绝不阻止上传(宁可先把已有的传上去)。
    典型异常:多机位/换卡时有人的卡还没插进来 -> 只采到半天,或中间缺一大段。
    """
    if not clips:
        return ["无片段"]
    times = sorted(c.shot_time for c in clips)
    issues: list[str] = []
    # 信号1:整天时间跨度太短 -> 只采到一小段(缺的卡在开头或结尾)。
    span_h = (times[-1] - times[0]).total_seconds() / 3600.0
    if span_h < COVERAGE_MIN_SPAN_HOURS:
        issues.append(f"时间跨度仅{span_h:.1f}h(<{COVERAGE_MIN_SPAN_HOURS}h),疑似只采到部分")
    # 信号2:中间有超大空档 -> 缺的卡在中间。
    # (注:开拍/收工的绝对时间因人而异,不据此判断,免得天天误报。)
    biggest = max(((b - a).total_seconds() / 60.0 for a, b in zip(times, times[1:])), default=0.0)
    if biggest > COVERAGE_GAP_WARN_MIN:
        issues.append(f"内部最大空档{biggest/60:.1f}h(>{COVERAGE_GAP_WARN_MIN}分),疑似中间缺一张卡")
    return issues


def day_is_sealed(drec: dict, now: datetime) -> tuple[bool, str]:
    """
    「封口」= 可以安全删本地原视频/整日文件夹了。必须已归档,且:
      - 拍摄日距今 >= RAW_DELETE_MIN_AGE_DAYS(给忘带卡的人留补交时间);且
      - 距最后一次新增片段 >= RAW_DELETE_STABLE_DAYS(近期没再长东西);且
      - 无覆盖异常(否则疑似还缺段,继续等)。
    但超过 RAW_DELETE_FORCE_AGE_DAYS 天则强制封口(防一张永远回不来的卡把磁盘占死)。
    """
    if drec.get("status") != "archived":
        return False, "未归档"
    age = _age_days(drec.get("day_label", ""), now)
    if age < 0:
        return False, "日期异常"
    if age >= RAW_DELETE_FORCE_AGE_DAYS:
        return True, f"已达强制封口龄({age}天)"
    if age < RAW_DELETE_MIN_AGE_DAYS:
        return False, f"距今仅{age}天(<{RAW_DELETE_MIN_AGE_DAYS})"
    last_new = drec.get("last_new_clip_at")
    if last_new:
        try:
            if (now - datetime.fromisoformat(last_new)).days < RAW_DELETE_STABLE_DAYS:
                return False, "近期仍有新片段加入"
        except ValueError:
            pass
    if drec.get("coverage_issues"):
        return False, "覆盖异常(疑似缺段),暂不删本地"
    return True, "ok"


# ====================================================================
#  片段与逻辑日
# ====================================================================

@dataclass
class Clip:
    clip_id: str          # owner::相对卡根路径,天然唯一(文件名含设备号+时间戳)
    owner: str
    src_path: str | None  # 卡上绝对路径;卡不在/已清时可能为 None 或已失效
    filename: str
    shot_time: datetime
    day_label: str = ""
    dest_path: str = ""


@dataclass
class LogicalDay:
    owner: str
    label: str
    clips: list[Clip]
    complete: bool = False      # 逻辑日已「拍完」(见 day_is_complete)
    process_now: bool = False   # 本轮是否抽帧+上传(卡在位 / 搁置超期 / --all)

    @property
    def key(self) -> str:
        return day_key(self.owner, self.label)


def crosses_night(t1: datetime, t2: datetime) -> bool:
    n0, n1 = NIGHT_WINDOW
    d = t1.date()
    while d <= t2.date():
        ns = datetime.combine(d, dtime(n0, 0))
        ne = datetime.combine(d, dtime(n1, 0))
        if max(t1, ns) < min(t2, ne):
            return True
        d += timedelta(days=1)
    return False


def day_is_complete(d: "LogicalDay", now: datetime) -> bool:
    """
    逻辑日「拍完了」的判定(与分天规则同一语义):
      1) 日期标签 < 今天;且
      2) 最后一段片段距「现在」已经隔了一个日界(> GAP_THRESHOLD_MIN 且跨夜)。
    条件2防的是:凌晨还在跨零点连拍时就跑脚本,把「还没结束的逻辑日」提前
    抽帧归档,导致之后的片段进不了这一天(会被永久漏掉)。
    """
    if d.label >= now.strftime("%Y%m%d"):
        return False
    last = max(c.shot_time for c in d.clips)
    gap_min = (now - last).total_seconds() / 60.0
    return gap_min > GAP_THRESHOLD_MIN and crosses_night(last, now)


def segment_days(owner: str, clips: list[Clip]) -> list[LogicalDay]:
    clips = sorted(clips, key=lambda c: c.shot_time)
    segments: list[list[Clip]] = [[clips[0]]]
    for prev, cur in zip(clips, clips[1:]):
        gap_min = (cur.shot_time - prev.shot_time).total_seconds() / 60.0
        if gap_min > GAP_THRESHOLD_MIN and crosses_night(prev.shot_time, cur.shot_time):
            segments.append([cur])
        else:
            segments[-1].append(cur)

    by_label: dict[str, list[Clip]] = {}
    for seg in segments:
        label = min(c.shot_time for c in seg).strftime("%Y%m%d")
        by_label.setdefault(label, []).extend(seg)

    days = []
    for label, seg_clips in sorted(by_label.items()):
        for c in seg_clips:
            c.day_label = label
        days.append(LogicalDay(owner, label, sorted(seg_clips, key=lambda c: c.shot_time)))
    return days


def gather_clips(present_cards: list[tuple[str, str]], mf: Manifest) -> dict[str, Clip]:
    """
    汇集每个人所有「尚未本地清理」的片段,供逻辑日切分:
      - 当前在位卡上扫描到的视频
      - manifest 里状态为 copied(已拷本地、卡可能已清)、尚未 purged 的片段
    这样即使今天的早段已拷贝并清卡,仍能与今天新拍的片段一起正确切分同一逻辑日。
    """
    clips: dict[str, Clip] = {}
    src_seen: dict[str, str] = {}
    for root, owner in present_cards:
        for path in find_videos(root):
            rel = os.path.relpath(path, root)
            cid = f"{owner}::{rel}"
            if cid in src_seen and os.path.normcase(src_seen[cid]) != os.path.normcase(path):
                raise PipelineError(
                    f"两处来源产生了相同片段标识 {cid}:\n    {src_seen[cid]}\n    {path}\n"
                    f"    可能是同一人两张卡里存在同名同路径文件,无法安全区分。请人工核对。")
            src_seen[cid] = path
            clips[cid] = Clip(cid, owner, path, os.path.basename(path),
                              parse_shot_time(os.path.basename(path)))
            if cid in mf.clips:
                mf.clips[cid]["src_path"] = path  # 刷新来源路径(盘符可能变过)

    for cid, rec in mf.clips.items():
        if rec.get("status") == "copied" and cid not in clips:
            clips[cid] = Clip(
                cid, rec["owner"], rec.get("src_path"), rec["filename"],
                datetime.fromisoformat(rec["shot_time"]),
                rec.get("day_label", ""), rec.get("dest_path", ""),
            )
    return clips


# ====================================================================
#  落地拷贝 + 即时清卡
# ====================================================================

def choose_dest(video_dir: str, clip: Clip, mf: Manifest, claimed: set[str]) -> str:
    prior = mf.clips.get(clip.clip_id, {})
    if prior.get("dest_path"):
        return prior["dest_path"]  # 沿用历史,保证幂等
    dest = os.path.join(video_dir, clip.filename)
    if dest in claimed or any(r.get("dest_path") == dest for cid, r in mf.clips.items()
                              if cid != clip.clip_id):
        stem, ext = os.path.splitext(clip.filename)
        tag = hashlib.md5(clip.clip_id.encode("utf-8")).hexdigest()[:6]
        dest = os.path.join(video_dir, f"{stem}__{tag}{ext}")
    return dest


def copy_clip(clip: Clip, mf: Manifest, claimed: set[str], limiter: "_RateLimiter") -> bool:
    """
    把片段【从卡直接传到 NAS 的 video\\ 目录】并校验。本地不落地。
    成功(或 NAS 上已存在且与卡一致)返回 True。
    失败返回 False(不抛异常,由调用方汇总报警、保留卡上原件)。
    """
    rec = mf.clips.get(clip.clip_id, {})
    if rec.get("card_cleared"):
        # 卡上原件已清 => 之前已成功传 NAS,不必也无法再传。
        return True
    if not nas_reachable():
        log.error("NAS(%s)不可达,无法传视频。检查 Z: 映射后重跑。", NAS_ROOT)
        return False
    nas_video_dir = os.path.join(NAS_ROOT, clip.owner, clip.day_label, "video")
    try:
        os.makedirs(nas_video_dir, exist_ok=True)
    except OSError as e:
        log.error("无法创建 NAS video 目录 %s: %s", nas_video_dir, e)
        return False
    dest = choose_dest(nas_video_dir, clip, mf, claimed)
    claimed.add(dest)
    clip.dest_path = dest

    # 幂等:NAS 上已有目标时必须先做完整校验。未知来源的同名文件绝不覆盖。
    try:
        already = os.path.isfile(dest) and clip.src_path and os.path.isfile(clip.src_path)
    except OSError:
        already = False
    if already:
        try:
            ok, why = files_match(clip.src_path, dest)
        except OSError as e:
            log.error("校验时读文件失败: %s: %s", dest, e)
            return False
        if not ok:
            if rec.get("dest_path") != dest:
                log.error("★冲突★ %s 与 NAS 已有副本内容不一致(%s),不覆盖不删卡,请人工核对: %s",
                          clip.src_path, why, dest)
                return False
            log.warning("NAS 上该片段的历史副本损坏(%s),将以卡上原件原子修复: %s", why, dest)
        else:
            log.debug("NAS 已有且一致,跳过传输: %s", dest)
            _record_clip(mf, clip, "copied", rec.get("card_cleared", False))
            return True

    if not clip.src_path or not os.path.isfile(clip.src_path):
        # 卡上没有源:该视频若其实【已在 NAS 上】(video\ 里有它),说明上一轮已传好、卡也已清,
        # 只是账本没来得及记 card_cleared(如账本写盘时崩了)。据 NAS 现状自愈,视为已完成。
        if os.path.isfile(dest):
            log.info("原片已不在卡上,但 NAS 已有该段 video,视为已传好: %s", clip.clip_id)
            rec.update({"owner": clip.owner, "src_path": clip.src_path,
                        "filename": clip.filename, "shot_time": clip.shot_time.isoformat(),
                        "day_label": clip.day_label, "dest_path": dest,
                        "status": "copied", "card_cleared": True})
            mf.clips[clip.clip_id] = rec
            mf.save()
            return True
        # NAS 上也没有:若该日已归档(processed+audio 齐),视为原片已按策略清理。
        if rec.get("status") == "copied" and nas_has_day(clip.owner, clip.day_label):
            log.warning("原片已不在卡上,NAS 该日已归档,视为已清: %s", clip.clip_id)
            rec["card_cleared"] = True
            rec["raw_deleted"] = True
            mf.clips[clip.clip_id] = rec
            mf.save()
            return True
        log.error("需要传输但源文件不可用: %s (%s)", clip.clip_id, clip.src_path)
        return False

    log.info("卡 -> NAS: %s -> %s", clip.src_path, dest)
    try:
        _throttled_copy(clip.src_path, dest, limiter)
        ok, why = files_match(clip.src_path, dest)
    except OSError as e:
        log.error("卡->NAS 传输失败(保留卡上原件): %s -> %s: %s", clip.src_path, dest, e)
        try:
            os.remove(dest)  # 半成品清掉,便于下次续传
        except OSError:
            pass
        return False
    if not ok:
        log.error("卡->NAS 校验失败(保留卡上原件): %s -> %s (%s)", clip.src_path, dest, why)
        try:
            os.remove(dest)
        except OSError:
            pass
        return False
    _record_clip(mf, clip, "copied", card_cleared=False)
    mf.save()
    return True


def upload_local_video_to_nas(local_path: str, owner: str, label: str,
                              limiter: "_RateLimiter", relative_path: str | None = None) -> bool:
    """
    把一个【已在本地】的视频文件上传到 NAS 的 video\\ 并校验。成功返回 True。
    用于恢复:老流程遗留在本地、卡已清、还没上 NAS 的视频(如 0720 那批)。
    幂等:NAS 上已有同名同大小且内容一致 -> 跳过。失败清半成品、返回 False(本地原件保留)。
    """
    if not nas_reachable():
        log.error("NAS(%s)不可达,无法上传本地视频。", NAS_ROOT)
        return False
    nas_video_dir = os.path.join(NAS_ROOT, owner, label, "video")
    try:
        os.makedirs(nas_video_dir, exist_ok=True)
    except OSError as e:
        log.error("无法创建 NAS video 目录 %s: %s", nas_video_dir, e)
        return False
    rel = relative_path or os.path.basename(local_path)
    rel = os.path.normpath(rel)
    if os.path.isabs(rel) or rel == ".." or rel.startswith(".." + os.sep):
        log.error("拒绝不安全的视频相对路径: %s", rel)
        return False
    dest = os.path.join(nas_video_dir, rel)
    try:
        if os.path.isfile(dest):
            ok, why = files_match(local_path, dest)
            if ok:
                log.info("NAS 已有该段且一致,跳过: %s", rel)
                return True
            log.error("★冲突★ 本地视频与 NAS 同路径文件内容不一致(%s),不覆盖: %s", why, dest)
            return False
    except OSError:
        pass
    log.info("本地 -> NAS: %s -> %s", local_path, dest)
    try:
        _throttled_copy(local_path, dest, limiter)
        ok, why = files_match(local_path, dest)
    except OSError as e:
        log.error("本地->NAS 传输失败(本地原件保留): %s: %s", dest, e)
        try:
            os.remove(dest)
        except OSError:
            pass
        return False
    if not ok:
        log.error("本地->NAS 校验失败(本地原件保留): %s (%s)", dest, why)
        try:
            os.remove(dest)
        except OSError:
            pass
        return False
    return True


def clear_card_for_clip(clip: Clip, mf: Manifest) -> None:
    """在该片段已成功拷到本地并校验后,删除其 SD 卡上原件。"""
    rec = mf.clips.get(clip.clip_id, {})
    if rec.get("card_cleared"):
        return
    src = rec.get("src_path") or clip.src_path
    if src and os.path.isfile(src):
        try:
            os.remove(src)
            log.info("已删卡上原文件: %s", src)
        except OSError as e:
            log.error("删除卡上文件失败(本地副本已在,可稍后手动清): %s: %s", src, e)
            return
    rec["card_cleared"] = True
    mf.clips[clip.clip_id] = rec
    mf.save()


def _record_clip(mf: Manifest, clip: Clip, status: str, card_cleared: bool) -> None:
    old = mf.clips.get(clip.clip_id, {})
    mf.clips[clip.clip_id] = {
        "owner": clip.owner, "src_path": clip.src_path, "filename": clip.filename,
        "shot_time": clip.shot_time.isoformat(), "day_label": clip.day_label,
        "dest_path": clip.dest_path, "status": status,
        "card_cleared": card_cleared or old.get("card_cleared", False),
    }


# ====================================================================
#  抽帧工具(命令行调用,无 GUI、无弹窗)
# ====================================================================
#  直接把「某天文件夹」当参数丢给 exe,让它自己抽帧+抽音。工具自身幂等:
#    没抽的抽、抽一半的续、已完成的天跳过;需要整天重抽时加 --force。
#  不再走「双击 exe 起服务/弹选择框」那套——那是给人手点的 GUI 模式。

def _validate_artifacts(day_dir: str) -> tuple[bool, str]:
    """严格检查可归档产物；完成标记本身不能证明大文件已经上传完整。"""
    processed = os.path.join(day_dir, "processed")
    audio = os.path.join(day_dir, "audio")
    marker = os.path.join(processed, "preprocess_complete.json")
    frames_zip = os.path.join(processed, "frames_low.zip")
    try:
        if not os.path.isfile(marker):
            return False, f"缺完成标记:{marker}"
        with open(marker, "r", encoding="utf-8-sig") as f:
            json.load(f)
        if not os.path.isfile(frames_zip) or os.path.getsize(frames_zip) <= 0:
            return False, f"缺失或空的 frames_low.zip:{frames_zip}"
        if not zipfile.is_zipfile(frames_zip):
            return False, f"frames_low.zip 不是完整 ZIP:{frames_zip}"
        if not os.path.isdir(audio):
            return False, f"缺 audio 目录:{audio}"
        audio_files = [os.path.join(dp, name) for dp, _d, files in os.walk(audio) for name in files]
        if not audio_files or not any(os.path.getsize(p) > 0 for p in audio_files):
            return False, f"audio 中没有非空文件:{audio}"
    except (OSError, json.JSONDecodeError) as e:
        return False, f"读取产物失败:{e}"
    return True, "ok"


def _artifacts_present(day_dir: str) -> bool:
    ok, _why = _validate_artifacts(day_dir)
    return ok


def nas_reachable() -> bool:
    """NAS 根目录当前是否可达(用来决定能不能拿 NAS 当已归档的判据)。"""
    try:
        return os.path.isdir(NAS_ROOT)
    except OSError:
        return False


def nas_has_day(owner: str, label: str) -> bool:
    """
    NAS 上该天是否已归档 = 有【非空】processed\\ 且【非空】audio\\。
    这是「要不要传」的真正判据(NAS 才是产物的最终归宿);账本可能滞后/丢失,不可全信。
    NAS 不可达或读失败一律返回 False(宁可当没传,也不误跳过真没传的)。
    """
    base = os.path.join(NAS_ROOT, owner, label)
    proc = os.path.join(base, "processed")
    aud = os.path.join(base, "audio")
    try:
        ok, _why = _validate_artifacts(base)
        return ok
    except OSError:
        return False


def _scratch_processed_for(day_dir: str) -> str:
    """
    由天目录推出本地 scratch 的 processed 路径: SCRATCH_ROOT\\人名\\日期\\processed。
    用 basename 取 人名/日期 两级(不用 relpath),因此 day_dir 在 NAS 还是本地都不会跨盘崩溃。
    """
    norm = os.path.normpath(day_dir)
    label = os.path.basename(norm)
    owner = os.path.basename(os.path.dirname(norm))
    return os.path.join(SCRATCH_ROOT, owner, label, "processed")


def _scratch_ready(scratch_processed: str) -> bool:
    """本地 scratch 里是否已有完整帧产物(完成标记 + zip),可跳过抽帧直接续传。"""
    return (os.path.isfile(os.path.join(scratch_processed, "preprocess_complete.json"))
            and os.path.isfile(os.path.join(scratch_processed, "frames_low.zip")))


def _upload_processed_to_nas(src_processed: str, nas_processed: str,
                             force_recopy: bool = False) -> bool:
    """把本地 scratch 的 processed(frames_low.zip + 索引 + 完成标记)镜像上传到 NAS,并校验。
    帧已打成一个大 zip,是 SMB 友好的顺序大文件,传得快。"""
    rels = _rel_files(src_processed)
    if not rels:
        log.error("scratch processed 为空,无可上传: %s", src_processed)
        return False
    limiter = _RateLimiter(UPLOAD_MAX_MBPS)
    log.info("上传 processed -> NAS(%d 个文件,含 frames_low.zip,限速 %s MB/s): %s",
             len(rels), UPLOAD_MAX_MBPS if UPLOAD_MAX_MBPS else "不", nas_processed)
    try:
        # 完成标记最后发布；传输中断时其他流程不会把半成品误判为已完成。
        if not _upload_tree(src_processed, nas_processed, rels, limiter,
                            force_recopy=force_recopy,
                            publish_last={"preprocess_complete.json"}):
            return False
        # 校验: 清单齐全 + 每个文件大小一致。
        bad = []
        for rel in rels:
            s, d = os.path.join(src_processed, rel), os.path.join(nas_processed, rel)
            try:
                if not os.path.isfile(d) or os.path.getsize(d) != os.path.getsize(s):
                    bad.append(rel)
            except OSError:
                bad.append(rel)
        if bad:
            log.error("processed 上传后 %d 个文件缺失/大小不符,如: %s", len(bad), bad[:5])
            return False
        # sha256 抽检: frames_low.zip 必检(核心产物),其余小索引一并全检(数量少)。
        for rel in rels:
            ok, why = files_match(os.path.join(src_processed, rel),
                                  os.path.join(nas_processed, rel))
            if not ok:
                log.error("processed sha256 校验不一致(%s): %s", why, rel)
                return False
        log.info("processed 已上传并校验通过(%d 个文件)。", len(rels))
        return True
    except OSError as e:
        log.error("上传 processed 到 NAS 异常(NAS 掉线?): %s", e)
        return False


def upload_local_artifacts_to_nas(local_day_dir: str, owner: str, label: str,
                                  force_recopy: bool = False) -> bool:
    """上传旧流程遗留在本地的 processed/audio，并在 NAS 端严格校验。"""
    ok, why = _validate_artifacts(local_day_dir)
    if not ok:
        log.error("本地产物不完整,拒绝上传归档: %s (%s)", local_day_dir, why)
        return False
    if not nas_reachable():
        log.error("NAS(%s)不可达,无法上传本地产物。", NAS_ROOT)
        return False
    nas_day = nas_day_folder(owner, label)
    local_processed = os.path.join(local_day_dir, "processed")
    local_audio = os.path.join(local_day_dir, "audio")
    if not _upload_processed_to_nas(local_processed, os.path.join(nas_day, "processed"),
                                    force_recopy=force_recopy):
        return False
    audio_rels = _rel_files(local_audio)
    if not audio_rels:
        log.error("本地 audio 为空,拒绝归档: %s", local_audio)
        return False
    limiter = _RateLimiter(UPLOAD_MAX_MBPS)
    if not _upload_tree(local_audio, os.path.join(nas_day, "audio"), audio_rels, limiter,
                        force_recopy=force_recopy):
        return False
    return upload_day(LogicalDay(owner, label, []), nas_day)


def run_extract(day_dir: str, force: bool = False) -> bool:
    """
    抽帧+抽音,产出齐全并落到 NAS 才返回 True。day_dir 应为 NAS 上的天目录。
    做法(见配置区说明):video 从 NAS 读,帧 churn 用 --out 写本地 scratch(快),
    audio 直接写 NAS,抽完把本地 processed 传回 NAS,再删 scratch。
    force=True 强制整天重抽(用于:归档后又混入新片段,须重生成完整帧集)。
    """
    # NAS 已有完整产物(processed 里有完成标记 + audio\\ 在)且不强制 -> 跳过。
    if not force and _artifacts_present(day_dir):
        log.info("该天 NAS 上已抽帧完成,跳过。")
        return True
    if not os.path.isfile(PREPROCESS_EXE):
        die(f"找不到抽帧工具:{PREPROCESS_EXE}\n"
            f"    请确认 localpreprocess-win-x64.exe 在该路径,或改配置区 PREPROCESS_EXE。")
    video_dir = os.path.join(day_dir, "video")
    if not os.path.isdir(video_dir) or not find_videos(video_dir):
        log.error("该天没有可抽帧的 video\\,无法处理: %s", video_dir)
        return False

    scratch_processed = _scratch_processed_for(day_dir)

    # 抽帧阶段:若 scratch 已有完整产物且不强制(上轮抽完但传 NAS 失败)-> 跳过抽帧直接续传。
    if force or not _scratch_ready(scratch_processed):
        try:
            if os.path.isdir(scratch_processed):
                shutil.rmtree(scratch_processed)  # 清掉半成品重抽
            os.makedirs(scratch_processed, exist_ok=True)
        except OSError as e:
            log.error("无法准备本地 scratch 目录 %s: %s", scratch_processed, e)
            return False
        cmd = [PREPROCESS_EXE, day_dir,
               "--out", scratch_processed,
               "--fps", str(PREPROCESS_FPS),
               "--frame-max-edge", str(PREPROCESS_FRAME_MAX_EDGE)]
        if force:
            cmd.append("--force")
        log.info("抽帧(video读NAS,帧写本地scratch%s): %s", "·强制重抽" if force else "", day_dir)
        try:
            proc = subprocess.run(
                cmd, cwd=os.path.dirname(PREPROCESS_EXE),
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace",
                timeout=PREPROCESS_JOB_TIMEOUT_SEC,
            )
        except subprocess.TimeoutExpired:
            log.error("抽帧超时(> %ds),视为失败。", PREPROCESS_JOB_TIMEOUT_SEC)
            return False
        except OSError as e:
            die(f"无法启动抽帧工具: {e}")
        for line in (proc.stdout or "").splitlines():
            if line.strip():
                log.debug("  抽帧: %s", line)
        # 退出码:0=全部成功;1=有段失败;2=参数/环境错误。仅 0 视为成功。
        if proc.returncode != 0:
            log.error("抽帧退出码 %s(非全部成功),视为失败,本轮不归档该日。", proc.returncode)
            return False
        if not _scratch_ready(scratch_processed):
            log.error("抽帧报成功(exit 0),但本地 scratch 缺 preprocess_complete.json 或 frames_low.zip,视为失败。")
            return False
        if not os.path.isdir(os.path.join(day_dir, "audio")) or \
           not os.listdir(os.path.join(day_dir, "audio")):
            log.error("抽帧报成功,但 NAS 上 audio\\ 缺失/为空,视为失败: %s", day_dir)
            return False
        log.info("抽帧完成(本地 scratch 就绪),开始把 processed 传回 NAS。")
    else:
        log.info("本地 scratch 已有完整帧产物(上轮抽好),跳过抽帧,直接续传 NAS。")

    # 上传阶段:本地 processed -> NAS processed。成功才清 scratch;失败保留 scratch 供下轮续传。
    nas_processed = os.path.join(day_dir, "processed")
    if not _upload_processed_to_nas(scratch_processed, nas_processed):
        log.error("processed 传 NAS 失败,保留本地 scratch(下轮跳过重抽直接续传): %s", scratch_processed)
        return False
    day_scratch = os.path.dirname(scratch_processed)       # scratch\人名\日期
    owner_scratch = os.path.dirname(day_scratch)           # scratch\人名
    try:
        shutil.rmtree(day_scratch)
        if os.path.isdir(owner_scratch) and not os.listdir(owner_scratch):
            os.rmdir(owner_scratch)  # 顺手删空的人名夹,不留空壳
    except OSError as e:
        log.warning("清理本地 scratch 失败(不影响归档,可手动删): %s: %s", scratch_processed, e)
    log.info("抽帧+上传完成:processed 已在 NAS,本地 scratch 已清。")
    return True


# ====================================================================
#  上传 NAS
# ====================================================================

def _rel_files(root: str) -> list[str]:
    out = []
    for dp, _d, files in os.walk(root):
        for name in files:
            out.append(os.path.relpath(os.path.join(dp, name), root))
    return out


class _RateLimiter:
    """全局令牌桶:多线程共享,总字节速率不超过 mbps。mbps<=0 则不限。"""

    def __init__(self, mbps: float):
        self.rate = mbps * 1024 * 1024
        # 至少容纳一次 1 MiB 读块；否则 mbps<4 时永远攒不够一次 acquire。
        self.burst = max(self.rate / 4, 1024 * 1024)
        self.lock = threading.Lock()
        self.tokens = 0.0           # 起始为空,避免第一波免费突发冲垮 NAS 缓存
        self.last = time.monotonic()

    def acquire(self, n: int) -> None:
        if self.rate <= 0:
            return
        while True:
            with self.lock:
                now = time.monotonic()
                self.tokens = min(self.burst, self.tokens + (now - self.last) * self.rate)
                self.last = now
                if self.tokens >= n:
                    self.tokens -= n
                    return
                wait = (n - self.tokens) / self.rate
            time.sleep(min(wait, 0.1))


def _copy_once(src: str, dst: str, tmp: str, limiter: _RateLimiter,
               cancel: dict, result: dict) -> None:
    """真正干活的一次拷贝(在 worker 线程里跑):src->tmp 限速拷 + fsync + 原子改名到 dst。
    fsync 可能在 NAS 上长时间不返回;超时判定由主线程 _throttled_copy 负责。"""
    try:
        with open(src, "rb") as fs, open(tmp, "wb") as fd:
            while True:
                chunk = fs.read(1024 * 1024)
                if not chunk:
                    break
                limiter.acquire(len(chunk))
                fd.write(chunk)
            fd.flush()
            os.fsync(fd.fileno())          # ← 可能在此卡死;主线程超时后会弃本线程
        shutil.copystat(src, tmp)
        if cancel.get("x"):                # 主线程已判超时放弃 -> 别再动 dst,清掉自己的半成品
            try:
                os.remove(tmp)
            except OSError:
                pass
            return
        _atomic_replace_with_retry(tmp, dst)
        result["ok"] = True
    except BaseException as e:              # 连 fsync 的 OSError 一并兜住,交主线程重试
        result["err"] = e
        try:
            os.remove(tmp)
        except OSError:
            pass


def _cleanup_parts(dst: str) -> None:
    """清掉 dst 对应的 .part 半成品(能删就删;句柄仍被弃线程占用的删不掉,留给 _upload_tree 兜底)。"""
    d, base = os.path.dirname(dst), os.path.basename(dst)
    try:
        for f in os.listdir(d):
            if f.startswith(base + ".part."):
                try:
                    os.remove(os.path.join(d, f))
                except OSError:
                    pass
    except OSError:
        pass


def _throttled_copy(src: str, dst: str, limiter: _RateLimiter) -> None:
    """限速拷 src->dst(卡→NAS / 本地→NAS 通用),带 NAS 卡死超时 + 重试保护。
    每次尝试在独立 daemon 线程里跑;若 timeout_s 内未完成(疑似 SMB fsync 无响应),
    弃该句柄、清半成品、换新句柄重试;全部失败才抛出(上层 fail-closed,不清卡)。"""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        size_mb = max(1.0, os.path.getsize(src) / (1024 * 1024))
    except OSError:
        size_mb = 1024.0
    timeout_s = size_mb / max(0.1, NAS_WRITE_MIN_MBPS) + NAS_WRITE_GRACE_S
    last_err: BaseException | None = None
    for attempt in range(NAS_WRITE_RETRIES + 1):
        tmp = f"{dst}.part.{os.getpid()}.{threading.get_ident()}.{attempt}"
        cancel: dict = {}
        result: dict = {}
        worker = threading.Thread(
            target=_copy_once, args=(src, dst, tmp, limiter, cancel, result), daemon=True)
        worker.start()
        worker.join(timeout_s)
        if not worker.is_alive():
            if result.get("ok"):
                return
            last_err = result.get("err") or RuntimeError("拷贝失败(原因未知)")
            log.warning("写 NAS 失败(第 %d/%d 次)将重试:%s(%s)",
                        attempt + 1, NAS_WRITE_RETRIES + 1, os.path.basename(dst), last_err)
        else:
            cancel["x"] = True             # 通知弃线程别再改 dst;它是 daemon,会随进程退出
            last_err = TimeoutError(
                f"写 NAS 超时 {timeout_s:.0f}s(疑似 SMB fsync 无响应),已弃句柄重试")
            log.warning("★写 NAS 卡死超时 %.0fs(第 %d/%d 次),弃句柄重试:%s",
                        timeout_s, attempt + 1, NAS_WRITE_RETRIES + 1, os.path.basename(dst))
        _cleanup_parts(dst)
        time.sleep(2)
    raise last_err if last_err else RuntimeError(f"写 NAS 反复失败:{dst}")


def _upload_tree(src_sub: str, dst_sub: str, rels: list[str], limiter: _RateLimiter,
                 force_recopy: bool = False, publish_last: set[str] | None = None) -> bool:
    """镜像 src->dst:已在且大小一致的跳过(断传续跑),多余的删,其余多线程限速拷。
    force_recopy=True 时不信任已有文件,全部重写覆盖(用于目标侧疑似写坏的场景)。"""
    os.makedirs(dst_sub, exist_ok=True)
    for extra in set(_rel_files(dst_sub)) - set(rels):  # 清 NAS 侧多余/半成品
        try:
            os.remove(os.path.join(dst_sub, extra))
        except OSError:
            pass
    publish_last = publish_last or set()
    # 发布阶段开始前先撤掉旧完成标记，避免读者把正在更新的目录视为完整。
    for rel in publish_last:
        try:
            os.remove(os.path.join(dst_sub, rel))
        except FileNotFoundError:
            pass
        except OSError as e:
            log.error("无法撤掉旧完成标记 %s: %s", rel, e)
            return False
    todo = []
    for rel in rels:
        s, d = os.path.join(src_sub, rel), os.path.join(dst_sub, rel)
        if not force_recopy:
            try:
                if os.path.isfile(d) and os.path.getsize(d) == os.path.getsize(s):
                    ok, _why = files_match(s, d)
                    if ok:
                        continue
            except OSError:
                pass
        todo.append(rel)
    if not todo:
        return True
    errors: list[str] = []
    done = [0]
    lk = threading.Lock()

    def work(rel: str) -> None:
        try:
            _throttled_copy(os.path.join(src_sub, rel), os.path.join(dst_sub, rel), limiter)
        except OSError as e:
            with lk:
                errors.append(f"{rel}: {e}")
            return
        with lk:
            done[0] += 1
            if done[0] % 5000 == 0:
                log.info("  上传进度: %d/%d", done[0], len(todo))

    normal = [rel for rel in todo if rel not in publish_last]
    last = [rel for rel in todo if rel in publish_last]
    for batch in (normal, last):
        if not batch:
            continue
        with concurrent.futures.ThreadPoolExecutor(max_workers=UPLOAD_MT_THREADS) as ex:
            list(ex.map(work, batch))
        if errors:
            break
    if errors:
        log.error("上传有 %d 个文件失败,如: %s", len(errors), errors[:3])
        return False
    return True


def upload_day(day: LogicalDay, day_dir: str, force_recopy: bool = False) -> bool:
    """
    新流程:抽帧工具直接把 processed/audio 输出到 NAS 上的 day_dir,不再有本地->NAS 拷贝。
    此函数只做归档校验:
      - NAS 上 processed\\preprocess_complete.json 存在
      - processed\\ 下有帧文件(非空)、audio\\ 非空
    通过 -> 视为归档。
    day_dir 应传 nas_day_folder(owner, label)。
    force_recopy: 保留参数以兼容 upload_all.py,新流程下无意义。
    """
    if force_recopy:
        log.info("提示:force_recopy 在新流程下无效果(产物已直接写 NAS)。")
    try:
        if os.path.commonpath([os.path.abspath(day_dir), os.path.abspath(NAS_ROOT)]) != os.path.abspath(NAS_ROOT):
            log.error("归档校验拒绝非 NAS 目录: %s", day_dir)
            return False
    except ValueError:
        log.error("归档校验拒绝非 NAS 目录: %s", day_dir)
        return False
    ok, why = _validate_artifacts(day_dir)
    if not ok:
        log.error("NAS 产物不齐全,该日不归档: %s (%s)", day_dir, why)
        return False
    log.info("NAS 归档校验通过: %s", day_dir)
    return True


def _delete_raw_dir(drec: dict, folder: str, mf: Manifest) -> None:
    """删除该日原始视频 video\\ 释放磁盘(帧/音频留着),并把其片段标记 raw_deleted。"""
    vdir = os.path.join(folder, "video")
    if os.path.isdir(vdir):
        try:
            size = sum(os.path.getsize(os.path.join(dp, f))
                       for dp, _d, fs in os.walk(vdir) for f in fs)
            shutil.rmtree(vdir)
            log.info("已删原始视频(封口),释放 %.1f GB: %s", size / 1024**3, vdir)
        except OSError as e:
            log.error("删除原始视频失败(不影响归档,下次再清): %s: %s", vdir, e)
            return
    for cid in drec.get("clip_ids", []):
        if cid in mf.clips:
            mf.clips[cid]["raw_deleted"] = True
    drec["raw_deleted"] = True


# ====================================================================
#  封口与本地清理:已归档 + 够老 + 稳定 + 覆盖正常,才删本地
# ====================================================================
#  两级删除,都以 day_is_sealed 为准(比上传保守,防多卡缺段被抢删):
#    1) 达封口条件 -> 删原始视频 video\(占 9 成空间);帧/音频先留着。
#    2) 再满 DESKTOP_RETENTION_DAYS 天 -> 删整个本地日文件夹(帧全在 NAS)。
#  未归档却已超龄、或有覆盖异常的天:一律保留不删,并报警提醒你补卡/排查。

def seal_and_cleanup(mf: Manifest, now: datetime) -> None:
    for dkey, drec in list(mf.days.items()):
        if drec.get("local_purged"):
            continue
        label, owner = drec.get("day_label", ""), drec.get("owner", "")
        age = _age_days(label, now)
        folder = day_folder(owner, label)

        if drec.get("status") != "archived":
            if age >= DESKTOP_RETENTION_DAYS and os.path.isdir(folder):
                log.warning("★注意★ %s 已满 %d 天但【未成功归档 NAS】,保留不删。"
                            "请检查该日抽帧/上传是否失败(或有人卡忘带、数据未齐)。", folder, age)
            continue

        sealed, reason = day_is_sealed(drec, now)
        if not sealed:
            if age >= DESKTOP_RETENTION_DAYS:
                log.info("%s 已归档但暂不删本地(%s),继续保留。", dkey, reason)
            continue

        # 1) 封口:删原始视频。
        if DELETE_RAW_AFTER_ARCHIVE and not drec.get("raw_deleted"):
            _delete_raw_dir(drec, folder, mf)
            mf.days[dkey] = drec
            mf.save()

        # 2) 再满保留期:删整个本地日文件夹(帧/音频也在 NAS 上)。
        if age >= DESKTOP_RETENTION_DAYS and os.path.isdir(folder):
            log.info("清理已归档本地文件夹(封口且留存 %d 天已到): %s", age, folder)
            try:
                shutil.rmtree(folder)
            except OSError as e:
                log.error("删除本地文件夹失败: %s: %s", folder, e)
                continue
            drec["local_purged"] = True
            mf.days[dkey] = drec
            for cid in drec.get("clip_ids", []):
                if cid in mf.clips:
                    mf.clips[cid]["status"] = "purged"
            mf.save()


# ====================================================================
#  总表
# ====================================================================

def print_summary(days_by_owner: dict[str, list[LogicalDay]], mf: Manifest,
                  no_upload: bool = False) -> None:
    up = "(本次不传NAS)" if no_upload else "+传NAS"
    print("\n" + "=" * 82)
    print("本次识别到的逻辑日汇总")
    print("=" * 82)
    for owner in sorted(days_by_owner):
        print(f"\n[{owner}]")
        print(f"  {'日期':<10} {'片段':>4} {'卡上新增':>6}  {'起':<12} {'止':<12} 本次动作")
        print("  " + "-" * 72)
        for d in days_by_owner[owner]:
            t0 = min(c.shot_time for c in d.clips).strftime("%m-%d %H:%M")
            t1 = max(c.shot_time for c in d.clips).strftime("%m-%d %H:%M")
            # 卡上待新拷的 = 尚未清卡的片段;其余为「已在本地」。
            new_n = sum(1 for c in d.clips
                        if not mf.clips.get(c.clip_id, {}).get("card_cleared", False))
            archived = (mf.days.get(d.key, {}).get("status") == "archived")
            if new_n:
                action = "拷贝+清卡" + (f"+抽帧{up}" if d.process_now else "(拍摄中,暂不抽帧)")
            elif archived:
                action = "已上传NAS(已改名),封口后清本地"
            elif d.process_now:
                action = f"已在本地→本次抽帧{up}"
            elif d.complete:
                action = "已在本地;其卡不在位,本轮不动"
            else:
                action = "已在本地,拍完后再抽帧+传NAS"
            flag = "  ★覆盖异常" if (d.complete and coverage_issues(d.clips)) else ""
            print(f"  {d.label:<10} {len(d.clips):>4} {new_n:>6}  {t0:<12} {t1:<12} {action}{flag}")
    print("\n" + "=" * 82)


def _build_roster_lines(mf: Manifest, present_owners: set[str], now: datetime) -> list[str]:
    """构造花名册看板的文本行(打印与落盘共用同一份内容)。"""
    owners: dict[str, dict[str, dict]] = {}
    for dkey, drec in mf.days.items():
        owner = drec.get("owner") or dkey.split("/")[0]
        label = drec.get("day_label") or dkey.split("/")[-1]
        owners.setdefault(owner, {})[label] = drec
    all_owners = sorted(set(owners) | present_owners)
    if not all_owners:
        return []

    def _mark(r: dict) -> str:
        if r.get("local_purged"):
            return "清"          # 本地已清(已在 NAS)
        if r.get("status") == "archived":
            return "传"          # 已上传 NAS
        return "缺" if r.get("coverage_issues") else "待"

    lines = [
        "=" * 82,
        f"花名册看板(谁的卡多日未见 = 数据可能在缺,需催其补交)   更新于 "
        f"{now.strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 82,
        f"  {'人':<10} {'卡在位':<6} {'最近采集日':<11} {'距今':>4} {'待传':>4} {'已传':>4}  最近几日",
        "  " + "-" * 74,
    ]
    for owner in all_owners:
        days = owners.get(owner, {})
        present = "是" if owner in present_owners else "—"
        if days:
            last = max(days)
            age = _age_days(last, now)
        else:
            last, age = "无", -1
        pending = sum(1 for r in days.values() if r.get("status") != "archived"
                      and not r.get("local_purged"))
        archived = sum(1 for r in days.values() if r.get("status") == "archived")
        recent = " ".join(f"{l[-4:]}:{_mark(days[l])}" for l in sorted(days)[-5:]) or "—"
        warn = ""
        if owner not in present_owners and 0 <= STALE_PROCESS_DAYS <= age:
            warn = f"  ★卡已{age}天未见"
        if any(r.get("coverage_issues") and r.get("status") != "archived"
               for r in days.values()):
            warn += "  ★有天覆盖异常"
        age_s = str(age) if age >= 0 else "-"
        lines.append(f"  {owner:<10} {present:<6} {last:<11} {age_s:>4} {pending:>4} "
                     f"{archived:>4}  {recent}{warn}")
    lines.append("  图例:待=待传  传=已上传NAS  清=本地已清  缺=覆盖异常疑似缺段")
    lines.append("=" * 82)
    return lines


def _write_roster_file(lines: list[str]) -> None:
    """把看板落盘到 ROSTER_FILE(UTF-8,记事本可读),原子替换成最新一份。"""
    try:
        os.makedirs(os.path.dirname(ROSTER_FILE), exist_ok=True)
        tmp = ROSTER_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        os.replace(tmp, ROSTER_FILE)
    except OSError as e:
        log.warning("花名册看板落盘失败(不影响主流程): %s", e)


def print_roster(mf: Manifest, present_owners: set[str], now: datetime) -> None:
    """
    花名册看板:横向看每个人最近几天到底齐没齐、传没传。
    重点是替你发现「谁的卡好几天没出现 -> 可能忘带、数据在缺」。
    脚本不替你猜:它只把线索(卡在不在、最近采集日、待传/已传、覆盖异常)摆出来。
    既打印到终端,又覆盖写一份到 采集录像\\花名册看板.txt 供事后查看。
    """
    lines = _build_roster_lines(mf, present_owners, now)
    if not lines:
        return
    print("")
    for ln in lines:
        print(ln)
    _write_roster_file(lines)


# ====================================================================
#  --register:仅列出卡与检测到的归属
# ====================================================================

def cmd_register() -> None:
    log.info("枚举当前可移动卷(驱动器类型 %s)...", sorted(CONSIDER_DRIVE_TYPES))
    cards = enumerate_card_volumes()
    if not cards:
        log.info("未发现可移动卷。若卡被读卡器报告为固定盘,可临时把 3 加入 CONSIDER_DRIVE_TYPES。")
        return
    print("\n盘符   卷标                 视频数   检测到的归属(来自卡上人名.txt)")
    print("-" * 66)
    for root, label in cards:
        owner = read_owner_marker(root) or "<未认领:请放一个 人名.txt>"
        try:
            nvid = len(find_videos(root))
        except OSError:
            nvid = -1
        print(f"{root:<6} {label:<20.20} {nvid:>5}   {owner}")
    print("-" * 66)
    print("\n在每张卡的根目录放一个【以人名命名】的 txt(如 Jeffery.txt,内容可空),即为该卡归属。")
    print("相机自带的 SETTINGS.txt 等会被自动忽略;卡根目录请只保留这一个人名 txt。")


# ====================================================================
#  主流程
# ====================================================================

def run_pipeline(dry_run: bool, assume_yes: bool, process_all: bool = False,
                 no_upload: bool = False, no_extract: bool = False) -> None:
    mf = Manifest.load()

    # 0) 启动期:封口 + 本地清理(已归档 且 够老 且 稳定 且 覆盖正常 才删本地)。
    if not dry_run:
        seal_and_cleanup(mf, datetime.now())

    # 1) 枚举在位卡,靠卡上「人名.txt」认领。有视频却没认领 -> 停机。
    present_cards: list[tuple[str, str]] = []
    for root, label in enumerate_card_volumes():
        vids = find_videos(root)
        owner = read_owner_marker(root)
        if owner:
            present_cards.append((root, owner))
            log.info("识别卡: %s 卷标 %r 归属 %s (%d 个视频)", root, label, owner, len(vids))
        elif vids:
            die(f"发现未认领的卡: 盘符 {root} 卷标 {label!r}(含 {len(vids)} 个视频)。\n"
                f"    在该卡根目录放一个【以人名命名】的 txt(如 Jeffery.txt)后重跑,\n"
                f"    并确保卡根目录只有这一个人名 txt。绝不猜测归属。")

    # 2) 汇集片段,按人切分逻辑日。
    all_clips = gather_clips(present_cards, mf)
    if not all_clips:
        log.info("没有待处理的片段。")
        return

    clips_by_owner: dict[str, list[Clip]] = {}
    for clip in all_clips.values():
        clips_by_owner.setdefault(clip.owner, []).append(clip)

    now = datetime.now()
    present_owners = {owner for _root, owner in present_cards}
    days_by_owner: dict[str, list[LogicalDay]] = {}
    all_days: list[LogicalDay] = []
    for owner, clips in clips_by_owner.items():
        days = segment_days(owner, clips)
        for d in days:
            d.complete = day_is_complete(d, now)
            if d.complete:
                # 只处理卡在位的人;搁置超期的自动补;--all 全处理。
                age = (now.date() - datetime.strptime(d.label, "%Y%m%d").date()).days
                d.process_now = (process_all or owner in present_owners
                                 or age >= STALE_PROCESS_DAYS)
        days_by_owner[owner] = days
        all_days.extend(days)

    # 2.5) ★以 NAS 为准核对★:逐天去 NAS 读 processed\+audio\ 在不在。
    #    在 = 这天早传好了 -> 标记 archived,后面不再重抽重传(只信本地账本会误判)。
    #    不在 = 真没传 -> 保持 pending,正常抽帧+上传。
    #    NAS 不可达时不敢乱标,退回只看账本,并【大声报警】(否则会把已传的又传一遍)。
    if nas_reachable():
        healed = 0
        for d in all_days:
            drec = mf.days.setdefault(d.key, {
                "owner": d.owner, "day_label": d.label, "status": "pending", "clip_ids": []})
            if drec.get("status") == "archived":
                continue
            # 安全闩:该天若还有【卡上尚未拷入】的新片段(典型:迟到补交的卡),
            # 别急着按 NAS 标归档(那会把这些新片段当成已在 NAS 而漏掉);
            # 让它走正常流程,该合并的合并、该重抽重传的重抽重传。
            if any(not mf.clips.get(c.clip_id, {}).get("card_cleared", False) for c in d.clips):
                continue
            if nas_has_day(d.owner, d.label):
                drec["status"] = "archived"
                drec.setdefault("archived_at", datetime.now().isoformat())
                drec["archived_clip_ids"] = sorted({c.clip_id for c in d.clips})
                drec.setdefault("clip_ids", sorted({c.clip_id for c in d.clips}))
                healed += 1
                log.info("NAS 上已有 %s 的 processed+audio,标记已归档,跳过重抽重传。", d.key)
                if not dry_run:
                    mark_day_archived(d.owner, d.label)
        if healed:
            log.info("已按 NAS 现状把 %d 天标记为已归档(它们无需再抽帧/上传)。", healed)
            if not dry_run:
                mf.save()
    else:
        log.warning("★NAS(%s)当前不可达★ 无法核对哪些天已归档,本轮只能按本地账本判断,"
                    "可能把【其实已在 NAS】的天又列为待传。请确认已映射网络盘 Z:(net use Z: \\\\主机\\共享)。",
                    NAS_ROOT)

    # 3) 总表 + 花名册看板 + 一次性确认。
    print_summary(days_by_owner, mf, no_upload)
    print_roster(mf, present_owners, now)
    if dry_run:
        log.info("--dry-run:仅到总表为止,不拷贝/不清卡/不抽帧/不上传。")
        return
    if not assume_yes:
        tail = "完整日再抽帧,本次不传NAS" if no_upload else "完整日再抽帧+传NAS"
        resp = input(f"\n开始执行(拷贝到本地->清卡;{tail})?输入 y 继续,其它退出: ").strip().lower()
        if resp != "y":
            log.info("用户未确认(输入 %r),退出,未做任何破坏性操作。", resp)
            return

    # 4) 逐日:每段视频【卡 -> NAS 直传】并校验;成功即清卡,失败报警保留。
    #    本地不落 video,不做本地磁盘预检。NAS 空间通常远大于卡容量,不额外预检。
    copy_failures: list[str] = []
    day_has_failure: dict[str, bool] = {}
    claimed: set[str] = set()
    # 卡->NAS 全局限速器(所有片段共享,总速率不超过 UPLOAD_MAX_MBPS)。
    transfer_limiter = _RateLimiter(UPLOAD_MAX_MBPS)
    for d in all_days:
        drec0 = mf.days.get(d.key, {})
        cur_ids = {c.clip_id for c in d.clips}
        # 已归档且【没有新片段】的天:冻结,别动。
        if drec0.get("status") == "archived":
            archived_ids = set(drec0.get("archived_clip_ids") or drec0.get("clip_ids") or [])
            if cur_ids <= archived_ids:
                continue

        for clip in d.clips:
            if copy_clip(clip, mf, claimed, transfer_limiter):
                clear_card_for_clip(clip, mf)
            else:
                copy_failures.append(clip.dest_path or clip.clip_id)
                day_has_failure[d.key] = True
        rec = mf.days.setdefault(d.key, {
            "owner": d.owner, "day_label": d.label,
            "status": "pending", "clip_ids": [],
        })
        # 补齐 clip_ids(今天新拍的片段并入同一日);片段集变大则记「最后新增时间」。
        prev_ids = set(rec.get("clip_ids", []))
        merged_ids = prev_ids | cur_ids
        if merged_ids - prev_ids:
            rec["last_new_clip_at"] = now.isoformat()
        rec["clip_ids"] = sorted(merged_ids)
        # 记录该日覆盖情况(供封口判定/看板用;此刻有 Clip 在手,算得准)。
        rec["coverage_issues"] = coverage_issues(d.clips)
    mf.save()

    if no_extract:
        log.info("--no-extract:卡→NAS+清卡已完成,按要求跳过抽帧/归档(稍后统一抽帧)。")
        if copy_failures:
            _report_copy_failures(copy_failures)
        return

    # 5) 阶段化:先把所有该处理的日【全部抽帧】,再【统一上传 NAS】。
    #    (拷贝在第 4 步已全部完成;抽帧是本地活、上传是网络活,分阶段互不拖累。)
    for d in (x for x in all_days if x.complete and not x.process_now):
        log.info("逻辑日 %s 已拍完但其卡不在位,本轮不动;其卡插入时处理(搁置满 %d 天会自动补)。",
                 d.key, STALE_PROCESS_DAYS)
    complete_days = [d for d in all_days if d.process_now]

    # 5a) 抽帧阶段(不碰 NAS)。命令行逐日调用抽帧工具,无需服务、无弹窗。
    to_upload: list[LogicalDay] = []
    force_days: set[str] = set()  # 归档后被打回的天:整天强制重抽(--force)
    for d in complete_days:
        drec = mf.days.get(d.key, {})
        cur_ids = sorted({c.clip_id for c in d.clips})
        if drec.get("status") == "archived":
            # 归档后又混入新片段(典型:同一人另一张卡隔天才交)-> 打回重抽重传。
            archived_ids = set(drec.get("archived_clip_ids") or drec.get("clip_ids") or cur_ids)
            if set(cur_ids) <= archived_ids:
                log.info("逻辑日 %s 已归档,跳过。", d.key)
                continue
            # 安全闩:若这天早先的原视频已按策略删除,整日重抽会只含新片段、
            # 覆盖 NAS 导致丢帧 -> 停下这天,留人工处理,绝不覆盖。
            if any(mf.clips.get(c.clip_id, {}).get("raw_deleted") for c in d.clips):
                log.error("★人工处理★ 逻辑日 %s 已归档且原视频已删,又出现新片段;"
                          "无法安全整日重抽(会覆盖 NAS 丢旧帧)。请人工决定如何合并。", d.key)
                continue
            log.warning("逻辑日 %s 归档后出现新片段(%d -> %d),打回重新抽帧+上传。",
                        d.key, len(archived_ids), len(cur_ids))
            drec["status"] = "pending"
            mf.days[d.key] = drec
            mf.demoted_days.add(d.key)  # 主动打回,合并保存时本方赢
            force_days.add(d.key)       # 已有完成标记,须 --force 才会重抽含新片段
            mf.save()
        if day_has_failure.get(d.key):
            log.error("逻辑日 %s 有片段传输失败,跳过其抽帧/归档(数据仍在卡上,请处理后重跑)。", d.key)
            continue
        # 抽帧对着 NAS 上的日目录直接进行(video 已在,processed/audio 也生成在 NAS)。
        day_dir = nas_day_folder(d.owner, d.label)
        log.info("==== 阶段2·抽帧(NAS) %s ====", d.key)
        if run_extract(day_dir, force=(d.key in force_days)):
            to_upload.append(d)
        else:
            log.error("逻辑日 %s 抽帧未通过验证,本轮不归档该日。", d.key)

    # 5b) 归档校验阶段(processed/audio 已在 NAS,这里只做产物齐全性校验)。
    if no_upload:
        if to_upload:
            log.info("--no-upload:已抽帧 %d 天,归档校验交由「上传全部到NAS」流程处理。",
                     len(to_upload))
        log.info("本次(仅拷卡+抽帧)完成。")
        if copy_failures:
            _report_copy_failures(copy_failures)
        return
    for d in to_upload:
        day_dir = nas_day_folder(d.owner, d.label)
        log.info("==== 阶段3·归档校验(NAS) %s ====", d.key)
        if not upload_day(d, day_dir):
            log.error("逻辑日 %s 归档校验失败,不标记归档(下次重跑)。", d.key)
            continue
        drec = mf.days.get(d.key, {})
        drec["status"] = "archived"
        drec["archived_at"] = datetime.now().isoformat()
        drec["archived_clip_ids"] = sorted({c.clip_id for c in d.clips})
        mf.days[d.key] = drec
        mf.save()
        log.info("逻辑日 %s 已归档。", d.key)

    # 6) 收尾:清理本地历史遗留(老版本的 桌面\人名\日期\ 文件夹)。
    seal_and_cleanup(mf, datetime.now())
    if copy_failures:
        _report_copy_failures(copy_failures)
    log.info("全部处理完成。")


def _report_copy_failures(copy_failures: list[str]) -> "NoReturn":  # type: ignore[name-defined]
    log.error("=" * 60)
    log.error("★有 %d 个视频卡->NAS 传输失败,已保留在 SD 卡上(未清卡):", len(copy_failures))
    for x in copy_failures[:20]:
        log.error("    %s", x)
    log.error("请检查 NAS 连通/映射盘 Z:/坏文件后重跑。")
    log.error("=" * 60)
    sys.exit(1)


# ====================================================================
#  入口
# ====================================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="SD 卡视频采集流水线(Windows 单机)")
    parser.add_argument("--register", action="store_true",
                        help="仅列出各卡与检测到的归属(读卡上的 人名.txt),不做任何处理。")
    parser.add_argument("--dry-run", action="store_true",
                        help="只做到打印总表为止,不拷贝/不清卡/不抽帧/不上传。")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="跳过 y/N 确认(无人值守日常运行用)。")
    parser.add_argument("--all", action="store_true", dest="process_all",
                        help="处理所有人的完整日(默认只处理卡在位的人;搁置超期的自动补)。")
    parser.add_argument("--no-upload", action="store_true", dest="no_upload",
                        help="旧流程兼容参数；当前直传 NAS 架构不支持执行，仅可配合 --dry-run 查看。")
    parser.add_argument("--no-extract", action="store_true", dest="no_extract",
                        help="只做 卡→NAS+清卡,跳过抽帧/归档(稍后统一抽帧;用于优先腾卡)。")
    args = parser.parse_args()

    setup_logging()
    if os.name != "nt":
        die("本脚本依赖 Windows 卷 API,仅支持 Windows。")
    if args.no_upload and not args.dry_run:
        die("当前流程从 SD 卡直接写 NAS，无法安全实现 --no-upload。"
            "请去掉该参数运行；如只想预览，请使用 --dry-run。")

    try:
        if args.register:
            cmd_register()
        elif args.dry_run:
            run_pipeline(dry_run=True, assume_yes=args.yes, process_all=args.process_all,
                         no_upload=args.no_upload)
        else:
            # 当前执行流程都会写 NAS 和 manifest，因此统一拿双锁独占。
            if not acquire_lock("all"):
                sys.exit(3)
            try:
                run_pipeline(dry_run=False, assume_yes=args.yes,
                             process_all=args.process_all, no_upload=args.no_upload,
                             no_extract=args.no_extract)
            finally:
                release_lock()
    except PipelineError as e:
        die(str(e))
    except KeyboardInterrupt:
        die("用户中断。")


if __name__ == "__main__":
    main()
