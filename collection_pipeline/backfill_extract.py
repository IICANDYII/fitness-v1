# -*- coding: utf-8 -*-
"""
补抽帧 / 本地恢复(新流程:卡直传 NAS 版)
====================================================================
用途:处理「本地还留着 video、但 NAS 上没归档」的天。典型来源:
  - 老流程遗留(video 先拷到了本地 C:\\...\\采集录像\\人名\\日期\\video\\,卡已清、
    还没上 NAS,如 0720 那批因当时磁盘满没跑完)。
  - 早期漏处理 / 抽帧失败的天。

对每个这样的天,做:
  1. 把本地 video\\ 里的每段【上传 NAS 并校验】(NAS 已有且一致的跳过);
  2. 全部上齐后,对 NAS 上的该天抽帧(video 读 NAS、帧写本地 scratch、audio 写 NAS、
     processed 传回 NAS)—— 复用主脚本 run_extract;
  3. 归档校验通过 -> 账本记 archived;
  4. 【删掉本地该天文件夹】释放磁盘(video 已在 NAS,帧/音频也在 NAS)。

命令行:
  python backfill_extract.py            列出待恢复的天,输 y 才执行
  python backfill_extract.py --yes      跳过确认(无人值守)
  python backfill_extract.py --dry-run  只列出待恢复清单,不上传/不抽帧/不删本地
  python backfill_extract.py --keep-local  恢复后【不删】本地(默认删,以释放磁盘)
====================================================================
"""
import argparse
import importlib.util
import os
import re
import shutil
import sys
from datetime import datetime

# 复用主脚本的全部逻辑(路径/抽帧/上传/账本/锁),避免两份实现走偏。
_PIPE = r"E:\01Internship\Relty\diet_balance_baseline\sd_video_pipeline.py"
spec = importlib.util.spec_from_file_location("pipe", _PIPE)
m = importlib.util.module_from_spec(spec)
sys.modules["pipe"] = m
spec.loader.exec_module(m)

_DAYDIR_RE = re.compile(r"^(\d{8})(?:" + re.escape(m.ARCHIVED_SUFFIX) + r")?$")


def _label_of(dirname: str) -> str | None:
    """把 20260720 或 20260720(已上传) 解析成 20260720;不是日文件夹返回 None。"""
    mt = _DAYDIR_RE.match(dirname)
    return mt.group(1) if mt else None


def find_targets() -> list[tuple[str, str, str]]:
    """返回需要恢复的 [(owner, label, 本地folder)]:本地有 video、且 NAS 未归档。"""
    root = m.DESKTOP_ROOT
    targets: list[tuple[str, str, str]] = []
    seen_days: dict[tuple[str, str], str] = {}
    for owner_dir in sorted(os.listdir(root)):
        odir = os.path.join(root, owner_dir)
        if not os.path.isdir(odir) or owner_dir.lower() == "logs":
            continue
        owner = owner_dir.lower()  # 账本/NAS 统一小写
        for day_dir in sorted(os.listdir(odir)):
            label = _label_of(day_dir)
            if not label:
                continue
            folder = os.path.join(odir, day_dir)
            vids = m.find_videos(os.path.join(folder, "video"))
            if not vids:
                continue                       # 没本地原视频,无从恢复
            if m.nas_has_day(owner, label):
                continue                       # NAS 上已归档(processed+audio 齐),不用管
            prior = seen_days.get((owner, label))
            if prior:
                raise m.PipelineError(
                    f"同一个逻辑日存在两个本地目录,无法安全判断如何合并:\n    {prior}\n    {folder}\n"
                    "请先人工合并 video 后再运行恢复脚本。")
            seen_days[(owner, label)] = folder
            targets.append((owner, label, folder))
    return targets


def _recover_day(owner: str, label: str, folder: str, mf, keep_local: bool,
                 no_extract: bool = False) -> bool:
    key = m.day_key(owner, label)
    limiter = m._RateLimiter(m.UPLOAD_MAX_MBPS)
    local_video_root = os.path.join(folder, "video")
    vids = m.find_videos(local_video_root)

    # 1) 本地 video -> NAS(逐段校验)。任一失败则整天中止(本地全保留)。
    m.log.info("==== 恢复 %s:本地 video(%d 段)-> NAS ====", key, len(vids))
    for v in vids:
        rel = os.path.relpath(v, local_video_root)
        if not m.upload_local_video_to_nas(v, owner, label, limiter, relative_path=rel):
            m.log.error("%s 有段上传 NAS 失败,本天中止(本地全部保留,下次重试)。", key)
            return False

    if no_extract:
        m.log.info("==== %s:--no-extract,仅上传 video 到 NAS(不抽帧/不归档,保留本地)====", key)
        return True

    # 2) 对 NAS 上该天抽帧(复用主脚本:video 读 NAS、帧写本地 scratch、processed 回传 NAS)。
    nas_day = m.nas_day_folder(owner, label)
    m.log.info("==== 恢复 %s:抽帧 ====", key)
    if not m.run_extract(nas_day):
        m.log.error("%s 抽帧未通过,本天中止(本地保留)。", key)
        return False

    # 3) 归档校验 -> 账本记 archived。
    if not m.upload_day(m.LogicalDay(owner, label, []), nas_day):
        m.log.error("%s 归档校验失败,本天中止(本地保留)。", key)
        return False
    drec = mf.days.setdefault(key, {"owner": owner, "day_label": label, "clip_ids": []})
    drec["status"] = "archived"
    drec.setdefault("archived_at", datetime.now().isoformat())
    mf.days[key] = drec
    mf.save()

    # 4) 删本地该天文件夹释放磁盘(video/帧/音频都已在 NAS)。除非 --keep-local。
    if keep_local:
        m.log.info("%s 已归档 NAS;--keep-local,本地保留。", key)
    else:
        try:
            size = sum(os.path.getsize(os.path.join(dp, f))
                       for dp, _d, fs in os.walk(folder) for f in fs)
            shutil.rmtree(folder)
            m.log.info("%s 已归档 NAS,已删本地释放 %.1f GB: %s", key, size / 1024**3, folder)
        except OSError as e:
            m.log.error("%s 已归档,但删本地失败(可手动删): %s: %s", key, folder, e)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(
        description="本地恢复:本地有 video、NAS 未归档的天,上传 NAS + 抽帧 + 归档 + 删本地")
    parser.add_argument("--yes", "-y", action="store_true", help="跳过 y 确认(无人值守)。")
    parser.add_argument("--dry-run", action="store_true", help="只列出待恢复清单,不动数据。")
    parser.add_argument("--keep-local", action="store_true",
                        help="恢复后不删本地(默认删,以释放磁盘)。")
    parser.add_argument("--no-extract", action="store_true", dest="no_extract",
                        help="只把本地 video 上传 NAS(不抽帧/不归档/保留本地),抽帧交给并行抽帧器。")
    args = parser.parse_args()

    m.setup_logging()
    if os.name != "nt":
        m.die("本脚本依赖 Windows,仅支持 Windows。")
    if not m.nas_reachable():
        m.die(f"NAS({m.NAS_ROOT})不可达。先确认 Z: 已映射再跑。")

    targets = find_targets()
    total_gb = 0.0
    print("\n" + "=" * 72)
    print(f"需要恢复的天(本地有 video、NAS 未归档):{len(targets)}")
    print("=" * 72)
    for owner, label, folder in targets:
        vd = os.path.join(folder, "video")
        n = len(m.find_videos(vd))
        try:
            gb = sum(os.path.getsize(os.path.join(dp, f))
                     for dp, _d, fs in os.walk(vd) for f in fs) / 1024**3
        except OSError:
            gb = 0.0
        total_gb += gb
        print(f"  {owner:<10} {label}   {n:>3} 段   {gb:6.1f} GB   {folder}")
    print("=" * 72)
    print(f"合计约 {total_gb:.1f} GB 待上传 NAS")
    if not targets:
        print("没有需要恢复的天。")
        return
    if args.dry_run:
        print("--dry-run:仅列出,不动数据。")
        return
    if not args.yes:
        tail = "(恢复后保留本地)" if args.keep_local else "(恢复成功后【删本地】释放磁盘)"
        resp = input(f"\n开始恢复:本地 video 上传 NAS + 抽帧 + 归档{tail}?输入 y 继续: ").strip().lower()
        if resp != "y":
            print("已退出,未做任何处理。")
            return

    # 上传 + 抽帧 + 删本地都要动 -> 拿双锁(与主脚本互斥)。
    if not m.acquire_lock("all"):
        print("有别的流水线在跑(锁被占),退出。")
        sys.exit(3)
    try:
        mf = m.Manifest.load()
        results: list[tuple[str, bool]] = []
        for owner, label, folder in targets:
            key = m.day_key(owner, label)
            try:
                ok = _recover_day(owner, label, folder, mf,
                                  args.keep_local or args.no_extract, no_extract=args.no_extract)
            except Exception as e:  # 单天异常不拖垮整批
                m.log.error("%s 恢复中异常(本地保留): %s", key, e)
                ok = False
            results.append((key, ok))

        print("\n" + "=" * 72)
        print("恢复结果:")
        for key, ok in results:
            if not ok:
                msg = '★失败(本地数据保留)'
            elif args.no_extract:
                msg = '已上传NAS(未抽帧,本地保留)'
            else:
                msg = '已上传NAS+抽帧+归档' + ('' if args.keep_local else '(本地已删)')
            print(f"  {key}: {msg}")
        fails = [r for r in results if not r[1]]
        print(f"\n共 {len(results)} 天,成功 {len(results)-len(fails)},失败 {len(fails)}")
        sys.exit(1 if fails else 0)
    finally:
        m.release_lock()


if __name__ == "__main__":
    main()
