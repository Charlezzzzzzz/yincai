"""Render the actual redistributed GLB from camera.json, rather than an alternate scene."""
import bpy,json,sys
from mathutils import Vector
from pathlib import Path
here=Path(sys.argv[sys.argv.index('--')+1]).resolve() if '--' in sys.argv else Path(__file__).resolve().parents[1]
bpy.ops.wm.read_factory_settings(use_empty=True)
s=bpy.context.scene
bpy.ops.import_scene.gltf(filepath=str(here/'assembly.glb'))
spec=json.loads((here/'camera.json').read_text())
def blender_vec(v):return Vector((v[0],-v[2],v[1]))
def aim(obj, target):obj.rotation_euler=(Vector(target)-obj.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.camera_add(location=blender_vec(spec['eye']))
cam=bpy.context.object;cam.data.type='ORTHO';cam.data.ortho_scale=spec['width'];aim(cam,blender_vec(spec['target']));s.camera=cam
bpy.ops.mesh.primitive_plane_add(size=200,location=(0.,0.,-.00003))
mat=bpy.data.materials.new('Ivory photography floor');mat.diffuse_color=(.835,.813,.747,1);mat.use_nodes=True
bs=mat.node_tree.nodes['Principled BSDF'];bs.inputs['Base Color'].default_value=mat.diffuse_color;bs.inputs['Roughness'].default_value=.91;bpy.context.object.data.materials.append(mat)
s.world=bpy.data.worlds.new('Soft daylight');s.world.use_nodes=True
b=s.world.node_tree.nodes['Background'];b.inputs[0].default_value=(.94,.945,1,1);b.inputs[1].default_value=.43
def light(name,loc,energy,size,color):
    bpy.ops.object.light_add(type='AREA',location=loc);o=bpy.context.object;o.name=name;o.data.shape='DISK';o.data.energy=energy;o.data.size=size;o.data.color=color;aim(o,(0,0,.5))
light('Window',(-4.,-4.1,6.7),830,5.0,(1,.94,.85))
light('Cool fill',(4,-2.8,4.1),360,4.2,(.9,.95,1))
light('Warm bounce',(2,4.1,5.8),640,3.4,(1,.96,.87))
s.render.engine='CYCLES';s.cycles.samples=24;s.cycles.use_denoising=True;s.cycles.max_bounces=5
s.render.threads_mode='FIXED';s.render.threads=8
s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGB';s.render.use_stamp_filename=False
s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast'
s.render.resolution_x=spec['pixelWidth'];s.render.resolution_y=spec['pixelHeight'];s.render.resolution_percentage=100
s.render.filepath=str(here/'hero.png');bpy.ops.render.render(write_still=True)
