"""Encode reciprocal still and moving-camera assets from Blender PNG passes."""
from PIL import Image
from pathlib import Path
import subprocess, sys
SRC=Path(__file__).resolve().parent
frames=SRC / 'build'
OUT=frames
def plate(src):
 im=Image.open(src).convert('RGBA')
 w,h=im.size
 # Keep soft contact shadows, fading only the far edges of the shadow-catching plane.
 ramp=Image.new('L',(w,1))
 ramp.putdata([round(255*max(0,min(1,x/(w*.039),(w-1-x)/(w*.037)))) for x in range(w)])
 from PIL import ImageChops
 im.putalpha(ImageChops.multiply(im.getchannel('A'),ramp.resize((w,h))))
 return im
if 'movie' in sys.argv:
 for i in range(19):
  im=plate(frames/('motion-%02d.png'%i));rgb=Image.new('RGB',im.size,'#F3F0E8');rgb.paste(im,mask=im.getchannel('A'));rgb.save(frames/('flat-%02d.png'%i))
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-framerate','24','-i',str(frames/'flat-%02d.png'),'-an','-c:v','libx264','-pix_fmt','yuv420p','-crf','17','-preset','medium','-movflags','+faststart',str(OUT/'enter.mp4')],check=True)
else:
 plate(frames/'hero.png').save(OUT/'studio.webp',quality=94,alpha_quality=95,method=6)
