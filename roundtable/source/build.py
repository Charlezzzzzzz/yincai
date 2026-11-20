"""Rebuild all six seats and the authored desk from the checked-in sources."""
from pathlib import Path
import json, math, struct, sys
import bpy, bmesh
from mathutils import Vector
from math import sin,cos,pi

SRC=Path(__file__).resolve().parent
OUT=Path(sys.argv[sys.argv.index('--')+1]).resolve() if '--' in sys.argv else SRC.parent
OUT.mkdir(parents=True, exist_ok=True)
MODEL=SRC.parents[1]/'models'
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene
def color(h):
    def linear(c): return c/12.92 if c<=.04045 else ((c+.055)/1.055)**2.4
    return tuple(linear(int(h[i:i+2],16)/255) for i in (0,2,4))+(1.,)
def material(name,rgb,rough=.65,metal=0,image=None):
    m=bpy.data.materials.new(name);m.diffuse_color=color(rgb);m.use_nodes=True
    bs=m.node_tree.nodes.get('Principled BSDF')
    for k,v in [('Base Color',color(rgb)),('Roughness',rough),('Metallic',metal)]:bs.inputs[k].default_value=v
    if image:
        im=bpy.data.images.load(str(SRC/image),check_existing=True);im.pack()
        t=m.node_tree.nodes.new('ShaderNodeTexImage');t.image=im
        m.node_tree.links.new(t.outputs['Color'],bs.inputs['Base Color'])
    return m
oak=material('Rift walnut / oiled satin','A58462',.48,image='rift-walnut.jpg')
linoleum=material('Sage writing linoleum','445951',.83)
blue=material('Blue-black powder coat','273544',.49,.18)
pewter=material('Bead-blasted graphite nickel','818783',.34,.69)
cover=material('Indigo bookcloth','253448',.80)
sheet=material('Warm paper','F4EFE3',.83)
printmat=material('Teaching review sheet','F3F0E8',.85,image='review-page.png')
floor_mat=material('Ivory studio floor','EEEAE0',.88)
lead=material('Graphite pencil','41484A',.63)
def mesh(name,points,faces,mat):
    m=bpy.data.meshes.new(name);m.from_pydata(points,[],faces);m.update()
    o=bpy.data.objects.new(name,m);s.collection.objects.link(o);m.materials.append(mat)
    return o
def soften(o,width):
    if width:
        b=o.modifiers.new('Machined soft edge','BEVEL');b.width=width;b.segments=4
        o.modifiers.new('Surface normals','WEIGHTED_NORMAL')
    return o
def box(name,loc,dims,mat,r=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=loc);o=bpy.context.object;o.name=name;o.dimensions=dims
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True);o.data.materials.append(mat)
    return soften(o,r)
count=192
def ellipse(a,b,i):
    t=2*pi*i/count
    power=2/2.48
    return (a*math.copysign(abs(cos(t))**power,cos(t)),b*math.copysign(abs(sin(t))**power,sin(t)))
def layered(name,levels,mat):
    verts=[(*ellipse(a,b,i),z) for a,b,z in levels for i in range(count)]
    faces=[tuple(reversed(range(count)))]
    for j in range(len(levels)-1):
        for i in range(count):faces.append((j*count+i,j*count+(i+1)%count,(j+1)*count+(i+1)%count,(j+1)*count+i))
    faces.append(tuple(range((len(levels)-1)*count,len(levels)*count)))
    o=mesh(name,verts,faces,mat)
    uv=o.data.uv_layers.new(name='Veneer layout')
    for p in o.data.polygons:
        zside=abs(p.normal.z)<.68
        for li in p.loop_indices:
            x,y,z=o.data.vertices[o.data.loops[li].vertex_index].co
            uv.data[li].uv=((x+2.28)/4.56, (z-.60)*4+.27 if zside else (y+1.06)/2.12)
        if zside:p.use_smooth=True
    return o

# Unit: metres. The liner beds in a genuine 3 mm recess in the timber.
A,B,Z=2.28,.93,.652
MAT_A,MAT_B=1.18,.56
BED=Z-.003
UNDER=Z-.084
TOP='table-top-walnut'
wood=layered(TOP,[(A-.064,B-.064,UNDER),(A-.014,B-.014,Z-.042),(A-.002,B-.002,Z-.032),(A,B,Z-.022),(A,B,Z-.007),(A-.005,B-.005,Z),(MAT_A,MAT_B,Z),(MAT_A,MAT_B,BED)],oak)
pad=layered('writing-inlay-sage',[(MAT_A-.0014,MAT_B-.0014,BED),(MAT_A-.0014,MAT_B-.0014,Z-.0005)],linoleum)
rail=box('apron-longitudinal',(0,0,UNDER-.036),(3.43,.151,.072),blue,.014)
def trestle(name,offset):
    # Arch extrusion. The spring line, abutments and rail share a common profile.
    w,inn,spring,top=.401,.221,.170,UNDER-.072
    pts=[(-w,0),(-w,top-.034),(-w+.034,top),(w-.034,top),(w,top-.034),(w,0),(inn,0),(inn,spring)]
    for i in range(1,49):
        t=pi*i/48;pts.append((inn*cos(t),spring+inn*sin(t)))
    pts.append((-inn,0))
    n=len(pts);v=[(offset+x,y,z) for y in (-.327,.327) for x,z in pts]
    faces=[tuple(reversed(range(n))),tuple(range(n,n*2))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    o=mesh(name,v,faces,blue)
    # Recalculate winding for a consistent closed manifold before beveling.
    bm=bmesh.new();bm.from_mesh(o.data);bmesh.ops.recalc_face_normals(bm,faces=bm.faces[:]);bm.to_mesh(o.data);bm.free()
    return soften(o,.018)
arches=[trestle('trestle-'+side,x) for side,x in [('left',-1.22),('right',1.22)]]
for side,x in [('left',-1.22),('right',1.22)]:
    # Mounting shoes sit on each arch and spread the upper load across the depth.
    for suffix,y in [('near',-.199),('far',.199)]:
        box('mount-'+side+'-'+suffix,(x,y,UNDER-.036),(.50,.147,.072),blue,.009)
    for suffix,dx in [('L',-.302),('R',.302)]:
        bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.012,depth=.004,location=(x+dx,-.327,.381),rotation=(pi/2,0,0))
        pin=bpy.context.object;pin.name='fastener-'+side+'-'+suffix;pin.data.materials.append(pewter)
        soften(pin,.0008)
furniture=list(s.objects)
def export(path,objects):
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:o.select_set(True)
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True,export_extras=False)

# Small teacher review folder. All layers share the same origin and binding.
draftmat=material('Rejected teaching draft','F3F0E8',.85,image='draft-page.png')
def printed_leaf(name,x,y,z,w,h,mat):
    m=mesh(name,[(x-w/2,y-h/2,z),(x+w/2,y-h/2,z),(x+w/2,y+h/2,z),(x-w/2,y+h/2,z)],[(0,1,2,3)],mat)
    uv=m.data.uv_layers.new()
    for i,p in enumerate([(0,0),(1,0),(1,1),(0,1)]):uv.data[i].uv=p
    return m
pad_z=Z-.0005
fx,fy=0.,-.02
book=box('folio-binding',(fx,fy,pad_z+.008),(1.076,.664,.016),cover,.010)
for sign,mat,name in [(-1,draftmat,'draft'),(1,printmat,'revision')]:
    x=fx+sign*.254
    box('folio-stack-'+name,(x,fy,pad_z+.021),(.495,.612,.010),sheet,.004)
    printed_leaf('folio-proof-'+name,x,fy,pad_z+.0261,.493,.608,mat)
# Hexagonal dark-lacquer pencil and actual conical wood/graphite point.
def pencil_piece(name,x,length,r1,r2,mat):
    bpy.ops.mesh.primitive_cone_add(vertices=6,radius1=r1,radius2=r2,depth=length,location=(x,-.407,pad_z+.0127),rotation=(0,pi/2,0))
    part=bpy.context.object;part.name=name;part.data.materials.append(mat);return part
pencil=pencil_piece('pencil-body',-.01,.34,.0127,.0127,blue)
pencil_piece('pencil-exposed-wood',.174,.028,.0127,.004,oak)
pencil_piece('pencil-graphite-point',.194,.012,.004,0,lead)
def actors():
    casts=[]
    seats=[('analyst',-2.52,.35,19),('expert',-1.62,1.04,10),('designer',-.57,1.30,6),
           ('producer',.50,1.30,-5),('checker',1.52,1.07,-10),('assistant',2.51,.42,-19)]
    for role,x,y,ang in seats:
        before=set(s.objects)
        bpy.ops.import_scene.gltf(filepath=str(MODEL/(role+'.glb')))
        obj=next(o for o in set(s.objects)-before if o.type=='MESH')
        bm=bmesh.new();bm.from_mesh(obj.data)
        # Delete only pedestal triangles. Shared glaze materials also occur on the model.
        delete=[f for f in bm.faces if max(v.co.z for v in f.verts)<=.12401 and
                 obj.data.materials[f.material_index].name.split('.')[0] in ('陶 · 象牙','墨蓝釉')]
        assert delete,role
        bmesh.ops.delete(bm,geom=delete,context='FACES')
        bm.to_mesh(obj.data);bm.free()
        zmin=min(v.co.z for v in obj.data.vertices); zmax=max(v.co.z for v in obj.data.vertices)
        assert abs(zmin-.124)<.001,(role,zmin)
        scale=1.48/(zmax-zmin)
        obj.name='agent-'+role;obj.scale=(scale,)*3;obj.rotation_mode='XYZ';obj.rotation_euler.z=math.radians(ang)
        obj.location=(x,y,-zmin*scale);casts.append(obj)
    return casts
cast=actors(); bpy.context.view_layer.update()

def extent(o):
    ev=o.evaluated_get(bpy.context.evaluated_depsgraph_get())
    zs=[(ev.matrix_world @ v.co).z for v in ev.data.vertices]
    return min(zs),max(zs)
gaps={'writing-inlay / recess':extent(pad)[0]-BED,'top / spine':extent(wood)[0]-extent(rail)[1]}
for arch in arches:
    gaps[arch.name+' / floor']=extent(arch)[0]
    gaps[arch.name+' / spine']=extent(rail)[0]-extent(arch)[1]
for ob in furniture:
    if ob.name.startswith('mount-'):
        arch=arches[0 if 'left' in ob.name else 1]
        gaps[ob.name+' / tabletop']=extent(wood)[0]-extent(ob)[1]
        gaps[ob.name+' / trestle']=extent(ob)[0]-extent(arch)[1]
for ob in cast:
    for side,sign in [('left',-1),('right',1)]:
        gaps[ob.name+' / '+side+' shoe / floor']=min((ob.matrix_world@v.co).z for v in ob.data.vertices if v.co.x*sign>0.015)
gaps['folio / writing surface']=extent(book)[0]-extent(pad)[1]
delta=extent(pad)[1]-extent(pencil)[0]
for part in (o for o in s.objects if o.name.startswith('pencil-')):part.location.z+=delta
bpy.context.view_layer.update()
gaps['pencil / writing surface']=extent(pencil)[0]-extent(pad)[1]
# Apply the reviewed layout in the same coordinate space used by the browser.
# Export once to a temp file: Blender may store an object's origin in either
# vertices or its node transform, depending on the mesh and export settings.
import tempfile
sys.path.insert(0, str(SRC))
from glb_io import pack, unpack
with tempfile.TemporaryDirectory() as temporary:
    path = Path(temporary) / 'geometry.glb'
    export(path, list(s.objects))
    scene, binary = unpack(path)
layout = json.loads((SRC / 'layout.json').read_text())
parts = layout['parts']
assert {node['name'] for node in scene['nodes']} == set(parts)
for node in scene['nodes']:
    for key in ('translation', 'rotation', 'scale'):
        node.pop(key, None)
    node.update(parts[node['name']])
(OUT / 'assembly.glb').write_bytes(pack(scene, binary))
(OUT / 'camera.json').write_text(json.dumps(layout['camera'], indent=2) + '\n')
