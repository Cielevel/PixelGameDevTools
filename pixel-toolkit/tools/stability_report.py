#!/usr/bin/env python3
"""稳定性读数离线脚本（方案 §7 固化：原 /tmp/evidence.py 易失，此文件是它的正式形态）。

口径与 `pixel-toolkit/stability.py` / `video-studio.html` 的 `computeStability()` 完全一致
（方案 §1）；用途是把「调参只能靠肉眼」变成「看数 + 可被任何人重跑」。

用法：
    python3 tools/stability_report.py <帧目录或 PNG...> [--max-flip 5] [--max-colors 3] [--json]

    # 复现方案 §1 基线（12fps / 48 帧 / 64×64 / 跨帧共享 16 色板）
    python3 pixcli.py video-std <视频> -o /tmp/out --fps 12 --size 64x64 --colors 16
    python3 tools/stability_report.py /tmp/out --json

exit 0 = 通过门禁；exit 1 = 超标或样本不足（可接 CI）。
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import stability


def collect(inputs):
    files = []
    for p in inputs:
        if os.path.isdir(p):
            files += sorted(f for f in glob.glob(os.path.join(p, "*.png"))
                            if not f.lower().endswith("_sheet.png"))   # sheet 不是帧（同 anim.expand_input）
        elif any(ch in p for ch in "*?["):
            files += sorted(f for f in glob.glob(p)
                            if not f.lower().endswith("_sheet.png"))
        else:
            files.append(p)
    missing = [f for f in files if not os.path.isfile(f)]
    if missing:
        raise SystemExit("错误：文件不存在: " + ", ".join(missing))
    if not files:
        raise SystemExit("错误：未找到任何 PNG 帧")
    return files


def main(argv=None):
    ap = argparse.ArgumentParser(prog="stability_report", description=__doc__.splitlines()[0])
    ap.add_argument("inputs", nargs="+", help="帧目录 / PNG 文件 / glob（按文件名排序即时间序）")
    ap.add_argument("--preset", choices=sorted(stability.PRESETS), default="strict",
                    help="阈值档位：strict=§1 门禁 5%%/3.0（默认）| standard=验收档 10%%/3.5 | "
                         "quick=回归探测档 15%%/4.0；显式 --max-flip/--max-colors 覆盖档位")
    ap.add_argument("--max-flip", type=float, default=None,
                    help="核心静态格变色率门禁 %%（不给则用档位值）")
    ap.add_argument("--max-colors", type=float, default=None,
                    help="单格平均色数门禁（不给则用档位值）")
    ap.add_argument("--min-static", type=int, default=stability.STATIC_MIN,
                    help="静态格下限，低于此数报样本不足（默认 %(default)s）")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出指标（供脚本比对）")
    args = ap.parse_args(argv)

    paths = collect(args.inputs)
    stats = stability.analyze_paths(paths)
    max_flip, max_colors = stability.preset(args.preset)
    if args.max_flip is not None:
        max_flip = args.max_flip
    if args.max_colors is not None:
        max_colors = args.max_colors
    ok, issues = stability.verdict(stats, max_flip, max_colors, args.min_static)
    if args.json:
        print(json.dumps(dict(stats or {}, ok=ok, issues=issues, preset=args.preset,
                              maxFlip=max_flip, maxColors=max_colors), ensure_ascii=False))
    else:
        print("[stability] {} 帧 {}　档位 {}".format(len(paths), paths[0], args.preset))
        print("  " + stability.format_stats(stats))
        print("  静态格变色率 {:.1f}% / 核心 {:.1f}%  门禁 ≤{:.1f}%".format(
            stats["flipAll"], stats["flipCore"], max_flip))
        print("  单格平均色数 {:.2f}  门禁 ≤{:.2f}".format(stats["avgColors"], max_colors))
        for msg in issues:
            print("  ✗ " + msg)
        print("  → {}".format("通过" if ok else "不通过"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
