"""Six original portrait-derived bodies in Blender coordinates: Z up, face towards -Y."""
import json
from math import cos, pi, sin, sqrt

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import yincai_base as base


ROLES = ("analyst", "expert", "designer", "producer", "checker", "assistant")
# The same tailoring profile drives the shell, shirt inserts, lapels and brooch backs.
BODY_RINGS = (
    (.175, .345, .222), (.182, .379, .242), (.202, .408, .256),
    (.244, .426, .266), (.350, .446, .279), (.475, .453, .282),
    (.580, .435, .270), (.665, .403, .249), (.735, .351, .218),
    (.793, .285, .187), (.839, .213, .160), (.878, .154, .133),
    (.905, .125, .115),
)


def front_y(x, z):
    for (lo, rx, ry), (hi, ux, uy) in zip(BODY_RINGS, BODY_RINGS[1:]):
        if z <= hi:
            t = max(0.0, (z-lo)/(hi-lo))
            a, b = rx+(ux-rx)*t, ry+(uy-ry)*t
            return -b*sqrt(max(.01, 1-(x/a)**2))
    return -BODY_RINGS[-1][2]*sqrt(max(.01, 1-(x/BODY_RINGS[-1][1])**2))


def garment_point(x, z, relief=0):
    return (x, front_y(x,z)-relief, z)


def rounded_patch(name, outline, relief, mat, actor):
    """Slightly curved fabric patch with rounded corners and real finished edge."""
    pts = [Vector(p) for p in outline]
    contour = []
    for i,p in enumerate(pts):
        incoming, outgoing = pts[i-1].lerp(p,.90), p.lerp(pts[(i+1)%len(pts)],.10)
        for t in (0., .25, .50, .75, 1.):
            contour.append((1-t)**2*incoming+2*(1-t)*t*p+t*t*outgoing)
    if sum(p.x*contour[(i+1)%len(contour)].y-contour[(i+1)%len(contour)].x*p.y
           for i,p in enumerate(contour)) < 0:
        contour.reverse()
    center = sum(contour,Vector((0,0)))/len(contour)
    vertices = [garment_point(center.x,center.y,relief)]
    faces = []
    # Three concentric loops carry larger inserts over a curved chest.
    for j,fraction in enumerate((.34,.67,1.)):
        for p in contour:
            q=center.lerp(p,fraction)
            vertices.append(garment_point(q.x,q.y,relief))
        for i in range(len(contour)):
            k=(i+1)%len(contour); start=1+j*len(contour)
            faces.append((0,start+i,start+k) if j==0 else
                         (start+i-len(contour),start+i,start+k,start+k-len(contour)))
    ob=base.mesh(name,vertices,faces,mat,actor,True)
    mod=ob.modifiers.new("布料厚度","SOLIDIFY");mod.thickness=.009;mod.offset=-1
    mod=ob.modifiers.new("柔软卷边","BEVEL");mod.width=.004;mod.segments=2
    return ob


def sleeve_tube(name, points, radii, mat, actor):
    """A curved soft sleeve with no seam between shoulder, elbow and wrist."""
    points=[Vector(p) for p in points]
    centers=[]; widths=[]
    for j in range(len(points)-1):
        a=points[max(j-1,0)];b=points[j];c=points[j+1];d=points[min(j+2,len(points)-1)]
        for k in range(6):
            t=k/6; t2=t*t; t3=t2*t
            centers.append(.5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t2+(-a+3*b-3*c+d)*t3))
            widths.append(radii[j]*(1-t)+radii[j+1]*t)
    centers.append(points[-1]); widths.append(radii[-1])
    verts=[];faces=[]; sides=22
    for j,p in enumerate(centers):
        tangent=(centers[min(len(centers)-1,j+1)]-centers[max(0,j-1)]).normalized()
        side=tangent.cross(Vector((0,1,0))).normalized()
        if not side.length: side=Vector((1,0,0))
        forward=tangent.cross(side).normalized()
        for i in range(sides):
            theta=2*pi*i/sides
            verts.append(p+widths[j]*(cos(theta)*side+sin(theta)*forward*.97))
        if j:
            for i in range(sides):
                k=(i+1)%sides
                faces.append(((j-1)*sides+i,(j-1)*sides+k,j*sides+k,j*sides+i))
    faces.extend([tuple(reversed(range(sides))),tuple(range(len(verts)-sides,len(verts)))])
    return base.mesh(name,verts,faces,mat,actor,True)


def rim_at(name, start, end, radius, mat, actor, thickness=.008):
    axis=(Vector(end)-Vector(start)).normalized()
    a=axis.cross(Vector((0,1,0))).normalized()
    b=axis.cross(a).normalized()
    ring=[Vector(end)+radius*(cos(2*pi*i/26)*a+sin(2*pi*i/26)*b*.97) for i in range(26)]
    return base.line(name,ring,thickness,mat,actor,True)


def oval_disc(name, center, width, height, depth, mat, parent):
    return base.globe(name,center,(width/2,depth/2,height/2),mat,parent)


def bubble_plate(name, mat, parent):
    # A single closed outline keeps the rounded tail continuous with the ceramic bubble.
    start=(-.172,.005)
    segments=[
        ((-.178,.088),(-.112,.134),(-.038,.138)),
        ((.041,.148),(.113,.142),(.148,.106)),
        ((.179,.070),(.182,.011),(.161,-.039)),
        ((.150,-.061),(.134,-.074),(.121,-.082)),
        ((.119,-.105),(.131,-.134),(.142,-.150)),
        ((.116,-.146),(.079,-.135),(.051,-.113)),
        ((.028,-.114),(-.034,-.114),(-.066,-.107)),
        ((-.140,-.095),(-.177,-.057),start)
    ]
    path=bpy.data.curves.new(name,"CURVE");path.dimensions="2D";path.fill_mode="BOTH"
    path.resolution_u=8; path.bevel_resolution=3; path.bevel_depth=.012; path.extrude=.026
    spl=path.splines.new("BEZIER");spl.bezier_points.add(len(segments)-1);spl.use_cyclic_u=True
    vertices=[start]+[seg[2] for seg in segments[:-1]]
    for i,(point,p) in enumerate(zip(spl.bezier_points,vertices)):
        point.co=(*p,0);point.handle_left_type="FREE";point.handle_right_type="FREE"
        point.handle_left=(*segments[(i-1)%len(segments)][1],0)
        point.handle_right=(*segments[i][0],0)
    ob=bpy.data.objects.new(name,path);bpy.context.scene.collection.objects.link(ob)
    base.finish(ob,name,mat,parent);ob.rotation_euler.x=pi/2
    return ob


def make_tool(role,actor,p):
    # Anchor is on the actual object in prop-local coordinates. Palm, cuff and sleeve
    # are built from that transformed point, including the prop's tilt.
    centers=(
        (-.23,-.301,.625),(-.244,-.275,.596),(-.250,-.293,.655),
        (-.242,-.305,.628),(-.225,-.337,.699),(-.302,-.353,.690),
    )
    tool=base.empty(p+"tool",centers[role],actor)
    tool.rotation_euler.y=(-.09,.235,-.165,-.11,.08,-.06)[role]
    if role==0:
        obj=base.block(p+"tablet-frame",(0,0,0),(.329,.068,.298),base.clay,.034,tool)
        base.block(p+"tablet-screen",(0,-.034,0),(.275,.014,.239),base.paper,.018,tool)
        for i,h in enumerate((.075,.126,.169)):
            base.block(p+"chart-column-"+str(i),(-.077+.073*i,-.047,-.084+h/2),
                       (.052,.015,h),(base.chartblue,base.chartviolet,base.chartred)[i],.009,tool)
        anchor=(-.145,-.031,-.094)
    elif role==1:
        # The front cover, back cover, cream pages and rounded spine enclose real volume.
        base.block(p+"book-back",(0,.045,0),(.275,.025,.337),base.pine,.014,tool)
        base.block(p+"book-paper",(0,.003,0),(.249,.068,.312),base.paper,.011,tool)
        obj=base.block(p+"book-cover",(0,-.042,0),(.275,.031,.337),base.pine,.016,tool)
        base.block(p+"book-spine",(-.124,.001,0),(.037,.099,.333),base.pine,.016,tool)
        for z in (.102,.122):
            base.line(p+"book-emboss", [(-.097,-.061,z),(-.040,-.061,z)],.003,base.patina,tool)
        anchor=(-.113,-.049,-.083)
    elif role==2:
        obj=base.block(p+"sketch-card",(0,0,0),(.293,.048,.258),base.notecard,.021,tool)
        # Hand-drawn landscape on a small square planning card.
        base.line(p+"sketch-hill",[(-.091,-.030,-.067),(-.048,-.031,-.008),(-.014,-.031,.012),
                                  (.025,-.031,-.019),(.066,-.031,.015),(.104,-.031,-.065)],.008,base.walnut,tool)
        base.line(p+"sketch-ground",[(-.097,-.032,-.071),(.100,-.032,-.071)],.005,base.walnut,tool)
        base.oval_line(p+"sketch-sun",(.050,-.029,.067),.025,.027,base.walnut,tool,.006)
        for i in range(2):
            base.line(p+"pencil-mark",[(-.084+i*.029,-.030,.071),(-.075+i*.029,-.030,.047)],.006,base.walnut,tool)
        anchor=(-.128,-.028,-.081)
    elif role==3:
        obj=base.block(p+"play-plaque",(0,0,0),(.309,.070,.218),base.ivory,.033,tool)
        base.tile(p+"play-triangle",[(-.035,-.046,-.054),(.060,-.046,0),(-.035,-.046,.056)],base.hood_black,tool)
        anchor=(-.136,-.033,-.065)
    elif role==4:
        obj=base.along(p+"magnifier-handle",(-.098,.002,-.260),(-.030,.002,-.086),.032,base.walnut,tool)
        base.oval_line(p+"magnifier-rim",(0,0,0),.122,.126,base.walnut,tool,.022)
        oval_disc(p+"magnifier-lens",(0,-.004,0),.222,.230,.047,base.ivory,tool)
        base.line(p+"check-mark",[(-.060,-.033,.001),(-.020,-.034,-.034),(.058,-.033,.045)],.018,base.rust,tool)
        anchor=(-.085,-.017,-.217)
    else:
        obj=bubble_plate(p+"speech-bubble",base.ivory,tool)
        for i,x in enumerate((-.071,0,.071)):
            oval_disc(p+"speech-dot-"+str(i),(x,-.041,.016),.040,.043,.018,base.blackeye,tool)
        anchor=(-.100,-.023,-.093)
    local=tool.matrix_basis@Vector(anchor)
    return obj,local


def make_collar(role,coat,actor,p):
    base.profile(p+"neck",[(.821,.143,.114),(.856,.137,.122),(.937,.117,.109),(.955,.108,.102)],base.skin,actor)
    if role in (0,3):
        outer=coat
        inner=base.lavender if role==0 else base.hood_black
        # The hood continues around the nape before the two thick front rolls fold in.
        base.padded_lock(p+"hood-back",[(-.289,-.079,.762),(-.272,.103,.796),(0,.184,.853),
                                        (.272,.103,.796),(.289,-.079,.762)],
                         [.051,.099,.113,.099,.051],outer,actor)
        for sign in (-1,1):
            pts=[(sign*.282,-.055,.770),(sign*.252,-.130,.807),(sign*.185,-.192,.794),
                 (sign*.087,-.237,.712),(sign*.032,-.257,.655)]
            base.padded_lock(p+"hood-roll",pts,[.055,.091,.068,.048,.026],outer,actor)
            pts=[garment_point(sign*x,z,.022) for x,z in ((.070,.707),(.072,.646),(.080,.572),(.085,.532))]
            base.line(p+"hood-drawcord",pts,.011,base.cream if role==0 else inner,actor)
            oval_disc(p+"drawcord-tip",pts[-1],.033,.046,.031,base.cream if role==0 else inner,actor)
        return
    garment=base.expert_sleeve if role==1 else base.cream
    depth={1:.52,2:.68,4:.60,5:.49}[role]
    rounded_patch(p+"shirt-insert",[(-.171,.810),(-.117,.879),(0,.837),(.117,.879),(.171,.810),
                                    (0,depth)],.013,garment,actor)
    if role in (1,4,5):
        for sign in (-1,1):
            # Open fronts sit to either side of the shirt, with a turned lapel.
            xz=[(sign*x,z) for x,z in ((.153,.839),(.264,.774),(.223,.730),(.243,.720),(.037,depth-.022))]
            rounded_patch(p+"vest-binding",xz,.017,coat,actor)
            if role==4:
                base.line(p+"jacket-piping",[garment_point(sign*x,z,.025) for x,z in
                          ((.252,.767),(.201,.732),(.222,.717),(.061,.581))],.005,base.walnut,actor)
    for sign in (-1,1):
        collar=[(sign*x,z) for x,z in ((.031,.833),(.112,.890),(.177,.845),(.115,.747))]
        rounded_patch(p+"point-collar",collar,.033,garment,actor)
    if role==1:
        rounded_patch(p+"knotted-tie",[(-.055,.810),(0,.836),(.055,.810),(.030,.758),(.052,.659),
                                      (0,.600),(-.050,.659),(-.028,.758)],.035,base.walnut,actor)
        for z in (.405,.291):
            oval_disc(p+"vest-button",garment_point(.016,z,.013),.038,.040,.020,base.walnut,actor)
    elif role==2:
        base.line(p+"blouse-placket",[garment_point(.008,z,.006) for z in (.693,.58,.43,.27)],.006,base.expert_sleeve,actor)
        for z in (.602,.440,.285):
            oval_disc(p+"shell-button",garment_point(.010,z,.015),.023,.024,.013,base.expert_sleeve,actor)
    elif role==5:
        # Two flat woven straps meet under the clip. Their V and the small white badge
        # are the recognisable silhouette of the assistant's uniform in the portrait.
        for sign in (-1,1):
            strap=[(sign*x,z) for x,z in ((.172,.818),(.207,.799),(.027,.475),(.000,.510))]
            rounded_patch(p+"blue-lanyard",strap,.043,base.denim,actor)
        base.block(p+"id-card",(0,front_y(0,.398)-.034,.390),(.197,.044,.162),base.ivory,.021,actor)
        base.block(p+"id-clip",(0,front_y(0,.489)-.052,.490),(.059,.025,.055),base.chartblue,.012,actor)


def bell(actor,p):
    x,z=.237,.578; y=front_y(x,z)
    pin=base.empty(p+"brooch",(x,y-.005,z),actor)
    # The back touches the garment; the domed front, flared lip and clapper overlap.
    pin.rotation_euler.z=.34
    backing=base.globe(p+"bell-backing",(0,0,.017),(.054,.025,.057),base.stamp,pin)
    base.globe(p+"bell-loop",(0,-.006,.105),(.020,.019,.029),base.stamp,pin)
    base.profile(p+"bell-dome",[(-.018,.073,.041),(-.009,.072,.042),(.006,.061,.039),
                               (.026,.054,.036),(.058,.041,.026),(.081,.024,.018),(.086,.015,.014)],
                 base.stamp,pin)
    base.globe(p+"bell-rim",(0,-.002,-.014),(.077,.044,.020),base.stamp,pin)
    base.globe(p+"bell-clapper",(0,-.003,-.030),(.028,.018,.018),base.walnut,pin)
    return backing


def build_body(role, actor):
    role=ROLES.index(role) if isinstance(role,str) else role
    p=ROLES[role]+"-"
    coat=(base.lavender,base.walnut,base.cream,base.hood_black,base.wine,base.periwinkle)[role]
    sleeve_mat=base.expert_sleeve if role==1 else coat
    torso=base.profile(p+"garment",BODY_RINGS,coat,actor)
    make_collar(role,coat,actor,p)
    # Short welt under the rounded hem; it follows the body all the way around.
    hem=[(.398*cos(2*pi*i/48),.252*sin(2*pi*i/48),.192) for i in range(48)]
    base.line(p+"hem",hem,.008,coat,actor,True)
    backing=bell(actor,p)
    held,grip=make_tool(role,actor,p)
    checks=[]
    def pair(label,first,second,point):
        checks.append({"joint":label,"parts":[first.name,second.name],
                       "anchor_actor_local":[round(float(n),6) for n in point]})
    pair("brooch–garment",backing,torso,garment_point(.237,.595))
    shoulder=Vector((-.307,-.016,.690))
    # The curled palm meets the prop first; the wrist and sleeve are derived from it.
    palm_center=grip+Vector((-.029,-.034,-.035))
    cuff_center=palm_center+Vector((-.032,.045,-.049))
    elbow=Vector((-.421,-.111,.389 if role!=5 else .428))
    points=[shoulder,Vector((-.398,-.044,.560)),elbow,
            elbow.lerp(cuff_center,.54)+Vector((-.012,-.018,-.006)),cuff_center]
    sleeve=sleeve_tube(p+"holding-sleeve",points,[.123,.132,.129,.120,.092],sleeve_mat,actor)
    rim_at(p+"holding-cuff",points[-2],points[-1],.089,sleeve_mat,actor)
    palm=base.globe(p+"holding-hand",palm_center,(.103,.095,.108),base.skin,actor)
    palm.rotation_euler.y=-.16
    # Deliberately small thumb, near the side of the object, leaving its icon clear.
    thumb_pos=grip+Vector((.008,-.028,.017))
    thumb=base.globe(p+"holding-thumb",thumb_pos,(.043,.049,.056),base.skin,actor)
    thumb.rotation_euler.y=.34
    pair("raised shoulder",torso,sleeve,shoulder)
    pair("raised wrist",sleeve,palm,cuff_center)
    pair("grip",palm,held,grip)
    pair("thumb",palm,thumb,thumb_pos)
    shoulder=Vector((.312,-.008,.683))
    elbow=Vector((.440,-.024,.468))
    cuff=Vector((.430,-.099,.297 if role not in (3,5) else .311))
    other=sleeve_tube(p+"relaxed-sleeve",[shoulder,(.387,-.010,.599),elbow,(.449,-.062,.363),cuff],
                      [.123,.130,.122,.112,.088],sleeve_mat,actor)
    rim_at(p+"relaxed-cuff",elbow,cuff,.084,sleeve_mat,actor)
    other_hand=base.globe(p+"relaxed-hand",cuff+Vector((-.012,-.022,-.039)),(.084,.078,.087),base.skin,actor)
    pair("relaxed shoulder",torso,other,shoulder);pair("relaxed wrist",other,other_hand,cuff)
    actor["body_contact_manifest"]=json.dumps(checks,ensure_ascii=False)
    return actor


def verify_body_contacts(actor):
    """Intersect the *evaluated* surfaces in world coordinates after scene assembly."""
    deps=bpy.context.evaluated_depsgraph_get();deps.update()
    trees={}
    def evaluated_tree(name):
        if name not in trees:
            ob=bpy.data.objects[name].evaluated_get(deps); geo=ob.to_mesh()
            try:
                world=[ob.matrix_world@v.co for v in geo.vertices]
                faces=[tuple(poly.vertices) for poly in geo.polygons]
                trees[name]=BVHTree.FromPolygons(world,faces)
            finally:
                ob.to_mesh_clear()
        return trees[name]
    result=[]
    for joint in json.loads(actor["body_contact_manifest"]):
        a,b=(evaluated_tree(n) for n in joint["parts"])
        overlaps=len(a.overlap(b))
        if not overlaps:
            raise ValueError(f"{actor.name}: separated {joint['joint']} {joint['parts']}")
        result.append({**joint,"intersecting_polygon_pairs":overlaps})
    return result
