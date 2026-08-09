#!/usr/bin/env python3
"""把绿幕动作母版编译为可精确寻帧的全关键帧 MP4。

适合一维连续参数控制的大尺寸动画。脚本强制插帧并保留均匀色键背景，网页使用
WebGL 实时抠色；最终页面背景不会写进视频。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from statistics import median
from typing import Any

from PIL import Image

from motion_pipeline import remove_key


SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE = SCRIPT_DIR / "motion_pipeline.py"
CLEANUP = SCRIPT_DIR / "loop_cleanup.py"
OPTIMIZE = SCRIPT_DIR / "optimize_motion.py"


def run(command: list[str]) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, check=True)


def require_command(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(f"找不到 {name}，请先安装 ffmpeg")


def probe(path: Path) -> dict[str, Any]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-of",
            "json",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


def video_stream(report: dict[str, Any]) -> dict[str, Any]:
    for stream in report.get("streams", []):
        if stream.get("codec_type") == "video":
            return stream
    raise ValueError("输入文件没有视频流")


def dimensions_for_width(
    requested_width: int,
    source_width: int,
    source_height: int,
    allow_upscale: bool,
) -> tuple[int, int]:
    width = requested_width
    if width > source_width and not allow_upscale:
        width = source_width
        print(
            f"提示：请求宽度 {requested_width}px 超过母版，自动限制为 {source_width}px",
            flush=True,
        )
    width = max(2, width - width % 2)
    height = round(width * source_height / source_width)
    height = max(2, height - height % 2)
    return width, height


def image_frames(directory: Path) -> list[Path]:
    return sorted(directory.glob("frame_*.png"))


def representative_frames(paths: list[Path], limit: int = 48) -> list[Path]:
    if limit < 1:
        raise ValueError("代表帧数量必须大于 0")
    if len(paths) <= limit:
        return paths
    if limit == 1:
        return [paths[0]]
    return [
        paths[round(index * (len(paths) - 1) / (limit - 1))]
        for index in range(limit)
    ]


def border_samples(path: Path) -> list[tuple[int, int, int]]:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    width, height = image.size
    band = max(1, min(width, height, 6))
    step = max(1, min(width, height) // 256)
    pixels = image.load()
    samples: list[tuple[int, int, int]] = []
    for x in range(0, width, step):
        for offset in range(band):
            samples.append(pixels[x, offset])
            samples.append(pixels[x, height - 1 - offset])
    for y in range(0, height, step):
        for offset in range(band):
            samples.append(pixels[offset, y])
            samples.append(pixels[width - 1 - offset, y])
    return samples


def sample_key_color(path: Path) -> tuple[int, int, int]:
    samples = border_samples(path)
    return tuple(
        int(round(median(sample[channel] for sample in samples)))
        for channel in range(3)
    )


def key_color_hex(key: tuple[int, int, int]) -> str:
    return f"#{key[0]:02X}{key[1]:02X}{key[2]:02X}"


def validate_key_source(
    paths: list[Path],
    key: tuple[int, int, int],
) -> dict[str, object]:
    red, green, blue = key
    if green >= red + 40 and green >= blue + 40:
        kind = "green"
    elif red >= green + 40 and blue >= green + 40:
        kind = "magenta"
    else:
        raise ValueError("母版边缘不是可识别的绿色或洋红色键背景")
    checked = representative_frames(paths)
    worst_spread = 0
    for path in checked:
        spreads = sorted(
            max(abs(color[channel] - key[channel]) for channel in range(3))
            for color in border_samples(path)
        )
        spread_p95 = spreads[round((len(spreads) - 1) * 0.95)]
        worst_spread = max(worst_spread, spread_p95)
        if spread_p95 > 32:
            raise ValueError(
                f"母版色键边缘不均匀：{path.name} 的 95% 色差范围为 "
                f"{spread_p95}，上限 32"
            )
    return {
        "kind": kind,
        "borderSpreadP95Max": worst_spread,
        "checkedFrames": len(checked),
    }


def prepare_alpha_qa_frames(
    source_frames: list[Path],
    output: Path,
    key: tuple[int, int, int],
) -> None:
    output.mkdir(parents=True, exist_ok=True)
    for index, frame in enumerate(source_frames, start=1):
        remove_key(
            frame,
            output / f"frame_{index:05d}.png",
            key,
            transparent_threshold=12,
            opaque_threshold=220,
        )


def load_budget_report(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"找不到预算报告：{path}")
    report = json.loads(path.read_text(encoding="utf-8"))
    delivery = report.get("delivery", {})
    if delivery.get("selected") != "chroma-video":
        raise ValueError("预算报告没有选择 chroma-video，禁止执行视频编译路线")
    if not report.get("passes"):
        raise ValueError("预算报告存在阻断项，禁止执行视频编译路线")
    return report


def require_interpolation_pass(path: Path) -> dict[str, Any]:
    report = json.loads(path.read_text(encoding="utf-8"))
    verdict = report.get("verdict", {})
    if not verdict.get("passedAutomaticChecks"):
        raise RuntimeError("插帧自动检查未通过，禁止继续编码视频")
    return report


def encode_all_intra(
    frames: Path,
    output: Path,
    fps: float,
    width: int,
    height: int,
    crf: int,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "warning",
            "-y",
            "-framerate",
            str(fps),
            "-start_number",
            "1",
            "-i",
            str(frames / "frame_%05d.png"),
            "-vf",
            f"scale={width}:{height}:flags=lanczos,setsar=1",
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            str(crf),
            "-g",
            "1",
            "-keyint_min",
            "1",
            "-sc_threshold",
            "0",
            "-pix_fmt",
            "yuv420p",
            "-an",
            "-movflags",
            "+faststart",
            str(output),
        ]
    )


def all_frames_are_keyframes(path: Path) -> bool:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "frame=key_frame",
            "-of",
            "csv=p=0",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    values = [
        line.strip().split(",", 1)[0]
        for line in completed.stdout.splitlines()
        if line.strip()
    ]
    return bool(values) and all(value == "1" for value in values)


def safe_prepare_output(output: Path, force: bool) -> None:
    output = output.resolve()
    if output == Path(output.anchor) or output == Path.home().resolve():
        raise ValueError("输出目录不能是磁盘根目录或用户主目录")
    if output.exists() and any(output.iterdir()):
        if not force:
            raise FileExistsError(f"输出目录非空：{output}；确认后使用 --force")
        for item in output.iterdir():
            if item.is_dir() and not item.is_symlink():
                shutil.rmtree(item)
            else:
                item.unlink()
    output.mkdir(parents=True, exist_ok=True)


def compile_motion(args: argparse.Namespace) -> int:
    require_command("ffmpeg")
    require_command("ffprobe")

    source = Path(args.source).expanduser().resolve()
    output = Path(args.output_dir).expanduser().resolve()
    budget_path = Path(args.budget_report).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"找不到视频：{source}")
    budget_report = load_budget_report(budget_path)
    if args.loop and args.end_reference:
        raise ValueError("--loop 与 --end-reference 不能同时使用")
    if args.fps <= 0:
        raise ValueError("--fps 必须大于 0")
    if args.desktop_width < 2 or args.mobile_width < 2:
        raise ValueError("输出宽度必须至少为 2")
    if not 0 <= args.desktop_crf <= 51 or not 0 <= args.mobile_crf <= 51:
        raise ValueError("CRF 必须在 0–51 之间")
    if args.seam_window < 1:
        raise ValueError("--seam-window 必须至少为 1")
    if args.duplicate_threshold < 0:
        raise ValueError("--duplicate-threshold 不能小于 0")
    if args.contact_columns < 1:
        raise ValueError("--contact-columns 必须至少为 1")
    safe_prepare_output(output, args.force)

    source_probe = probe(source)
    source_video = video_stream(source_probe)
    source_width = int(source_video["width"])
    source_height = int(source_video["height"])

    interpolation = output / "interpolation"
    raw_frames = interpolation / "frames"
    cleaned_frames = output / "frames" / "final"
    alpha_qa_frames = output / "frames" / "alpha-qa"
    qa = output / "qa"
    final = output / "final"
    qa.mkdir(parents=True, exist_ok=True)
    final.mkdir(parents=True, exist_ok=True)

    run(
        [
            sys.executable,
            str(OPTIMIZE),
            "interpolate",
            str(source),
            str(interpolation),
            "--fps",
            str(args.fps),
            "--key",
            "none",
        ]
    )
    interpolation_report_path = interpolation / "interpolation-report.json"
    interpolation_report = require_interpolation_pass(
        interpolation_report_path
    )
    raw_count = len(image_frames(raw_frames))
    if raw_count < 3:
        raise RuntimeError("母版切帧后少于 3 帧")

    if args.loop or args.end_reference:
        cleanup_command = [
            sys.executable,
            str(CLEANUP),
            str(raw_frames),
            str(cleaned_frames),
            "--seam-window",
            str(args.seam_window),
            "--duplicate-threshold",
            str(args.duplicate_threshold),
            "--report",
            str(qa / "cleanup.json"),
        ]
        if args.end_reference:
            cleanup_command.extend(
                [
                    "--end-reference",
                    str(Path(args.end_reference).expanduser().resolve()),
                ]
            )
        run(cleanup_command)
        final_frames = cleaned_frames
    else:
        final_frames = raw_frames
        print("提示：未传 --loop 或 --end-reference，使用全部插帧", flush=True)

    final_frame_paths = image_frames(final_frames)
    if not final_frame_paths:
        raise RuntimeError("清理后没有可编码帧")
    final_count = len(final_frame_paths)
    detected_key = sample_key_color(final_frame_paths[0])
    detected_key_color = key_color_hex(detected_key)
    key_validation = validate_key_source(final_frame_paths, detected_key)
    alpha_qa_sources = representative_frames(final_frame_paths)
    prepare_alpha_qa_frames(alpha_qa_sources, alpha_qa_frames, detected_key)
    shutil.copy2(
        image_frames(alpha_qa_frames)[0],
        final / "poster-alpha.png",
    )
    run(
        [
            sys.executable,
            str(PIPELINE),
            "analyze",
            str(alpha_qa_frames),
            "--output",
            str(qa / "analysis.json"),
        ]
    )
    run(
        [
            sys.executable,
            str(PIPELINE),
            "contact",
            str(alpha_qa_frames),
            "--output",
            str(qa / "contact-sheet.jpg"),
            "--columns",
            str(args.contact_columns),
        ]
    )
    shutil.rmtree(alpha_qa_frames)

    desktop_size = dimensions_for_width(
        args.desktop_width,
        source_width,
        source_height,
        args.allow_upscale,
    )
    mobile_size = dimensions_for_width(
        args.mobile_width,
        source_width,
        source_height,
        args.allow_upscale,
    )
    desktop_output = final / "motion-chroma-desktop.mp4"
    mobile_output = final / "motion-chroma-mobile.mp4"
    encode_all_intra(
        final_frames,
        desktop_output,
        args.fps,
        desktop_size[0],
        desktop_size[1],
        args.desktop_crf,
    )
    encode_all_intra(
        final_frames,
        mobile_output,
        args.fps,
        mobile_size[0],
        mobile_size[1],
        args.mobile_crf,
    )

    desktop_probe = probe(desktop_output)
    mobile_probe = probe(mobile_output)
    manifest = {
        "source": {
            "path": str(source),
            "width": source_width,
            "height": source_height,
            "probe": source_probe,
        },
        "compile": {
            "backgroundOwner": "page",
            "detectedKeyColor": detected_key_color,
            "keyValidation": key_validation,
            "fps": args.fps,
            "rawFrameCount": raw_count,
            "finalFrameCount": final_count,
            "alphaQaFrameCount": len(alpha_qa_sources),
            "duration": final_count / args.fps,
            "cleanup": (
                "loop"
                if args.loop
                else "end-reference"
                if args.end_reference
                else "none"
            ),
            "duplicateThreshold": args.duplicate_threshold,
            "seamWindow": args.seam_window,
            "interpolationReport": str(interpolation_report_path),
            "interpolationVerdict": interpolation_report["verdict"],
            "budgetReport": str(budget_path),
            "selection": budget_report["delivery"],
            "intermediateFramesRetained": args.keep_frames,
        },
        "outputs": {
            "poster": {
                "path": str(final / "poster-alpha.png"),
                "alpha": True,
            },
            "desktop": {
                "path": str(desktop_output),
                "width": desktop_size[0],
                "height": desktop_size[1],
                "bytes": desktop_output.stat().st_size,
                "allFramesAreKeyframes": all_frames_are_keyframes(desktop_output),
                "probe": desktop_probe,
            },
            "mobile": {
                "path": str(mobile_output),
                "width": mobile_size[0],
                "height": mobile_size[1],
                "bytes": mobile_output.stat().st_size,
                "allFramesAreKeyframes": all_frames_are_keyframes(mobile_output),
                "probe": mobile_probe,
            },
        },
    }
    manifest_path = output / "compile.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    if not args.keep_frames:
        for directory in (raw_frames, cleaned_frames):
            if directory.is_dir():
                shutil.rmtree(directory)
        frames_root = output / "frames"
        if frames_root.is_dir() and not any(frames_root.iterdir()):
            frames_root.rmdir()
    print(f"编译完成：{manifest_path}", flush=True)
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="把绿幕动作母版插帧并编译为桌面与移动端全关键帧视频，供 WebGL 实时抠色"
    )
    result.add_argument("source", help="MiniMax 生成的均匀绿幕动作母版 MP4")
    result.add_argument("output_dir", help="新的构建目录")
    result.add_argument(
        "--budget-report",
        required=True,
        help="motion_budget.py 生成且已选择 chroma-video 的 JSON 报告",
    )
    mode = result.add_mutually_exclusive_group()
    mode.add_argument("--loop", action="store_true", help="按闭环首帧裁掉尾部停顿")
    mode.add_argument("--end-reference", help="单向转场目标尾帧，用于裁掉尾部停顿")
    result.add_argument("--fps", type=float, default=48)
    result.add_argument(
        "--desktop-width",
        type=int,
        default=1920,
        help="桌面资源像素宽度，通常为最大 CSS 宽度 × DPR；默认 1920",
    )
    result.add_argument(
        "--mobile-width",
        type=int,
        default=1280,
        help="移动端资源像素宽度，通常为最大 CSS 宽度 × DPR；默认 1280",
    )
    result.add_argument("--desktop-crf", type=int, default=12)
    result.add_argument("--mobile-crf", type=int, default=14)
    result.add_argument("--seam-window", type=int, default=40)
    result.add_argument("--duplicate-threshold", type=float, default=0.003)
    result.add_argument("--contact-columns", type=int, default=8)
    result.add_argument(
        "--allow-upscale",
        action="store_true",
        help="允许输出宽度超过母版；默认自动限制为母版宽度",
    )
    result.add_argument(
        "--keep-frames",
        action="store_true",
        help="保留插帧和清理帧用于调试；默认成功后删除中间 PNG",
    )
    result.add_argument("--force", action="store_true")
    return result


if __name__ == "__main__":
    try:
        raise SystemExit(compile_motion(parser().parse_args()))
    except (
        FileNotFoundError,
        FileExistsError,
        RuntimeError,
        ValueError,
        subprocess.CalledProcessError,
    ) as error:
        print(f"错误：{error}", file=sys.stderr)
        raise SystemExit(1) from error
