#!/usr/bin/env python3
"""使用 ZenMux 的图片模型（如 openai/gpt-image-2）生成并下载关键帧图片。"""

from __future__ import annotations

import argparse
import base64
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from oil_motion_config import require_api_key

API_ROOT = "https://zenmux.ai/api/v1"
DEFAULT_IMAGE_MODEL = "openai/gpt-image-2"


def generate_image(
    prompt: str,
    output_path: Path,
    model: str = DEFAULT_IMAGE_MODEL,
    size: str = "1024x1024",
    transparent: bool = True,
    force: bool = False,
) -> Path:
    if output_path.exists() and not force:
        raise FileExistsError(f"输出文件已存在：{output_path}；确认后使用 --force")

    api_key = require_api_key()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    enhanced_prompt = prompt.strip()
    if transparent and "transparent" not in enhanced_prompt.lower():
        enhanced_prompt = f"{enhanced_prompt}, clean transparent background, isolated subject, no background elements"

    payload: dict[str, Any] = {
        "model": model,
        "prompt": enhanced_prompt,
        "size": size,
        "n": 1,
    }

    req = urllib.request.Request(
        f"{API_ROOT}/images/generations",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "oil-motion/1.0",
        },
    )

    print(f"正在向 ZenMux 提交图片生成请求（模型：{model}）...", flush=True)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ZenMux Image API {exc.code}: {details}") from exc

    items = data.get("data", [])
    if not items:
        raise RuntimeError(f"图片生成接口未返回数据：{data}")

    first_item = items[0]
    if "b64_json" in first_item:
        image_bytes = base64.b64decode(first_item["b64_json"])
        output_path.write_bytes(image_bytes)
    elif "url" in first_item:
        image_url = first_item["url"]
        down_req = urllib.request.Request(
            image_url, headers={"User-Agent": "oil-motion/1.0"}
        )
        with urllib.request.urlopen(down_req, timeout=120) as down_resp:
            output_path.write_bytes(down_resp.read())
    else:
        raise RuntimeError(f"未知的图片返回格式：{first_item.keys()}")

    print(f"图片已保存：{output_path}（{output_path.stat().st_size} 字节）", flush=True)
    return output_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt", help="提示词文本")
    prompt_group.add_argument("--prompt-file", help="包含提示词的文件路径")
    parser.add_argument(
        "--output", required=True, help="保存图片的输出路径（PNG）"
    )
    parser.add_argument(
        "--model", default=DEFAULT_IMAGE_MODEL, help="图片模型名称"
    )
    parser.add_argument(
        "--size", default="1024x1024", help="分辨率尺寸（如 1024x1024）"
    )
    parser.add_argument(
        "--no-transparent",
        dest="transparent",
        action="store_false",
        help="不强制要求透明背景",
    )
    parser.set_defaults(transparent=True)
    parser.add_argument(
        "--force", action="store_true", help="覆盖已存在的输出文件"
    )
    args = parser.parse_args()

    prompt = args.prompt
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8").strip()

    output_path = Path(args.output).expanduser().resolve()
    generate_image(
        prompt=prompt,
        output_path=output_path,
        model=args.model,
        size=args.size,
        transparent=args.transparent,
        force=args.force,
    )


if __name__ == "__main__":
    main()
