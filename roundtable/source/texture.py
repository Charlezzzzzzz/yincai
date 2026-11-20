"""Deterministic original surface samples. Supply the project Noto font directory."""
from pathlib import Path
from sys import argv
import numpy as np
from PIL import Image,ImageDraw,ImageFont
out=Path(__file__).resolve().parent
rng=np.random.default_rng(107)
h,w=768,2048
y,x=np.mgrid[0:h,0:w].astype(float)
x/=w;y/=h
def field(nx,ny):
    small=Image.fromarray((rng.random((ny,nx))*255).astype('uint8'))
    return np.asarray(small.resize((w,h),Image.Resampling.BICUBIC),dtype=float)/255-.5
warp=y+.009*np.sin(7*x+6*y)+.004*field(5,12)+.002*np.sin(21*x+9*y)
growth=warp*118+1.25*np.sin(7.2*x+1.4*np.sin(17*y))+.17*field(9,32)
rings=(.5+.5*np.cos(2*np.pi*growth))**6
streak=field(10,340)
vein=field(35,420)
tone=20*field(4,16)+16*streak+7*vein-16*rings+1.8*rng.normal(size=(h,w))
rgb=np.array([133,98,72])[None,None,:]+tone[:,:,None]*np.array([1,.88,.69])
Image.fromarray(np.uint8(np.clip(rgb,0,255))).save(out/'rift-walnut.jpg',quality=91,subsampling=0)
fonts=Path(argv[1])
def font(name,size):return ImageFont.truetype(str(fonts/name),size)
paper=Image.new('RGB',(848,1120),'#F3F0E8');d=ImageDraw.Draw(paper)
navy='#26354A'; muted='#69766B'
sans=lambda n:font('NotoSansSC-Regular.ttf',n)
song=lambda n:font('NotoSerifSC-Bold.ttf',n)
d.text((82,82),'因才   /   教研工作稿',font=sans(34),fill=muted)
d.line([(82,180),(765,180)],fill='#BFC3B6',width=3)
d.text((72,224),'教案批注',font=song(104),fill=navy)
d.text((82,421),'核查退回   /   同段修订',font=sans(41),fill=navy)
lines=['请先圈出等号两边的每一项。','为什么不含分母的项也要同乘 6？','把你的解代回原式检验。']
for i,s in enumerate(lines):d.text((82,587+96*i),s,font=sans(30),fill=navy)
d.line([(82,958),(765,958)],fill='#BFC3B6',width=3)
d.text((82,994),'教师批阅',font=sans(27),fill=muted)
paper.save(out/'review-page.png')
# Draft and reviewed folio are distinct pages. The answer leak is labelled.
draft=Image.new('RGB',(848,1120),'#F3F0E8');d=ImageDraw.Draw(draft)
d.text((82,82),'因才   /   教研工作稿',font=sans(34),fill=muted)
d.line([(82,180),(765,180)],fill='#BFC3B6',width=3)
d.text((72,224),'教案初稿',font=song(103),fill=navy)
d.text((82,421),'第 12 题   /   去分母',font=sans(41),fill=navy)
d.text((82,598),'(x−1)/2 − (x+2)/3 = 1',font=sans(42),fill=navy)
d.text((82,701),'初稿直接给出答案 13。',font=sans(31),fill=navy)
d.line([(77,729),(470,727)],fill='#94695E',width=4)
d.text((82,825),'演示反例：这句话需要退回。',font=sans(31),fill='#874F45')
d.line([(82,958),(765,958)],fill='#BFC3B6',width=3)
d.text((82,994),'制作人初稿',font=sans(27),fill=muted)
draft.save(out/'draft-page.png')
