"""Shared calibration for all v7 and v7.1 front proofs (Blender)."""
import json
from math import radians, sin, cos
from pathlib import Path
import bpy
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view

OUT = Path(__file__).resolve().parent / "build" / "models"
PROOFS = OUT / "校样"

IDS = ("analyst","expert","designer","producer","checker","assistant")

def lighting(scene):
    scene.render.engine = "CYCLES"
    scene.cycles.samples = 14
    scene.cycles.max_bounces = 4
    scene.cycles.use_denoising = True
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 7
    scene.render.use_stamp_filename = False
    scene.render.film_transparent = True
    scene.render.image_settings.color_mode = "RGBA"
    scene.render.resolution_x, scene.render.resolution_y = 800,920
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.look = "AgX - Medium High Contrast"
    for light in scene.objects:
        if light.type != "LIGHT": continue
        data=light.data
        if light.name.startswith("左上"):
            data.energy, data.size, data.color = 525, 5.5, (1.0,.90,.84)
        elif light.name.startswith("补光"):
            data.energy, data.size, data.color = 240, 5.2, (.95,.96,1)
        elif light.name.startswith("柔边"):
            data.energy, data.size, data.color = 185, 4.8, (1,.94,.88)
    bg=scene.world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value=(.85,.81,.79,1)
    bg.inputs[1].default_value=.46

def camera(scene, degrees):
    turn = radians(degrees)
    target = Vector((0,0,1.37))
    cam=scene.camera
    cam.location=target+Vector((8*sin(turn),-8*cos(turn),.45))
    cam.rotation_euler=(target-cam.location).to_track_quat("-Z","Y").to_euler()
    cam.data.type="ORTHO"
    cam.data.ortho_scale=3.15
    bpy.context.view_layer.update()

def proof(scene,root,tag,degrees,render=True):
    camera(scene,degrees)
    if tag == "designer-old":
        # The original tall curls touch the top of the 3.15 m frame. An
        # orthographic scale change preserves both viewing angle and pose.
        scene.camera.data.ortho_scale=3.40
        bpy.context.view_layer.update()
    if render:
        scene.render.filepath=str(PROOFS/(tag+".png"))
        bpy.ops.render.render(write_still=True)
    face=next(x for x in root.children_recursive if x.name.startswith("手塑面部"))
    # The lower outline of the white beard is the elderly expert's chin landmark.
    objects=[x for x in root.children_recursive if x.name.startswith(("灰胡须","贴颌短胡须","颏部","下颌胡须","下颌灰胡须"))] + [face]
    deps=bpy.context.evaluated_depsgraph_get()
    # An orthographic projection is affine. Sample the image-y axis once,
    # then project evaluated vertices including curve bevels and modifiers.
    origin=Vector((0,0,0))
    def pixel_y(co):
        return (1-world_to_camera_view(scene,scene.camera,co).y)*scene.render.resolution_y
    offset=pixel_y(origin)
    axis=Vector([pixel_y(Vector(v))-offset for v in ((1,0,0),(0,1,0),(0,0,1))])
    def lowest(parts):
        bottom=0.0
        for ob in parts:
            if ob.type not in ("MESH","CURVE","SURFACE","FONT"): continue
            ev=ob.evaluated_get(deps)
            mesh=ev.to_mesh()
            try:
                for vertex in mesh.vertices:
                    bottom=max(bottom,offset+axis.dot(ev.matrix_world @ vertex.co))
            finally:
                ev.to_mesh_clear()
        return round(bottom,2)
    role=root["role_id"]
    props=set()
    for ob in root.children_recursive:
        if ob.name.startswith(("辨识物","陶铃别针",role+"-tool",role+"-brooch")):
            props.update(ob.children_recursive)
        if ob.name.startswith(("工作证",role+"-id-card",role+"-blue-lanyard",role+"-holding-hand",role+"-holding-thumb")):
            props.add(ob)
    marks={"chin_y":lowest(objects)}
    if props: marks["prop_bottom_y"]=lowest(props)
    return marks

def write_marks(label,marks):
    (PROOFS/(label+"-投影.json")).write_text(json.dumps(marks,ensure_ascii=False,indent=2), encoding="utf-8")
    (PROOFS/"landmarks.json").write_text(json.dumps(marks,ensure_ascii=False,indent=2), encoding="utf-8")
