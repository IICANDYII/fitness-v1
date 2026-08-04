# -*- coding: utf-8 -*-
r"""一次性:把本地所有【已抽帧完成、未归档】的日文件夹 限速上传 NAS,
校验通过 -> 登记账本 archived -> 删除该日原始视频 video\ 释放磁盘。
(含手动拷入的、不在账本里的日文件夹。遵守流水线互斥锁。)"""
import importlib.util, sys, os, re
from datetime import date, datetime

spec = importlib.util.spec_from_file_location(
    "pipe", r"E:\01Internship\Relty\diet_balance_baseline\sd_video_pipeline.py")
m = importlib.util.module_from_spec(spec)
sys.modules["pipe"] = m
spec.loader.exec_module(m)
m.setup_logging()

if not m.acquire_lock("nas"):  # 只拿 NAS 锁:可与「拷卡抽帧-不传NAS」并行
    print("有别的 NAS 上传流程在跑,退出。")
    sys.exit(3)

try:
    mf = m.Manifest.load()
    ROOT = m.DESKTOP_ROOT
    today = date.today().strftime("%Y%m%d")
    targets = []
    for owner_dir in sorted(os.listdir(ROOT)):
        odir = os.path.join(ROOT, owner_dir)
        if not os.path.isdir(odir) or owner_dir.lower() == "logs":
            continue
        owner = owner_dir.lower()  # NAS/账本统一小写(SMB 不区分大小写)
        for dirname in sorted(os.listdir(odir)):
            ddir = os.path.join(odir, dirname)
            mt = re.fullmatch(r"(\d{8})(?:" + re.escape(m.ARCHIVED_SUFFIX) + r")?", dirname)
            if not mt:
                continue
            day = mt.group(1)
            if day >= today:
                continue
            marker = os.path.join(ddir, "processed", "preprocess_complete.json")
            if not os.path.isfile(marker):
                continue  # 没抽帧完成的不传
            key = m.day_key(owner, day)
            if mf.days.get(key, {}).get("status") == "archived":
                print(f"跳过 {key}(账本:已归档)")
                continue
            # ★以 NAS 为准★:NAS 上已有 processed+audio 就别再传(账本可能滞后)。
            if m.nas_has_day(owner, day):
                print(f"跳过 {key}(NAS 上已有 processed+audio)")
                drec = mf.days.setdefault(key, {"owner": owner, "day_label": day, "clip_ids": []})
                drec["status"] = "archived"
                drec.setdefault("archived_at", datetime.now().isoformat())
                mf.days[key] = drec
                mf.save()
                m.mark_day_archived(owner, day)
                continue
            targets.append((owner, day, ddir, key))

    print(f"\n待上传 {len(targets)} 天\n" + "=" * 50)
    results = []
    for owner, day, ddir, key in targets:
        # jeffery/20260707 在 NAS 缓存被打爆时写过半截,疑似有坏文件 -> 强制全量重写覆盖
        force = (key == "jeffery/20260707")
        print(f"\n>>> 上传 {key}{'(强制全量重写)' if force else ''}")
        ok = m.upload_local_artifacts_to_nas(ddir, owner, day, force_recopy=force)
        if ok:
            drec = mf.days.get(key, {"owner": owner, "day_label": day, "clip_ids": []})
            drec["status"] = "archived"
            drec["archived_at"] = datetime.now().isoformat()
            drec["archived_clip_ids"] = drec.get("clip_ids", [])
            mf.days[key] = drec
            mf.save()
            # 改名标记 (已上传);【不立即删原视频】——交由主脚本的封口判定
            # (够老+稳定+覆盖正常)再删,防多卡缺段被抢删。
            m.mark_day_archived(owner, day)
        results.append((key, ok))

    print("\n" + "=" * 50)
    print("上传结果汇总:")
    for key, ok in results:
        print(f"  {key}: {'已上传+改名(已上传)(原视频待封口后清)' if ok else '★失败(本地数据保留)'}")
    fails = [r for r in results if not r[1]]
    print(f"\n共 {len(results)} 天,成功 {len(results)-len(fails)},失败 {len(fails)}")
    sys.exit(1 if fails else 0)
finally:
    m.release_lock()
