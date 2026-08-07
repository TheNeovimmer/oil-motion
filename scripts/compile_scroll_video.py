#!/usr/bin/env python3
"""把 MiniMax 动作母版编译为可滚动拖动的全关键帧 MP4。

适合不需要透明背景、以一维时间轴顺序访问的大尺寸动画。脚本会切帧、裁掉可选的
尾部停顿、生成质检材料，并输出桌面与移动端两个无音轨版本。
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
PIPELINE = SCRIPT_DIR / "motion_pipeline.py"
CLEANUP = SCRIPT_DIR / "loop_cleanup.py"


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
    if not source.is_file():
        raise FileNotFoundError(f"找不到视频：{source}")
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

    raw_frames = output / "frames" / "raw"
    final_frames = output / "frames" / "final"
    qa = output / "qa"
    final = output / "final"
    qa.mkdir(parents=True, exist_ok=True)

    run(
        [
            sys.executable,
            str(PIPELINE),
            "extract",
            str(source),
            str(raw_frames),
            "--fps",
            str(args.fps),
            "--key",
            "none",
        ]
    )
    raw_count = len(image_frames(raw_frames))
    if raw_count < 3:
        raise RuntimeError("母版切帧后少于 3 帧")

    if args.loop or args.end_reference:
        cleanup_command = [
            sys.executable,
            str(CLEANUP),
            str(raw_frames),
            str(final_frames),
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
    else:
        final_frames.mkdir(parents=True, exist_ok=True)
        for frame in image_frames(raw_frames):
            shutil.copy2(frame, final_frames / frame.name)
        print("提示：未传 --loop 或 --end-reference，保留全部母版帧", flush=True)

    final_count = len(image_frames(final_frames))
    run(
        [
            sys.executable,
            str(PIPELINE),
            "analyze",
            str(final_frames),
            "--output",
            str(qa / "analysis.json"),
        ]
    )
    run(
        [
            sys.executable,
            str(PIPELINE),
            "contact",
            str(final_frames),
            "--output",
            str(qa / "contact-sheet.jpg"),
            "--columns",
            str(args.contact_columns),
        ]
    )

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
    desktop_output = final / "motion-scrub-desktop.mp4"
    mobile_output = final / "motion-scrub-mobile.mp4"
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
            "fps": args.fps,
            "rawFrameCount": raw_count,
            "finalFrameCount": final_count,
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
        },
        "outputs": {
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
    print(f"编译完成：{manifest_path}", flush=True)
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description="把 MiniMax 母版编译为桌面与移动端全关键帧滚动视频"
    )
    result.add_argument("source", help="MiniMax 生成的动作母版 MP4")
    result.add_argument("output_dir", help="新的构建目录")
    mode = result.add_mutually_exclusive_group()
    mode.add_argument("--loop", action="store_true", help="按闭环首帧裁掉尾部停顿")
    mode.add_argument("--end-reference", help="单向转场目标尾帧，用于裁掉尾部停顿")
    result.add_argument("--fps", type=float, default=24)
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
    result.add_argument("--desktop-crf", type=int, default=18)
    result.add_argument("--mobile-crf", type=int, default=19)
    result.add_argument("--seam-window", type=int, default=40)
    result.add_argument("--duplicate-threshold", type=float, default=0.003)
    result.add_argument("--contact-columns", type=int, default=8)
    result.add_argument(
        "--allow-upscale",
        action="store_true",
        help="允许输出宽度超过母版；默认自动限制为母版宽度",
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
