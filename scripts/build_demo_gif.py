"""把 record-demo.mjs 抓到的帧合成为演示 GIF。

用法（需要 Pillow）：
    python scripts/build_demo_gif.py --frames <帧目录> --out assets/demo.gif

要点：
- 帧间隔取录制时的真实时间差，并夹在 [1.8s, 5s]，避免某一屏一闪而过或长时间空等；
- 总时长不足 60 秒时把差额补到最后一帧，保证演示节奏适合讲解；
- 所有帧共用一张调色板，避免逐帧量化造成闪烁。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image

MIN_DELAY_MS = 1800
MAX_DELAY_MS = 5000
TARGET_TOTAL_MS = 60000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="合成演示 GIF")
    parser.add_argument("--frames", type=Path, required=True, help="帧目录（含 timeline.json）")
    parser.add_argument("--out", type=Path, required=True, help="输出 GIF 路径")
    parser.add_argument("--width", type=int, default=1000, help="输出宽度")
    parser.add_argument("--colors", type=int, default=200, help="调色板颜色数（逐帧自适应）")
    parser.add_argument(
        "--dither",
        choices=("none", "floyd"),
        default="none",
        help="渐变背景用 none 更干净（抖色会让大片纯色出现噪点），需要更平滑的渐变再开 floyd",
    )
    parser.add_argument(
        "--palette",
        choices=("global", "frame"),
        default="frame",
        help="global=所有帧共用调色板（不闪），frame=逐帧自适应（颜色最准）",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    meta = json.loads((args.frames / "timeline.json").read_text(encoding="utf-8"))
    frames = meta["frames"]
    if not frames:
        raise SystemExit("timeline.json 里没有帧")

    # 真实时间差 → 展示时长
    delays: list[int] = []
    for cur, nxt in zip(frames, frames[1:]):
        delays.append(max(MIN_DELAY_MS, min(MAX_DELAY_MS, nxt["at"] - cur["at"])))
    delays.append(2800)

    # 总时长不够 60 秒时逐帧分摊，不能全压到最后一帧（那样结尾会僵住十几秒）
    short = TARGET_TOTAL_MS - sum(delays)
    if short > 0:
        while short > 0:
            for index in range(len(delays)):
                if short <= 0:
                    break
                if delays[index] >= MAX_DELAY_MS:
                    continue
                step = min(600, MAX_DELAY_MS - delays[index], short)
                delays[index] += step
                short -= step

    images = []
    for item in frames:
        image = Image.open(args.frames / item["frame"]).convert("RGB")
        height = round(image.height * args.width / image.width)
        images.append(image.resize((args.width, height), Image.LANCZOS))

    # 用所有帧拼一张缩略图来生成统一调色板：
    # 只取单帧会出现「浅靛蓝按钮 / 橙色表头」这类颜色缺失，量化后变成灰块
    cols = 4
    rows = (len(images) + cols - 1) // cols
    thumb_w, thumb_h = 240, round(images[0].height * 240 / images[0].width)
    mosaic = Image.new("RGB", (cols * thumb_w, rows * thumb_h), "white")
    for index, image in enumerate(images):
        mosaic.paste(image.resize((thumb_w, thumb_h), Image.LANCZOS), ((index % cols) * thumb_w, (index // cols) * thumb_h))
    palette = mosaic.quantize(colors=args.colors, method=Image.MEDIANCUT)
    dither = Image.NONE if args.dither == "none" else Image.FLOYDSTEINBERG
    if args.palette == "frame":
        paletted = [image.quantize(colors=args.colors, method=Image.MEDIANCUT, dither=dither) for image in images]
    else:
        paletted = [image.quantize(palette=palette, dither=dither) for image in images]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # 注意：不要开 optimize（它写增量帧），配合 disposal=2 会在下一帧留下灰色残块；
    # 这里每帧都写整屏，体积换正确性。
    paletted[0].save(
        args.out,
        save_all=True,
        append_images=paletted[1:],
        duration=delays,
        loop=0,
        optimize=False,
        disposal=2,
    )

    size_mb = args.out.stat().st_size / 1024 / 1024
    print(f"帧数 {len(paletted)}，尺寸 {images[0].width}x{images[0].height}")
    print(f"总时长 {sum(delays) / 1000:.1f}s，文件 {size_mb:.2f}MB → {args.out}")
    for item, delay in zip(frames, delays):
        print(f"  {item['frame']}  {delay / 1000:.1f}s  {item['label']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
