# -*- coding: utf-8 -*-
"""并行抽帧 worker：对一个【NAS 上的天目录】抽帧。
- 复用主脚本 sd_video_pipeline 的 run_extract:video 从 NAS 读、帧写本地 scratch、
  processed 回传 NAS、audio 写 NAS,抽完清 scratch。
- 每个 worker 只处理一个天目录,scratch 路径按 人/日 隔离,多个 worker 天然互不干扰。
- 不写 manifest(归属由 NAS 目录结构保证;nas_has_day 按 NAS 产物判定)。
用法:
  python extract_one_day.py "Z:\\Processed Videos\\<人名>\\<日期>"
退出码:0=成功或已抽过;1=抽帧未通过;2=用法/环境错误。
"""
import sys
import importlib.util

_PIPE = r"E:\01Internship\Relty\diet_balance_baseline\sd_video_pipeline.py"
_spec = importlib.util.spec_from_file_location("pipe", _PIPE)
m = importlib.util.module_from_spec(_spec)
sys.modules["pipe"] = m
_spec.loader.exec_module(m)


def _owner_label(day_dir: str):
    """从 NAS 天目录 ...\\<人名>\\<日期> 取 (人名, 日期标签)。"""
    norm = m.os.path.normpath(day_dir)
    return m.os.path.basename(m.os.path.dirname(norm)), m.os.path.basename(norm)


def main() -> None:
    args = sys.argv[1:]
    check_only = False
    if args and args[0] == "--check-sealed":
        # 编排器预筛用:只判该天是否已封口(可抽),不做任何抽帧。
        # 退出码 0=已封口可抽;3=未封口暂不抽;2=用法/环境错。
        check_only = True
        args = args[1:]
    if not args:
        print("用法: extract_one_day.py [--check-sealed] <NAS 天目录>")
        sys.exit(2)
    day_dir = args[0]
    m.setup_logging()
    if m.os.name != "nt":
        m.die("仅支持 Windows。")

    owner, label = _owner_label(day_dir)

    # 永久跳过名单(数据已知损坏等):两种模式都最先判,命中就直接跳过。
    if m.day_in_skiplist(owner, label):
        if check_only:
            print(f"SKIP {owner}/{label}: 在永久跳过名单 EXTRACT_SKIP_DAYS 里")
            sys.exit(3)
        print(f"[skip] {owner}/{label} 在永久跳过名单里,不抽: {day_dir}")
        sys.exit(0)

    if check_only:
        sealed, why = m.day_sealed_for_extract(owner, label)
        print(f"{'SEALED' if sealed else 'UNSEALED'} {owner}/{label}: {why}")
        sys.exit(0 if sealed else 3)

    if not m.nas_reachable():
        print(f"NAS 不可达,跳过: {day_dir}")
        sys.exit(2)
    if m._artifacts_present(day_dir):
        print(f"[skip] 已有完整产物,跳过: {day_dir}")
        sys.exit(0)
    vids = m.find_videos(m.os.path.join(day_dir, "video"))
    if not vids:
        print(f"[skip] 无 video,跳过: {day_dir}")
        sys.exit(0)
    # 封口闸门:该人尚未出现「次日 02:00 后」的数据 -> 这天可能还没传完,暂不抽(留到以后)。
    sealed, why = m.day_sealed_for_extract(owner, label)
    if not sealed:
        print(f"[skip] 该天未封口,暂不抽({why}): {day_dir}")
        sys.exit(0)
    ok = m.run_extract(day_dir)
    print(f"[{'OK' if ok else 'FAIL'}] {day_dir}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
