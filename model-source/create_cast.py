"""Build the six revised portrait sculpts and the two established teacher looks."""
import json
import argparse
import shutil
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree
import yincai_base as base
from portrait_bodies import build_body, verify_body_contacts
from portrait_heads import build_portrait
from portrait_studio import OUT, PROOFS, lighting, proof, write_marks

def intersections(first, second):
    deps=bpy.context.evaluated_depsgraph_get()
    def surface(ob):
        evaluated=ob.evaluated_get(deps)
        geom=evaluated.to_mesh()
        try:
            return BVHTree.FromPolygons([evaluated.matrix_world@v.co for v in geom.vertices],
                                        [list(p.vertices) for p in geom.polygons])
        finally:
            evaluated.to_mesh_clear()
    return len(surface(first).overlap(surface(second)))

def make_agent(i):
    role=base.IDS[i]
    root=base.empty(role+"-root")
    torso=base.empty(role+"-衣身与头部",(0,0,.405),root)
    build_body(i,torso)
    build_portrait(i,torso)
    deck=base.pedestal(root,.615)
    base.shoes_and_legs(root,.665,.164,deck,base.pants if i not in (1,2) else base.hair_brown)
    root["upper_pivot"]=torso.name
    if i==5: root["role_gender"]="男生"
    return root

def audit(root, role):
    bpy.context.view_layer.update()
    torso=bpy.data.objects[root["upper_pivot"]]
    def component(prefix):
        return next(o for o in root.children_recursive if o.name.startswith(prefix))
    result=verify_body_contacts(torso)
    pairs=[("颈部与面部",component(role+"-neck"),component("手塑面部")),
           ("衣身与髋部",component(role+"-garment"),component("裤腰及髋部"))]
    for label, a, b in pairs:
        count=intersections(a,b)
        if not count: raise ValueError((role,label,a.name,b.name))
        result.append({"joint":label,"parts":[a.name,b.name],"intersecting_polygon_pairs":count})
    return {"joins":result,"foot_gaps":base.validate_contacts(root)}

def build(scene_only=False):
    build_dir = HERE / "build"
    build_dir.mkdir(exist_ok=True)
    scene=bpy.context.scene
    old=bpy.data.collections.get("Collection")
    if old and not old.objects:bpy.data.collections.remove(old)
    roots=[]; spots=[]; groups=[]
    for i,role in enumerate(base.IDS):
        group=bpy.data.collections.new(role);scene.collection.children.link(group)
        root=make_agent(i) if i<6 else base.make_teacher(i==6)
        root.name=role+"-root"
        root["role_id"]=role;root["display_name"]=base.NAMES[i]
        root["kind"]="agent" if i<6 else "human-teacher"
        base.move_to_collection(root,group)
        spot=((-1.5+i%4)*2.24,(i//4-.5)*3.0,0)
        root.location=spot; spots.append(spot); roots.append(root); groups.append(group)
    cam=base.studio();base.configure_camera(cam,True)
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type=="VIEW_3D":
                sp=area.spaces.active; sp.region_3d.view_rotation=cam.rotation_euler.to_quaternion()
                sp.region_3d.view_location=(0,0,1);sp.region_3d.view_distance=10;sp.shading.color_type="MATERIAL"
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.preferences.filepaths.save_version=0
    bpy.ops.wm.save_as_mainfile(filepath=str(build_dir/"cast.blend"),compress=True)
    if scene_only:
        return
    PROOFS.mkdir(parents=True, exist_ok=True)
    # Teachers retain the original studio, full-body framing and separate portrait camera.
    for i in (6, 7):
        role = base.IDS[i]
        root = roots[i]
        for j, group in enumerate(groups):
            group.hide_render = j != i
        root.location = (0, 0, 0)
        bpy.context.view_layer.update()
        base.validate_contacts(root)
        base.export_joined(root, OUT / (role + ".glb"))
        base.configure_camera(cam)
        scene.render.resolution_x, scene.render.resolution_y = 800, 920
        scene.render.filepath = str(OUT / (role + ".png"))
        bpy.ops.render.render(write_still=True)
        cam.location = (0, -8, 2.70)
        cam.rotation_euler = (Vector((0, 0, 2.355)) - cam.location).to_track_quat("-Z", "Y").to_euler()
        cam.data.ortho_scale = 1.73
        scene.render.resolution_x, scene.render.resolution_y = 640, 640
        scene.render.filepath = str(OUT / (role + "-avatar.png"))
        bpy.ops.render.render(write_still=True)
        root.location = spots[i]
    lighting(scene)
    results={};marks={}
    for i in (5,0,1,2,3,4):
        role=base.IDS[i]; root=roots[i]
        for j,group in enumerate(groups):group.hide_render=j!=i
        root.location=(0,0,0);bpy.context.view_layer.update()
        results[role]=audit(root,role)
        base.export_joined(root,OUT/(role+".glb"))
        label=role+"-front";marks[label]=proof(scene,root,label,0)
        shutil.copyfile(PROOFS/(label+".png"),OUT/(role+".png"))
        if role=="assistant":
            label=role+"-three";marks[label]=proof(scene,root,label,32)
        root.location=spots[i]
        print("BUILT",role,flush=True)
    write_marks("v7.1",marks)
    (OUT/"接合复核.json").write_text(json.dumps(results,ensure_ascii=False,indent=2), encoding="utf-8")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-only", action="store_true", help="仅构建封面与核验所用的可编辑场景")
    args = parser.parse_args(sys.argv[sys.argv.index("--")+1:] if "--" in sys.argv else [])
    build(args.scene_only)
