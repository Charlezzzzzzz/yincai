"""Blender 5.2 background renderer for the editable local cover scene and camera path."""
import math,sys
from pathlib import Path
import bpy
from mathutils import Vector
from math import sin,cos,pi
SRC=Path(__file__).resolve().parent
ROOT=SRC.parents[1]
OUT=SRC / 'build'
scene_path = ROOT / 'model-source' / 'build' / 'cast.blend'
if not scene_path.is_file():
 raise FileNotFoundError("请先按 model-source/README.md 运行 create_cast.py -- --scene-only")
OUT.mkdir(exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene
def mat(name,color,rough=.75):
 m=bpy.data.materials.new(name);m.diffuse_color=(*color,1);m.use_nodes=True
 b=m.node_tree.nodes.get('Principled BSDF');b.inputs['Base Color'].default_value=(*color,1);b.inputs['Roughness'].default_value=rough
 return m
def link(ob,n,m):
 ob.name=n;ob.data.materials.append(m);return ob
def block(n,loc,dim,m,r=.04):
 bpy.ops.mesh.primitive_cube_add(size=1,location=loc);ob=link(bpy.context.object,n,m);ob.dimensions=dim
 bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
 if r:
  bevel=ob.modifiers.new('包边','BEVEL');bevel.width=r;bevel.segments=5
  ob.modifiers.new('饰面法线','WEIGHTED_NORMAL')
 return ob
def rounded_slab(n,w,h,z,thick,r,m,x=0,y=0):
 points=[]
 for cx,cy,start in ((w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),(-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)):
  for j in range(13):
   t=math.radians(start+90*j/12);points.append((cx+r*cos(t),cy+r*sin(t)))
 total=len(points);vs=[(a+x,b+y,z+dz) for dz in [0,thick] for a,b in points]
 fs=[tuple(reversed(range(total))),tuple(range(total,2*total))]+[(i,(i+1)%total,(i+1)%total+total,i+total) for i in range(total)]
 mesh=bpy.data.meshes.new(n);mesh.from_pydata(vs,[],fs);mesh.update();ob=bpy.data.objects.new(n,mesh);s.collection.objects.link(ob);link(ob,n,m)
 bevel=ob.modifiers.new('薄书角','BEVEL');bevel.width=min(.014,thick*.33);bevel.segments=3;ob.modifiers.new('纸边','WEIGHTED_NORMAL')
 return ob
def curve(n,points,m,r):
 c=bpy.data.curves.new(n,'CURVE');c.dimensions='3D';c.bevel_depth=r;c.bevel_resolution=3;c.resolution_u=8
 q=c.splines.new('BEZIER');q.bezier_points.add(len(points)-1)
 for v,p in zip(q.bezier_points,points):v.co=p;v.handle_left_type=v.handle_right_type='AUTO'
 ob=bpy.data.objects.new(n,c);s.collection.objects.link(ob);link(ob,n,m);return ob
def aim(o,p):o.rotation_euler=(Vector(p)-o.location).to_track_quat('-Z','Y').to_euler()
def light(n,xyz,power,size,color):
 bpy.ops.object.light_add(type='AREA',location=xyz);ob=bpy.context.object;ob.name=n;ob.data.energy=power;ob.data.shape='DISK';ob.data.size=size;ob.data.color=color;aim(ob,(0,0,.45))
def printmat(side):
 m=mat('备课手记印页'+str(side),(.95,.93,.89));img=bpy.data.images.load(str(SRC/('page-%d.png'%side)));img.pack()
 tex=m.node_tree.nodes.new('ShaderNodeTexImage');tex.image=img;m.node_tree.links.new(tex.outputs['Color'],m.node_tree.nodes.get('Principled BSDF').inputs['Base Color']);return m
paper=mat('米色书口',(.83,.79,.70));paperedge=mat('页叠阴影',(.69,.66,.58))
ink=mat('藏青书布',(.033,.056,.089),.83); green=mat('灰绿布面',(.20,.31,.31),.81);cloth=mat('雾灰皮革',(.49,.55,.50))
metal=mat('乌青金属',(.13,.16,.17),.36);wood=mat('原木笔尖',(.58,.45,.32));stone=mat('奶白背景',(.87,.86,.83))
# Single low, cloth-covered folio under the working group.
rounded_slab('下封板',8.5,4.8,.04,.13,.32,ink)
rounded_slab('整本教研记录的纸芯',8.37,4.68,.165,.22,.28,paper)
for k in (0,1,2):rounded_slab('可辨书口'+str(k),8.381,4.69,.199+k*.054,.010,.28,paperedge)
rounded_slab('上封板',8.50,4.8,.386,.102,.32,ink)
rounded_slab('封面压凹布纹',8.35,4.64,.482,.022,.26,green)
z=.504
# Small, open workbook; the two printed surfaces share the actual binding.
book_y=-.81
rounded_slab('练习册双页封套',4.04,2.22,z+.005,.06,.065,cloth,0,book_y)
def leaf(side):
 sign= -1 if side==0 else 1
 matp=printmat(side)
 n=48;k=6;vs=[];uv=[]
 for j in range(k+1):
  for i in range(n+1):
   t=i/n;y0=book_y-1.04+2.08*j/k;h=.134+.135*sin(pi*t)**.8+.027*t
   vs.append((sign*(.009+1.955*t),y0,z+h))
   uv.append((1-t if side==0 else t,j/k))
 fs=[]
 for j in range(k):
  for i in range(n):
   a=j*(n+1)+i
   face=(a,a+1,a+n+2,a+n+1)
   fs.append(tuple(reversed(face)) if side==0 else face)
 mesh=bpy.data.meshes.new('曲面页');mesh.from_pydata(vs,[],fs);mesh.update();ob=bpy.data.objects.new('教案左页' if side==0 else '教案右页',mesh);s.collection.objects.link(ob);ob.data.materials.append(matp);ob.data.materials.append(paper)
 uv_layer=mesh.uv_layers.new()
 for lp in mesh.loops:uv_layer.data[lp.index].uv=uv[lp.vertex_index]
 for p in mesh.polygons:p.use_smooth=True
 mod=ob.modifiers.new('真实纸厚','SOLIDIFY');mod.thickness=.073;mod.material_offset=1;mod.material_offset_rim=1
for side in (0,1):leaf(side)
# Fabric bookmark falls over the near book edge, under the large folio lip.
block('织物书签',(.19,book_y-1.035,z+.092),(.115,.59,.012),green,.004)
# Two manuscript revision stickers repeated from the same cream/navy product palette.
for n,x,y in (('页签一',1.96,-.94),('页签二',1.96,-1.29)):
 block(n,(x,y,z+.097),(.23,.25,.025),cloth if n.endswith('一') else ink,.014)
# Place the intact figure sculpts from the source including their original apparel and attached props;
# remove the gallery bases for this composition. Every shoe lies on the folio deck.
ids=['analyst','expert','designer','producer','checker','assistant']
with bpy.data.libraries.load(str(scene_path),link=False) as (src,dst):
 dst.collections=list(ids)
positions=[(-3.15,-.67,.79,19),(-2.51,1.17,.82,5),(-.88,1.40,.82,-5),(.83,1.38,.83,-9),(2.28,1.34,.84,-20),(3.48,-1.14,.76,-30)]
for role,(x,y,scale,turn) in zip(ids,positions):
 co=next(c for c in dst.collections if c.name==role)
 s.collection.children.link(co);root=next(o for o in co.objects if o.parent is None and o.get('role_id')==role)
 for o in co.objects:
  if o.name.startswith('底座'):o.hide_render=True
 root.rotation_euler=(0,0,math.radians(turn));root.location=(x,y,z-.124*scale);root.scale=(scale,)*3
# Graphite pencil beside the open journal.
def cyl_between(n,a,b,rad,m):
 a,b=Vector(a),Vector(b);d=b-a
 bpy.ops.mesh.primitive_cylinder_add(vertices=12,radius=rad,depth=d.length,location=(a+b)/2);ob=link(bpy.context.object,n,m);ob.rotation_euler=d.to_track_quat('Z','Y').to_euler();return ob
a=Vector((-2.48,-1.66,z+.055));b=Vector((-2.29,-.46,z+.055));direction=(b-a).normalized()
cyl_between('石墨色铅笔',a,b,.046,ink)
cyl_between('笔帽',a-direction*.09,a,.049,metal)
bpy.ops.mesh.primitive_cone_add(vertices=12,radius1=.046,radius2=.003,depth=.14,location=b+direction*.07);tip=link(bpy.context.object,'已削笔尖',wood);tip.rotation_euler=direction.to_track_quat('Z','Y').to_euler()
cyl_between('铅芯',b+direction*.126,b+direction*.144,.008,ink)
bpy.ops.mesh.primitive_plane_add(size=200,location=(0,0,0));plane=link(bpy.context.object,'摄影棚地面',stone);plane.is_shadow_catcher=True
s.world=bpy.data.worlds.new('软光棚');s.world.use_nodes=True;bg=s.world.node_tree.nodes.get('Background');bg.inputs[0].default_value=(.88,.85,.80,1);bg.inputs[1].default_value=.48
light('向左漫射光',(-4,-6,9),1450,6.5,(1,.95,.89));light('纸页填光',(4,-3.5,6),570,6,(.87,.94,1));light('身后勾边',(1,4,8),950,4,(1,.92,.82))
bpy.ops.object.camera_add();cam=bpy.context.object;cam.name='工作台进入镜头';s.camera=cam;cam.data.type='ORTHO'
s.render.engine='CYCLES';s.cycles.samples=16;s.cycles.use_denoising=True;s.cycles.max_bounces=4;s.render.film_transparent=True
s.render.threads_mode='FIXED';s.render.threads=6
s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast'
s.render.use_stamp_filename = False
s.render.resolution_x=1344;s.render.resolution_y=944;s.render.resolution_percentage=100;s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA'
def shot(t):
 ease=t*t*(3-2*t)
 cx,cy,cz=(2.9-1.4*ease,-11.3+.75*ease,7.2+3.9*ease)
 cam.location=(cx,cy,cz);aim(cam,(.04+.10*ease,-.06-.69*ease,.87-.15*ease));cam.data.ortho_scale=10.25-5.95*ease
shot(0)
def audit_deck():
 from bpy_extras.object_utils import world_to_camera_view
 bpy.context.view_layer.update()
 def z_values(ob):
  evaluated=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());geom=evaluated.to_mesh()
  try:return [(evaluated.matrix_world@v.co).z for v in geom.vertices]
  finally:evaluated.to_mesh_clear()
 deck=max(z_values(bpy.data.objects['封面压凹布纹']))
 checks=[]
 for name in ids:
  co=bpy.data.collections[name];soles=[ob for ob in co.objects if ob.name.startswith('贴地鞋底')]
  assert len(soles)==2
  errors=[abs(min(z_values(sole))-deck) for sole in soles]
  assert max(errors)<.00002,(name,errors)
  face=next(ob for ob in co.objects if ob.name.startswith('手塑面部'))
  midpoint=sum((face.matrix_world@Vector(v) for v in face.bound_box),Vector())/8
  pos=world_to_camera_view(s,cam,midpoint)
  assert 0.04<pos.x<.96 and .04<pos.y<.96
  checks.append((name,[round(x,8) for x in errors],round(pos.x,3),round(pos.y,3)))
 print('COVER CONTACTS / FACE CENTRES',checks,flush=True)
audit_deck()
if '--' in sys.argv and 'audit' in sys.argv[sys.argv.index('--')+1:]:
 pass
elif '--' in sys.argv and 'motion' in sys.argv[sys.argv.index('--')+1:]:
 s.cycles.samples=8;s.render.resolution_x=982;s.render.resolution_y=690
 for i in range(19):
  shot(i/18);s.render.filepath=str(OUT/('motion-%02d.png'%i));bpy.ops.render.render(write_still=True)
else:
 s.render.filepath=str(OUT/'hero.png');bpy.ops.render.render(write_still=True)
