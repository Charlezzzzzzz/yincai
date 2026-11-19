"""按发顶、颏底等高排版六位智能体校样；仅使用已经生成的图片。"""

import argparse
from dataclasses import dataclass
from functools import lru_cache
import json
import math
from functools import partial
from pathlib import Path
from statistics import median

from PIL import Image, ImageChops, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "models"
PROOFS = MODELS / "校样"
BOARD = "六位智能体_原头像与两版对照.png"
ASSISTANT = "06_教师助理男生_转面校样.png"
PAPER, WELL, INK, MUTED, RULE = "#F3F0E8", "#E9E7DF", "#14213D", "#4F5B6A", "#C6C9C3"

# Original avatar coordinates were read on the supplied 256-pixel images.
# Endpoints measure the hair/accessory crown through the chin or elderly beard.
ROLES = [
    ("analyst", "学情分析师", "圆镜、连帽衫与统计牌", 18, 190),
    ("expert", "学科专家", "灰发、方镜与绿书", 18, 192),
    ("designer", "教学设计师", "栗色卷发与草图卡", 8, 199),
    ("producer", "多模态制作人", "盘发、紫色发束与耳机", 4, 196),
    ("checker", "核查员", "红发夹、低马尾与放大镜", 14, 185),
    ("assistant", "教师助理", "黑色翘发、工作证与对话牌", 10, 181),
]


@lru_cache(maxsize=20)
def font_from_dir(directory, size, serif=False):
    name = "NotoSerifSC-Bold.ttf" if serif else "NotoSansSC-Regular.ttf"
    return ImageFont.truetype(str(directory / name), size)


@dataclass
class Portrait:
    image: Image.Image
    crop: tuple
    center: float
    crown: float
    chin: float
    label: str

    @property
    def height(self):
        return self.chin - self.crown


def face_end(image, bounds, role):
    """Estimate an unmarked neck junction from face colour and narrowing silhouette."""
    left, top, right, bottom = bounds
    small = image.crop(bounds).resize((192, 256), Image.Resampling.BOX)
    pixels = small.load()
    widths, skin = [], []
    def is_skin(pixel):
        red, green, blue, alpha = pixel
        return alpha >= 64 and red > 95 and red-green >= 8 and green-blue >= 3 and red-blue > 20

    for y in range(256):
        occupied = [x for x in range(192) if pixels[x, y][3] >= 64]
        widths.append(occupied[-1] - occupied[0] + 1 if occupied else 0)
        # The centre of the upper face stays with the head for a three-quarter view.
        skin.append(sum(is_skin(pixels[x, y]) for x in range(75, 120)) / 45)
    peak = max(widths[39:120])
    neck = min(range(86, 166), key=lambda i: median(widths[i-2:i+3]))
    transitions = []
    for i in range(83, 174):
        before = sum(skin[i-7:i]) / 7
        after = sum(skin[i:i+7]) / 7
        if before > .62 and after < .52 and widths[i] < peak * .92:
            transitions.append((before-after - abs(i-neck)*.004, i))
    if role == "expert":
        # The white beard changes colour above the real chin.
        estimate = neck
    elif transitions:
        estimate = max(transitions)[1]
    else:
        estimate = neck
    return top + estimate / 256 * (bottom - top)


def read_model(path, role, marks, full=False):
    with Image.open(path) as stream:
        image = stream.convert("RGBA")
    alpha = image.getchannel("A")
    if alpha.getextrema()[0] == 255:
        raise ValueError(f"{path.name} 缺少透明背景，无法按轮廓取景。")
    mask = alpha.point(lambda a: 255 if a >= 32 else 0)
    bounds = mask.getbbox()
    if not bounds:
        raise ValueError(f"{path.name} 的透明画布为空。")
    l, t, r, b = bounds
    if min(l, t, image.width-r, image.height-b) <= 0:
        raise ValueError(f"{path.name} 的有效轮廓接触图边，请先核对全身相机。")
    points = marks.get(path.stem, {})
    crown = points.get("crown_y", t)
    chin = points.get("chin_y")
    if chin is None:
        chin = face_end(image, bounds, role)
    if not t - 8 <= crown < chin < b or not .24 < (chin-crown)/(b-t) < .76:
        raise ValueError(f"{path.name} 的头部坐标异常，请复核发顶与颏底。")
    # If a renderer supplied the lowest edge of a prop, give it a margin. A
    # pose without projected landmarks gets a more conservative lower bound.
    prop_bottom = points.get("prop_bottom_y")
    head = chin-crown
    if prop_bottom is not None and not t <= prop_bottom <= b+8:
        raise ValueError(f"{path.name} 的道具投影超出全身轮廓。")
    safe_end = prop_bottom+.08*head if prop_bottom is not None else t+.82*(b-t)
    crop_end = b if full else min(b, math.ceil(max(safe_end, chin+.50*head)))
    x0, _, x1, _ = mask.crop((l, t, r, math.ceil(chin))).getbbox()
    center = l + (x0 + x1) / 2
    pad = 4
    crop = (max(0,l-pad), max(0,t-pad), min(image.width,r+pad), min(image.height,crop_end+pad))
    return Portrait(image, crop, center, crown, chin, path.stem)


def read_avatar(role):
    key, _, _, crown, chin = role
    with Image.open(ROOT / "avatars" / (key+".webp")) as stream:
        image = stream.convert("RGBA")
    if image.size != (256, 256):
        raise ValueError(f"{key} 原头像尺寸变化，请重新量取发顶与颏底。")
    return Portrait(image, (0, 0, *image.size), 128, crown, chin, key+"-ref")


def framing(views, width, target):
    # One forehead/eye-level scale across all panels. Allow asymmetric hair
    # and props a wider margin without shrinking a single role independently.
    side = max(max(p.center-p.crop[0], p.crop[2]-p.center)/p.height for p in views)
    head = min(target, math.floor((width/2-18)/side))
    above = max((p.crown-p.crop[1])/p.height for p in views)
    below = max((p.crop[3]-p.crown)/p.height for p in views)
    crown_y = 16 + math.ceil(above*head)
    return head, crown_y, crown_y + math.ceil(below*head) + 18


def put_portrait(board, view, left, top, width, geometry):
    head, anchor, height = geometry
    scale = head/view.height
    x0, y0, x1, y1 = view.crop
    dest = (round(left+width/2-(view.center-x0)*scale), round(top+anchor-(view.crown-y0)*scale))
    if not view.label.endswith("-ref"):
        # The cropped torso meets the lower edge of the photographic field.
        # Every measured head and prop fits before this optional extension.
        y1 = max(y1, min(view.image.height, y0+math.floor((top+height-dest[1])/scale)))
    size = (round((x1-x0)*scale), round((y1-y0)*scale))
    if dest[0] < left or dest[1] < top or dest[0]+size[0] > left+width or dest[1]+size[1] > top+height:
        raise ValueError(f"{view.label} 超出展示区域。")
    new_head = view.height * size[1] / (y1-y0)
    if abs(new_head-head) > 1:
        raise ValueError(f"{view.label} 的输出头高未对齐。")
    raster = view.image.crop(view.crop).resize(size, Image.Resampling.LANCZOS)
    board.paste(raster, dest, raster)


def title(draw, width, name, note, font):
    draw.text((58, 36), name, font=font(51, True), fill=INK)
    draw.text((60, 112), note, font=font(23), fill=MUTED)
    draw.line((58, 168, width-58, 168), fill=INK, width=2)


def six_board(rows, font):
    col, gap, group_gap, left_margin = 412, 14, 62, 58
    group = col*3 + gap*2
    width = left_margin*2 + group*2 + group_gap
    geometry = framing([v for group_views in rows for v in group_views], col, 225)
    tile_h = geometry[2]
    group_h = tile_h + 139
    height = 197 + group_h*3 + 28
    board = Image.new("RGB", (width, height), PAPER)
    draw = ImageDraw.Draw(board)
    title(draw, width, "因才   六位智能体角色对照", "原头像保留原有视角。两版模型使用正面镜头，三列按各角色发顶至颏底等高排版。", font)
    for i, views in enumerate(rows):
        key, name, features, _, _ = ROLES[i]
        x = left_margin + (i%2)*(group+group_gap)
        y = 197 + (i//2)*group_h
        draw.text((x, y), f"{i+1:02}  {name}", font=font(37, True), fill=INK)
        draw.text((x+group, y+17), features, anchor="ra", font=font(21), fill=MUTED)
        for j, (p, label) in enumerate(zip(views, ("原头像", "v7 模型", "v7.1 模型"))):
            xx = x + j*(col+gap)
            draw.text((xx, y+61), label, font=font(22), fill=MUTED)
            top = y + 99
            draw.rectangle((xx,top,xx+col-1,top+tile_h-1), fill=WELL)
            put_portrait(board,p,xx,top,col,geometry)
        draw.line((x, y+group_h-17, x+group, y+group_h-17), fill=RULE, width=2)
    return board


def assistant_board(views, font):
    col, gap, margin = 514, 18, 58
    width = 2*margin + 4*col + 3*gap
    geometry = framing(views[:3], col, 296)
    height = 273 + geometry[2] + 42
    board = Image.new("RGB", (width,height), PAPER)
    draw = ImageDraw.Draw(board)
    title(draw, width, "因才   06 教师助理 · 男生", "黑色翘发、蓝紫色制服、工作证与对话牌", font)
    for i, (p,label) in enumerate(zip(views,("原头像","新版正面","新版四分之三侧面","新版全身"))):
        x = margin+i*(col+gap)
        draw.text((x, 200), label, font=font(31, True), fill=INK)
        draw.rectangle((x,273,x+col-1,273+geometry[2]-1), fill=WELL)
        if i < 3:
            put_portrait(board,p,x,273,col,geometry)
        else:
            figure = p.image.crop(p.crop)
            figure.thumbnail((col-30, geometry[2]-30), Image.Resampling.LANCZOS)
            dest = (x+(col-figure.width)//2, 273+(geometry[2]-figure.height)//2)
            board.paste(figure, dest, figure)
    return board


def finish(image, path, check):
    if not check:
        image.save(path, format="PNG", optimize=True)
    with Image.open(path) as on_disk:
        if (on_disk.size != image.size or on_disk.mode != "RGB"
                or ImageChops.difference(on_disk.convert("RGB"), image).getbbox() is not None):
            raise ValueError(f"{path} 与当前源图或排版不同。")
    print(f"{path.name}    {image.width} × {image.height} px，PNG 像素回读一致。")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="重建于内存并校验两份已有 PNG，不写文件。")
    parser.add_argument("--font-dir", type=Path, required=True, help="含两款指定 Noto SC 字体的目录")
    args = parser.parse_args()
    font = partial(font_from_dir, args.font_dir)
    output = MODELS if args.check else Path(__file__).resolve().parent / "build" / "models"
    if not args.check:
        output.mkdir(parents=True, exist_ok=True)
    sidecar = PROOFS / "landmarks.json"
    marks = json.loads(sidecar.read_text(encoding="utf-8")) if sidecar.exists() else {}
    rows = []
    for role in ROLES:
        key = role[0]
        pair = [read_model(PROOFS/f"{key}-{angle}.png",key,marks) for angle in ("old", "front")]
        rows.append([read_avatar(role), *pair])
    detail = [rows[-1][0], rows[-1][2], read_model(PROOFS/"assistant-three.png","assistant",marks),
              read_model(PROOFS/"assistant-front.png","assistant",marks,full=True)]
    for pair in rows:
        print("  ".join(f"{v.label} {v.crown:.1f}–{v.chin:.1f}px" for v in pair))
    finish(six_board(rows, font), output/BOARD, args.check)
    finish(assistant_board(detail, font), output/ASSISTANT, args.check)


if __name__ == "__main__":
    main()
