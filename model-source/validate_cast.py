"""Validate the actual standalone GLBs and PNGs, then reopen the source .blend and each exported GLB in Blender."""
import json
import argparse
import sys
import hashlib
from datetime import datetime, timezone
from pathlib import Path
import struct
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
import numpy as np

HERE=Path(__file__).resolve().parent
BUILD = HERE / "build"
SCENE = BUILD / "cast.blend"
parser = argparse.ArgumentParser(description="核对八份 GLB、预渲染 PNG 和从源码重建的可编辑场景")
parser.add_argument("--published", action="store_true", help="比对发行目录已有的模型与图片")
args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
OUT = HERE.parent / "models" if args.published else BUILD / "models"
IDS=('analyst','expert','designer','producer','checker','assistant','teacher-female','teacher-male')

def read_glb(path):
    data=path.read_bytes();magic,version,length=struct.unpack_from('<4sII',data)
    assert magic==b'glTF' and version==2 and length==len(data)
    json_length,kind=struct.unpack_from('<I4s',data,12)
    assert kind==b'JSON'
    obj=json.loads(data[20:20+json_length])
    buf_length,kind=struct.unpack_from('<I4s',data,20+json_length)
    binary=data[28+json_length:]
    assert kind==b'BIN\0' and len(binary)==buf_length and len(obj['buffers'])==1
    assert not obj.get('extensionsRequired') and not obj.get('images') and all('uri' not in b for b in obj['buffers'])
    assert len(obj['nodes'])==1 and obj['nodes'][0]['mesh']==0 and len(obj['meshes'])==1
    assert not any(k in obj['nodes'][0] for k in ('matrix','translation','rotation','scale'))
    def lookup(i):
        a=obj['accessors'][i];view=obj['bufferViews'][a['bufferView']]
        types={5126:'<f4',5125:'<u4',5123:'<u2',5121:'u1'}
        dtype=np.dtype(types[a['componentType']]);nc={'SCALAR':1,'VEC3':3}[a['type']]
        offset=view.get('byteOffset',0)+a.get('byteOffset',0)
        stride=view.get('byteStride',nc*dtype.itemsize)
        array=np.ndarray((a['count'],nc),dtype,buffer=binary,offset=offset,strides=(stride,dtype.itemsize))
        assert offset+(a['count']-1)*stride+nc*dtype.itemsize<=view.get('byteOffset',0)+view['byteLength']
        return array
    positions=[];triangles=0;vertices=0;materials=set()
    for primitive in obj['meshes'][0]['primitives']:
        assert primitive.get('mode',4)==4
        xyz=lookup(primitive['attributes']['POSITION'])
        normal=lookup(primitive['attributes']['NORMAL'])
        indices=lookup(primitive['indices']).ravel()
        assert xyz.shape==normal.shape and np.isfinite(xyz).all() and np.isfinite(normal).all()
        assert len(indices)%3==0 and indices.size and indices.min()>=0 and indices.max()<len(xyz)
        assert np.allclose(np.linalg.norm(normal,axis=1),1,atol=.002)
        material=primitive['material'];assert 0<=material<len(obj['materials'])
        materials.add(material);positions.append(xyz);triangles+=len(indices)//3;vertices+=len(xyz)
    xyz=np.concatenate(positions);lo=xyz.min(axis=0);hi=xyz.max(axis=0)
    assert abs(lo[1])<1e-5 and np.all(hi>lo)
    return xyz, {'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'meshes':1,'material_count':len(materials),'vertices':vertices,'indexed_triangles':triangles,
            'bounds_gltf_min':np.round(lo.astype(float),5).tolist(),'bounds_gltf_max':np.round(hi.astype(float),5).tolist()}

def image_frame(path,avatar=False):
    im=bpy.data.images.load(str(path));width,height=im.size
    raw=np.empty(width*height*4,dtype=np.float32);im.pixels.foreach_get(raw)
    alpha=raw.reshape(height,width,4)[::-1,:,3];y,x=np.nonzero(alpha>.03)
    bounds=[int(x.min()),int(y.min()),int(x.max()),int(y.max())]
    assert (width,height)==((640,640) if avatar else (800,920)) and im.channels==4 and alpha.min()==0 and alpha.max()>.99
    assert min(bounds[0],bounds[1],width-1-bounds[2])>=8
    if not avatar:assert height-1-bounds[3]>=8
    bpy.data.images.remove(im)
    return {'dimensions':[width,height],'alpha_bbox_ltrb':bounds,'transparent_pixels_percent':round(float(np.mean(alpha<.001))*100,2)}

def evaluated_part(ob, deps, root_inverse, *, export_matrix=None):
    """Return final geometry after modifiers, in the coordinate system of the exported root."""
    evaluated = ob.evaluated_get(deps)
    mesh = evaluated.to_mesh()
    try:
        matrix = root_inverse @ (evaluated.matrix_world if export_matrix is None else export_matrix)
        local = [matrix @ v.co for v in mesh.vertices]
        faces = [tuple(p.vertices) for p in mesh.polygons]
        assert local and faces, ob.name
        return np.asarray(local), BVHTree.FromPolygons(local, faces)
    finally:
        evaluated.to_mesh_clear()


def nearest_vertex_error(a, b):
    def distances(points, target):
        tree = KDTree(len(target))
        for index, vertex in enumerate(target):
            tree.insert(vertex, index)
        tree.balance()
        return max(tree.find(vertex)[2] for vertex in points)
    # Joining, triangulating, and splitting normals may duplicate vertices.
    return max(distances(a,b), distances(b,a))


def check_source(glb_vertices):
    bpy.ops.wm.open_mainfile(filepath=str(SCENE))
    scene = bpy.context.scene
    assert set(c.name for c in scene.collection.children) == set(IDS)
    assert not bpy.data.libraries
    deps = bpy.context.evaluated_depsgraph_get()
    deps.update()
    result = {}
    for index, role in enumerate(IDS):
        co = bpy.data.collections[role]
        roots = [o for o in co.objects if o.parent is None and o.get('role_id') == role]
        assert len(roots) == 1, role
        root = roots[0]
        editable = [o for o in root.children_recursive if o.type in ('MESH','CURVE')]
        root_inverse = root.matrix_world.inverted()
        geometry = {o.name:evaluated_part(o,deps,root_inverse) for o in editable}
        def component(prefix):
            hits = [name for name in geometry if name.startswith(prefix)]
            assert len(hits) == 1,(role,prefix,hits)
            return hits[0]
        def match(prefix):
            return [name for name in geometry if name.startswith(prefix)]
        points = np.concatenate([g[0] for g in geometry.values()])
        source_gltf = np.column_stack((points[:,0],points[:,2],-points[:,1]))
        max_error = nearest_vertex_error(source_gltf,glb_vertices[role])
        export_error = max_error
        if index >= 6:
            # Reproduce the actual repo exporter: assign each component's world
            # transform to a fresh, unparented Blender object (default Euler XYZ).
            # Ask Blender itself to evaluate this assignment before testing vertices.
            copies = []
            try:
                for ob in editable:
                    copy = bpy.data.objects.new('验证用临时变换',None)
                    scene.collection.objects.link(copy)
                    copy.matrix_world = ob.evaluated_get(deps).matrix_world.copy()
                    copies.append(copy)
                bpy.context.view_layer.update()
                baked = np.concatenate([evaluated_part(o,deps,root_inverse,export_matrix=m.matrix_world)[0]
                                        for o,m in zip(editable,copies)])
            finally:
                for copy in copies:
                    bpy.data.objects.remove(copy,do_unlink=True)
            baked_gltf = np.column_stack((baked[:,0],baked[:,2],-baked[:,1]))
            export_error = nearest_vertex_error(baked_gltf,glb_vertices[role])
        assert export_error < .00003,(role,"GLB/exported-source vertex mismatch",export_error)
        deck = geometry[component('底座上面')]
        soles = match('贴地鞋底')
        assert len(soles)==2
        shoe_gaps = {}
        for sole in soles:
            foot = geometry[sole][0]
            floor_z = float(foot[:,2].min())
            below = foot[np.abs(foot[:,2]-floor_z) < .00001,:2]
            xy = below.mean(axis=0)
            # A vertical ray through each sole tests that it is positioned over real deck geometry.
            hit, _, _, _ = deck[1].ray_cast((xy[0],xy[1],floor_z+.04),(0,0,-1))
            assert hit is not None,(role,sole,'outside platform')
            gap = floor_z-hit.z
            assert abs(gap)<.00002,(role,sole,gap)
            shoe_gaps[sole] = round(gap,9)
        face_name = component('手塑面部' if index<6 else '成年面部')
        face = geometry[face_name][0]
        eyes = [geometry[n][0] for n in match('墨釉眼睛')]
        center_y = (face[:,1].min()+face[:,1].max())/2
        eye_depths = [float(center_y-eye[:,1].mean()) for eye in eyes]
        assert len(eyes)==2 and min(eye_depths)>0,(role,eye_depths)
        # A tilted head's axis-aligned object box encloses empty corners. Use real crown
        # and anatomical chin vertices; count a beard where it extends the chin contour.
        face_object=bpy.data.objects[face_name]
        head = face_object.parent
        assert head and '头部' in head.name,(role,face_name)
        head_parts = [geometry[o.name][0] for o in head.children_recursive if o.name in geometry]
        hair_top = max(float(a[:,2].max()) for a in head_parts)
        chin_surfaces = [face] + [geometry[n][0] for n in match(('灰胡须','颏部','下颌胡须'))]
        chin = min(float(a[:,2].min()) for a in chin_surfaces)
        stand = float(deck[0][:,2].max())
        height, head_height = hair_top-stand, hair_top-chin
        assert 0 < head_height < height,(role,chin,hair_top,stand)
        info = {'editable_parts':len(editable),'foot_to_base_signed_gaps':shoe_gaps,
                'foot_to_base_max_gap':max(abs(g) for g in shoe_gaps.values()),
                'face_direction_checked':'+Z (glTF)','eye_forward_offsets':np.round(eye_depths,5).tolist(),
                'figure_height':round(height,5),'head_crown_to_chin':round(head_height,5),
                'figure_height_in_head_units':round(height/head_height,4),
                'source_full_affine_glb_bidirectional_vertex_max_error':float(f'{max_error:.6g}'),
                'source_export_bake_glb_bidirectional_vertex_max_error':float(f'{export_error:.6g}')}
        if index < 6:
            p=role+'-'
            prop=p+('tablet-frame','book-cover','sketch-card','play-plaque','magnifier-handle','speech-bubble')[index]
            pairs = [
                ('胸针与衣身',p+'bell-backing',p+'garment'),
                ('抬起侧肩袖与衣身',p+'holding-sleeve',p+'garment'),
                ('抬起侧袖口与手',p+'holding-sleeve',p+'holding-hand'),
                ('持物手与道具',p+'holding-hand',prop),
                ('拇指与手掌',p+'holding-thumb',p+'holding-hand'),
                ('下垂侧肩袖与衣身',p+'relaxed-sleeve',p+'garment'),
                ('下垂侧袖口与手',p+'relaxed-sleeve',p+'relaxed-hand'),
                ('颈部与面部',p+'neck',face_name),
                ('衣身与髋部',p+'garment',component('裤腰及髋部'))]
            joins = []
            for label, left_name, right_name in pairs:
                left,right = geometry[left_name][1],geometry[right_name][1]
                count=len(left.overlap(right))
                assert count > 0,(role,label,left_name,right_name)
                joins.append({'joint':label,'parts':[left_name,right_name],'intersecting_polygon_pairs':count})
            info['body_contacts'] = joins
        result[role]=info
    return result

def reopen_glb(path,metrics):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    assert bpy.ops.import_scene.gltf(filepath=str(path))=={'FINISHED'}
    objects=[ob for ob in bpy.context.scene.objects if ob.type=='MESH']
    assert len(objects)==1 and len(objects[0].data.materials)==metrics['material_count']
    ob=objects[0];bounds=np.array([tuple(ob.matrix_world@Vector(p)) for p in ob.bound_box])
    gltf=np.column_stack((bounds[:,0],bounds[:,2],-bounds[:,1]))
    assert np.allclose(gltf.min(axis=0),metrics['bounds_gltf_min'],atol=.00003)
    assert np.allclose(gltf.max(axis=0),metrics['bounds_gltf_max'],atol=.00003)
    return True

metrics = {}
positions = {}
for role in IDS:
    path = OUT/(role+'.glb')
    positions[role],metrics[role] = read_glb(path)
    metrics[role]['png'] = image_frame(OUT/(role+'.png'))
    if role.startswith('teacher-'):
        metrics[role]['front_face_avatar'] = image_frame(OUT/(role+'-avatar.png'),True)
for role,source in check_source(positions).items():
    metrics[role].update(source)
for role in IDS:
    metrics[role]['blender_reimported'] = reopen_glb(OUT/(role+'.glb'),metrics[role])

report={'inputs':'published' if args.published else 'rebuilt','verified_utc':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'kind':'从本版源场景和交付文件重新核验','blender_version':list(bpy.app.version),
        'source_scene_sha256':hashlib.sha256(SCENE.read_bytes()).hexdigest(),
        'summary':{'source_collections':len(IDS),'glbs_reopened':sum(v['blender_reimported'] for v in metrics.values()),
                   'agent_joint_checks':sum(len(v.get('body_contacts',[])) for v in metrics.values()),
                   'sole_support_checks':sum(len(v['foot_to_base_signed_gaps']) for v in metrics.values())},
        'teacher_source_note':'两位教师沿用 v7 的 GLB。v7 与 v7.1 源文件的完整仿射变换均保留非等比父缩放带来的切变；旧导出器将各部件矩阵拆为平移、旋转、缩放后合并，袖管等处有微小偏差。报告分别记录源显示几何与真实导出变换的误差。',
        'axes':'glTF +Y 向上，脸朝 +Z；距离以模型单位计。',
        'measurement':'头高为头部可见最高顶点至颏底或胡须下缘，身高从底座上缘至同一头顶。鞋底中心垂线必须命中底座实体，报告高差为有符号距离。两个方向的最近顶点最大误差比对源文件求值几何与导出 GLB。六位智能体的九处接合以独立列出的组件和实际求值后网格表面相交验证。',
        'assets':metrics}
target = BUILD / ('published-check.json' if args.published else 'rebuilt-check.json')
temporary=target.with_suffix('.tmp')
temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n', encoding='utf-8')
temporary.replace(target)
print('VERIFIED',report['summary'],flush=True)
