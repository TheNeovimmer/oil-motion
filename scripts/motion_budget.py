#!/usr/bin/env python3
"""根据最终显示尺寸计算交互动画的像素与图集预算。"""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass


def parse_size(value: str) -> tuple[int, int]:
    normalized = value.lower().replace("×", "x").strip()
    try:
        width_text, height_text = normalized.split("x", 1)
        width, height = int(width_text), int(height_text)
    except (ValueError, AttributeError) as exc:
        raise argparse.ArgumentTypeError("尺寸必须写成 WIDTHxHEIGHT") from exc
    if width <= 0 or height <= 0:
        raise argparse.ArgumentTypeError("宽高必须大于 0")
    return width, height


@dataclass(frozen=True)
class SizeCheck:
    width: int
    height: int
    required_width: int
    required_height: int
    width_ratio: float
    height_ratio: float
    passes: bool


def check_size(size: tuple[int, int], required: tuple[int, int]) -> SizeCheck:
    width, height = size
    required_width, required_height = required
    return SizeCheck(
        width=width,
        height=height,
        required_width=required_width,
        required_height=required_height,
        width_ratio=round(width / required_width, 3),
        height_ratio=round(height / required_height, 3),
        passes=width >= required_width and height >= required_height,
    )


def build_report(args: argparse.Namespace) -> dict[str, object]:
    display_width, display_height = args.display
    required = (
        math.ceil(display_width * args.dpr),
        math.ceil(display_height * args.dpr),
    )
    required_width, required_height = required
    max_columns = args.max_texture // required_width
    max_rows = args.max_texture // required_height
    capacity = max_columns * max_rows
    sheets = math.ceil(args.frames / capacity) if capacity else None
    decoded_mib = (
        required_width * required_height * args.frames * 4 / 1024 / 1024
    )

    if capacity == 0:
        recommendation = "降低显示尺寸，或改用视频 / WebCodecs"
    elif args.access == "sequential" and (args.frames > 120 or (sheets or 0) > 2):
        recommendation = "视频解码；需要精确跳帧时使用 WebCodecs"
    elif sheets == 1:
        recommendation = "单张图集"
    elif sheets is not None and sheets <= 8:
        recommendation = "分片图集"
    else:
        recommendation = "视频 / WebCodecs"

    failures: list[str] = []
    source_check = check_size(args.source, required) if args.source else None
    cell_check = check_size(args.cell, required) if args.cell else None
    if source_check and not source_check.passes:
        failures.append("源素材低于最终显示所需像素")
    if cell_check and not cell_check.passes:
        failures.append("图集单帧低于最终显示所需像素")
    if capacity == 0:
        failures.append("单帧已超过纹理尺寸上限")

    temporal_check = None
    if args.scroll_pages is not None:
        required_frames = math.ceil(args.scroll_pages * args.frames_per_page)
        frames_per_page = args.frames / args.scroll_pages
        temporal_check = {
            "scrollPages": args.scroll_pages,
            "framesPerPage": round(frames_per_page, 2),
            "targetFramesPerPage": args.frames_per_page,
            "requiredFrames": required_frames,
            "passes": args.frames >= required_frames,
        }
        if not temporal_check["passes"]:
            failures.append(
                f"滚动采样密度不足：需要至少 {required_frames} 帧"
            )

    return {
        "display": {
            "width": display_width,
            "height": display_height,
            "dpr": args.dpr,
        },
        "requiredCell": {
            "width": required_width,
            "height": required_height,
        },
        "frames": args.frames,
        "texture": {
            "maxSize": args.max_texture,
            "columnsPerSheet": max_columns,
            "rowsPerSheet": max_rows,
            "framesPerSheet": capacity,
            "sheetCount": sheets,
        },
        "decodedFrameMemoryMiB": round(decoded_mib, 1),
        "sourceCheck": asdict(source_check) if source_check else None,
        "cellCheck": asdict(cell_check) if cell_check else None,
        "temporalCheck": temporal_check,
        "access": args.access,
        "recommendation": recommendation,
        "failures": failures,
        "passes": not failures,
    }


def print_human(report: dict[str, object]) -> None:
    display = report["display"]
    required = report["requiredCell"]
    texture = report["texture"]
    print(
        f"显示尺寸：{display['width']}×{display['height']} CSS px，"
        f"DPR {display['dpr']}"
    )
    print(f"最低单帧：{required['width']}×{required['height']} px")
    print(
        f"纹理预算：每片最多 {texture['columnsPerSheet']}×"
        f"{texture['rowsPerSheet']} 帧，共需 {texture['sheetCount']} 片"
    )
    print(f"全部帧解码内存理论值：{report['decodedFrameMemoryMiB']} MiB")

    for label, key in (("源素材", "sourceCheck"), ("当前单帧", "cellCheck")):
        check = report[key]
        if check:
            status = "通过" if check["passes"] else "不通过"
            print(
                f"{label}：{check['width']}×{check['height']} px，{status}"
                f"（宽 {check['width_ratio']}×，高 {check['height_ratio']}×）"
            )

    temporal = report["temporalCheck"]
    if temporal:
        status = "通过" if temporal["passes"] else "不通过"
        print(
            f"滚动采样：{temporal['framesPerPage']} 帧/屏，{status}"
            f"（目标 {temporal['targetFramesPerPage']} 帧/屏，"
            f"至少 {temporal['requiredFrames']} 帧）"
        )

    print(f"推荐格式：{report['recommendation']}")
    failures = report["failures"]
    if failures:
        print("阻断项：")
        for failure in failures:
            print(f"- {failure}")
    else:
        print("结果：通过")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="根据 CSS 显示尺寸、DPR、帧数和纹理上限检查动画资源预算。"
    )
    parser.add_argument("--frames", type=int, required=True, help="总帧数")
    parser.add_argument(
        "--display", type=parse_size, required=True, help="最终 CSS 尺寸，如 268x468"
    )
    parser.add_argument("--dpr", type=float, default=2.0, help="目标设备 DPR")
    parser.add_argument(
        "--max-texture", type=int, default=4096, help="保守纹理边长上限"
    )
    parser.add_argument(
        "--access",
        choices=("random", "sequential"),
        default="random",
        help="运行时主要访问方式",
    )
    parser.add_argument("--source", type=parse_size, help="源视频或母版帧尺寸")
    parser.add_argument("--cell", type=parse_size, help="当前图集单帧尺寸")
    parser.add_argument(
        "--scroll-pages",
        type=float,
        help="滚动驱动覆盖的视口屏数；传入后同时检查时间采样密度",
    )
    parser.add_argument(
        "--frames-per-page",
        type=float,
        default=24.0,
        help="每屏目标帧数，默认 24",
    )
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    parser.add_argument(
        "--strict", action="store_true", help="存在阻断项时返回非零退出码"
    )
    args = parser.parse_args()

    if args.frames <= 0:
        parser.error("--frames 必须大于 0")
    if args.dpr <= 0:
        parser.error("--dpr 必须大于 0")
    if args.max_texture <= 0:
        parser.error("--max-texture 必须大于 0")
    if args.scroll_pages is not None and args.scroll_pages <= 0:
        parser.error("--scroll-pages 必须大于 0")
    if args.frames_per_page <= 0:
        parser.error("--frames-per-page 必须大于 0")

    report = build_report(args)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_human(report)
    return 2 if args.strict and not report["passes"] else 0


if __name__ == "__main__":
    sys.exit(main())
