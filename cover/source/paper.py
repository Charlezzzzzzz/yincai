"""Typeset two neutral teaching-journal textures for the curved Blender pages."""
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
INK = "#293548"
MUTED = "#677877"
RULE = "#b6bab0"
PAPER = "#f9f4e6"


def font(font_dir, size, serif=False):
    name = "NotoSerifSC-Bold.ttf" if serif else "NotoSansSC-Regular.ttf"
    return ImageFont.truetype(str(font_dir / name), size)


def field(draw, top, title, font_dir):
    draw.text((92, top), title, fill=INK, font=font(font_dir, 38))
    for offset in (100, 170):
        draw.line((94, top + offset, 920, top + offset), fill=RULE, width=2)


def print_pages(font_dir):
    layouts = (("备课手记", "学习目标", "教学活动"), ("教师批注", "课堂观察", "调整记录"))
    for side, (title, upper, lower) in enumerate(layouts):
        page = Image.new("RGB", (1024, 1220), PAPER)
        draw = ImageDraw.Draw(page)
        draw.text((90, 80), "因才   /   教研工作簿", fill=MUTED, font=font(font_dir, 31))
        draw.line((92, 140, 934, 140), fill=MUTED, width=3)
        draw.text((86, 188), title, fill=INK, font=font(font_dir, 96, True))
        field(draw, 420, upper, font_dir)
        field(draw, 790, lower, font_dir)
        page.save(HERE / f"page-{side}.png", optimize=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--font-dir", type=Path, required=True, help="含两款指定 Noto SC 字体的目录")
    print_pages(parser.parse_args().font_dir)
