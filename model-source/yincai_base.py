"""Materials, geometry, teacher sculpts, studio and GLB export used by create_cast.py."""
import math
from math import sin, cos, pi, sqrt
import bpy
from mathutils import Vector

s = bpy.context.scene
bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

def material(name, color, roughness=.55, metal=0):
    def linear(v):
        v = int(v, 16)/255
        return v/12.92 if v <= .04045 else ((v+.055)/1.055)**2.4
    rgb = tuple(linear(color[i:i+2]) for i in (0,2,4))
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb,1)
    m.use_nodes=True
    bs=m.node_tree.nodes['Principled BSDF']
    bs.inputs['Base Color'].default_value=(*rgb,1)
    bs.inputs['Roughness'].default_value=roughness
    bs.inputs['Metallic'].default_value=metal
    return m

ivory=material('陶 · 象牙','F3F0E8')
floor=material('台面亚麻灰','DCDDD4')
sand=material('磨砂石边','C6C7BD')
paper=material('档案纸','F7F5ED',.85)
edge=material('纸张切口','D6D5C8',.86)
navy=material('墨蓝釉','23354A',.36)
ink=material('印刷墨','2D3A43',.68)
rule=material('石墨灰','A3AAA6',.75)
slate=material('灰蓝釉','859C9F',.37)
pale=material('浅青灰','BDC9C3')
skin=material('米色素胎','F5C6AA',.61)
hair_brown=material('栗色陶釉','56332D',.45)
hair_ink=material('墨色陶釉','24262A',.44)
hair_producer=material('褐黑陶釉','32252A',.45)
silver=material('银灰发','B9B0BA',.55)
plum=material('低饱和紫釉','865FA3',.5)
bronze=material('熏灰金属','5F6563',.33,.58)
white=material('纸白衬衣','E9E8D9')
clay=material('暖灰陶','B6A693')
blush=material('浅肉桂素胎','EEA297')
baseblue=material('书布 · 石蓝','647D84',.79)
denim=material('靛青教员制服','445A71')

def empty(name,loc=(0,0,0),parent=None):
    ob=bpy.data.objects.new(name,None);s.collection.objects.link(ob);ob.parent=parent;ob.location=loc
    return ob

def finish(ob,name,mat,parent=None):
    ob.name=name
    ob.parent=parent
    ob.data.materials.append(mat)
    return ob

def block(name,xyz,dims,mat,r=.03,parent=None):
    bpy.ops.mesh.primitive_cube_add(size=1)
    ob=bpy.context.object
    for v in ob.data.vertices:
        for i,d in enumerate(dims): v.co[i]*=d
    finish(ob,name,mat,parent)
    ob.location=xyz
    if r:
        mod=ob.modifiers.new('圆角','BEVEL');mod.width=r;mod.segments=4
        norm=ob.modifiers.new('面法线','WEIGHTED_NORMAL')
    return ob

def globe(name,xyz,dims,mat,parent=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=32,ring_count=18,radius=1)
    ob=finish(bpy.context.object,name,mat,parent);ob.location=xyz;ob.scale=dims
    for p in ob.data.polygons:p.use_smooth=True
    return ob

def cyl(name,xyz,radius,thick,mat,parent=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=56,radius=radius,depth=thick)
    ob=finish(bpy.context.object,name,mat,parent);ob.location=xyz
    mod=ob.modifiers.new('车削边缘','BEVEL');mod.width=min(.035,thick*.25);mod.segments=4
    ob.modifiers.new('面法线','WEIGHTED_NORMAL')
    return ob

def line(name,points,rad,mat,parent=None,closed=False):
    cv=bpy.data.curves.new(name,'CURVE');cv.dimensions='3D';cv.resolution_u=5;cv.bevel_depth=rad;cv.bevel_resolution=2
    spl=cv.splines.new('BEZIER');spl.bezier_points.add(len(points)-1)
    for p,co in zip(spl.bezier_points,points):
        p.co=co;p.handle_left_type=p.handle_right_type='AUTO'
    spl.use_cyclic_u=closed
    ob=bpy.data.objects.new(name,cv);s.collection.objects.link(ob)
    return finish(ob,name,mat,parent)

def mesh(name,verts,faces,mat,parent=None,smooth=False):
    data=bpy.data.meshes.new(name);data.from_pydata(verts,[],faces);data.update()
    ob=bpy.data.objects.new(name,data);s.collection.objects.link(ob);finish(ob,name,mat,parent)
    if smooth:
        for p in ob.data.polygons:p.use_smooth=True
    return ob

def profile(name,rings,mat,parent):
    n=40;vv=[];ff=[]
    for z,rx,ry in rings:
        for i in range(n):
            a=2*pi*i/n;vv.append((rx*cos(a),ry*sin(a),z))
    for j in range(len(rings)-1):
        for i in range(n):ff.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
    ff+=[tuple(reversed(range(n))),tuple(range((len(rings)-1)*n,len(rings)*n))]
    return mesh(name,vv,ff,mat,parent,True)

def oval_line(name,center,rx,rz,mat,parent,rad=.02):
    x,y,z=center
    return line(name,[(x+rx*cos(2*pi*i/24),y,z+rz*sin(2*pi*i/24)) for i in range(24)],rad,mat,parent,True)

def tile(name,verts,mat,parent):
    ob=mesh(name,verts,[tuple(range(len(verts)))],mat,parent)
    m=ob.modifiers.new('布面厚度','SOLIDIFY');m.thickness=.017
    m=ob.modifiers.new('布料卷边','BEVEL');m.width=.018;m.segments=3
    return ob

ROLE_NAMES=('学情分析师','学科专家','教学设计师','多模态制作人','核查员','教师助理')

# Warm ceramic glaze sampled by eye from the six approved project portraits.
lavender=material('浅灰紫连帽衫','ADA3B7',.70)
violetwire=material('紫灰眼镜','927A9C',.42,.15)
walnut=material('深棕马甲','533F34',.74)
expert_sleeve=material('米白衬衣袖','E7D7BD',.71)
cream=material('奶油白衬衫','F7E8D6',.68)
hood_black=material('石墨黑连帽衫','302932',.67)
wine=material('酒棕夹克','583941',.68)
periwinkle=material('蓝紫制服','676C9F',.70)
pine=material('松叶绿书封','42523E',.66)
rust=material('珊瑚红检视记号','B85750',.54)
stamp=material('图标陶棕','9E6647',.52)
chartblue=material('色柱 · 湖蓝','7594BF')
chartviolet=material('色柱 · 紫','9A86AD')
chartred=material('色柱 · 珊瑚','D98783')
notecard=material('草图纸面','F1D69C')
blackeye=material('直瞳','241F22',.54)

def padded_lock(name,points,radii,hair,parent):
    curve=line(name,points,1.0,hair,parent)
    for point,radius in zip(curve.data.splines[0].bezier_points,radii):
        point.radius=radius
    curve.data.use_fill_caps=True
    return curve

def long_panel(name,cap,a,width,height,sweep,mat,parent):
    verts=[];faces=[];count=17;edge=10
    def center(t):return Vector(cap(a+sweep*max(0.,1-t)**1.2,t+.004))
    for j in range(count):
        t=.11+j/(count-1)*.918
        c=center(t);n=Vector((c.x/(.52**2),(c.y+.005)/(.46**2),(c.z-1.41)/(.584**2))).normalized()
        tangent=(center(t+.001)-center(t-.001)).normalized();side=tangent.cross(n).normalized()
        taper=(max(.03,sin(pi*j/(count-1)))**.56) if j not in (0,count-1) else .03
        for k in range(edge):
            angle=2*pi*k/edge
            verts.append(c+side*(sin(angle)*width*taper)+n*(cos(angle)*height*taper-.005))
    for j in range(count-1):
        for i in range(edge):faces.append((j*edge+i,j*edge+(i+1)%edge,(j+1)*edge+(i+1)%edge,(j+1)*edge+i))
    return mesh(name,verts,faces,mat,parent,True)

def cast(role,parent,loc,scale,turn):
    actor=empty(ROLE_NAMES[role],loc,parent);actor.rotation_euler.z=turn;actor.scale=(scale,)*3
    hair=[hair_ink,silver,hair_brown,hair_producer,hair_brown,hair_ink][role]
    coat=[lavender,walnut,cream,hood_black,wine,periwinkle][role]
    profile('双肩与上衣',[(.185,.47,.32),(.22,.54,.35),(.42,.57,.36),(.65,.52,.31),(.82,.40,.26),(.89,.20,.205)],coat,actor)
    globe('领口',(0,-.015,.90),(.19,.17,.19),skin,actor)
    if role not in (0,3):tile('衬衣领心',[(-.17,-.176,.885),(0,-.322,.495),(.17,-.176,.885)],white,actor)
    for sg in (-1,1):
        if role not in (0,3):tile('翻领',[(sg*.16,-.19,.89),(sg*.315,-.235,.789),(sg*.245,-.286,.70),(sg*.275,-.27,.685),(0,-.332,.47)],cream if role in (1,2,5) else wine,actor)
    # Face is a single subtly oval ceramic volume. Eyes follow its projected surface.
    # All facial parts below share one head pivot.
    cx,cy,cz=0,-.018,1.41
    rx,ry,rz=.49,.415,.53
    globe('手塑面部',(cx,cy,cz),(rx,ry,rz),skin,actor)
    for sg in (-1,1):
        globe('耳廓',(sg*.465,-.006,1.38),(.085,.065,.107),skin,actor)
        ex,ez=sg*.173,1.446
        ey=cy-ry*sqrt(1-(ex/rx)**2-((ez-cz)/rz)**2)
        eye=globe('墨釉眼睛',(ex,ey-.006,ez),(.040,.020,.083),blackeye,actor);eye.rotation_euler.y=-.15
    ey=cy-ry*sqrt(1-((1.365-cz)/rz)**2)
    for sg in (-1,1):
        x=sg*.287;z=1.333
        y=cy-ry*sqrt(1-(x/rx)**2-((z-cz)/rz)**2)
        cheek=globe('陶粉腮红',(x,y-.003,z),(.071,.012,.054),blush,actor)
        cheek.rotation_euler.z=sg*.55
    # A continuous cap with a swept hairline. Length and part vary by character.
    n,m=60,16;vv=[];ff=[]
    def cap(a,t,extra=0):
        front=max(0.,-sin(a))
        wave=.11*sin(2*a+.4+role*.18)
        limit=2.15-1.15*front**2 + .21*front*sin(3*a+1.55) +wave
        if role in [0,4]:limit+=.28*(1-front)
        if role==0:limit-=.19*front**1.8
        if role==1:limit=1.72-.70*front**1.3+.065*sin(2*a+.4)
        if role==5:limit-=.12*front**1.6
        phi=.003+(limit-.003)*t
        return ((rx+.042+extra)*sin(phi)*cos(a),(ry+.047+extra)*sin(phi)*sin(a)+cy+.012,cz+(rz+.051+extra)*cos(phi))
    for j in range(m+1):
        for i in range(n):vv.append(cap(i*2*pi/n,j/m))
    for j in range(m):
        for i in range(n):ff.append((j*n+i,(j+1)*n+i,(j+1)*n+(i+1)%n,j*n+(i+1)%n))
    shell=mesh('整体发壳',vv,ff,hair,actor,True)
    shell.modifiers.new('发梢厚度','SOLIDIFY').thickness=.03
    for idx,a in enumerate((-3.03,-2.62,-2.25,-1.96,-.87,-.47,.02,.58,1.18,1.82)):
        long_panel('蓬松造型发束',cap,a,.102 if idx in (2,3) else .083,.032 if role!=1 else .041,.88 if idx<4 else -.38,hair,actor)
    if role==3:
        long_panel('紫色挑染',cap,-2.23,.055,.051,.88,plum,actor)
    if role==1:
        for sg,sz in ((-1,1), (1,.84)):
            padded_lock('银灰侧梳发',[(sg*.04,-.13,1.946),(sg*.236,-.15,1.894),(sg*.387,-.18,1.78),(sg*.474,-.104,1.695),(sg*.499,-.051,1.711)],
                        [.01,.076*sz,.085*sz,.060*sz,.009],silver,actor)
    if role==5:
        padded_lock('倾斜侧分刘海',[(.167,-.10,1.929),(-.035,-.254,1.906),(-.227,-.314,1.815),(-.366,-.297,1.685),(-.465,-.190,1.60)],
                    [.010,.071,.094,.069,.008],hair,actor)
    if role in (2,3):
        bun=globe('盘发',(-.27,.23,1.88),(.275,.245,.24),hair,actor)
        for f in (.05,.16):
            oval_line('盘发缕',(-.27+f,.13,1.88),.12,.16,hair,actor,.011)
    if role==3:
        line('耳机头带',[(.49*cos(i*pi/18),.055,1.47+.53*sin(i*pi/18)) for i in range(19)],.040,navy,actor)
        for sg in (-1,1):
            globe('耳机外罩',(sg*.515,-.013,1.38),(.092,.131,.181),hood_black,actor)
    if role==2:
        for x,y,z,r in [(-.28,.18,1.92,.18),(-.38,.06,1.83,.17),(-.46,.04,1.66,.149),(.28,.15,1.86,.154),(.45,.03,1.73,.143)]:
            globe('栗色饱满发卷',(x,y,z),(r,r*.85,r*.90),hair,actor)
        for sg in (-1,1):
            curl=[(sg*.055,-.27,1.86),(sg*.22,-.34,1.90),(sg*.36,-.35,1.78),(sg*.43,-.27,1.69),(sg*.49,-.17,1.71)]
            padded_lock('波浪额发',curl,[.034,.123,.095,.080,.008],hair,actor)
        line('顶卷',[(.06,.19,1.95),(.02,.19,2.09),(-.09,.18,2.11),(-.15,.16,2.045)],.050,hair,actor)
    if role==4:
        line('发夹',[(.442,-.228,1.55),(.475,-.173,1.62)],.036,rust,actor)
        for sg in (-1,1):globe('耳珠',(sg*.458,-.079,1.322),(.037,.032,.037),ivory,actor)
        pony=globe('低马尾',(.48,.20,1.11),(.22,.18,.35),hair,actor);pony.rotation_euler.y=-.30
    if role==5:
        line('顶翘',[(0,.08,1.91),(.05,.11,2.03),(.13,.12,1.98)],.042,hair,actor)
    if role in (0,1):
        for sg in (-1,1):
            if role==0:
                oval_line('圆镜框',(sg*.192,-.422,1.454),.165,.162,violetwire,actor,.014)
            else:
                points=[]
                for i in range(32):
                    a=2*pi*i/32
                    x=math.copysign(abs(cos(a))**.43,cos(a))*.15
                    z=math.copysign(abs(sin(a))**.43,sin(a))*.112
                    points.append((sg*.182+x,-.418,1.45+z))
                line('方镜框',points,.018,ink,actor,True)
        if role==1:
            line('灰胡须',[(-.394,-.19,1.28),(-.323,-.270,1.15),(-.16,-.302,1.07),(0,-.302,1.06),(.16,-.302,1.07),(.323,-.27,1.15),(.394,-.19,1.28)],.066,silver,actor)
        line('鼻梁架',[(-.036,-.423,1.45),(0,-.437,1.47),(.036,-.423,1.45)],.015,bronze,actor)
        for sg in (-1,1):line('镜腿',[(sg*.327,-.416,1.46),(sg*.445,-.25,1.49),(sg*.469,-.05,1.47)],.014,bronze,actor)
    # Lift and enlarge the complete head assembly together, preserving glasses and face contact.
    facial_parts=[ob for ob in actor.children if ob.name.split('.')[0] not in ('双肩与上衣','领口','衬衣领心','翻领')]
    head=empty('Q版头部',(0,0,.885),actor)
    for part in facial_parts:
        part.parent=head;part.location.z-=.885
    head.scale=(1.26,1.23,1.20)
    if role in (0,3):
        padded_lock('柔软帽领',[(-.32,-.05,.790),(-.19,-.236,.845),(-.08,-.255,.755),(0,-.292,.702)], [.06,.108,.075,.029],coat,actor)
        padded_lock('柔软帽领',[(.32,-.05,.790),(.19,-.236,.845),(.08,-.255,.755),(0,-.292,.702)], [.06,.108,.075,.029],coat,actor)
        for sg in (-1,1):
            line('帽衫抽绳',[(sg*.062,-.307,.706),(sg*.070,-.338,.619),(sg*.076,-.346,.566)],.014,coat if role==3 else cream,actor)
    if role==1:
        tile('褐色领带',[(-.041,-.257,.812),(.041,-.257,.812),(.052,-.320,.660),(0,-.339,.600),(-.052,-.320,.660)],rust,actor)
    if role==5:
        line('工作证吊绳',[(-.13,-.24,.86),(0,-.34,.62),(.13,-.24,.86)],.015,navy,actor)
        block('工作证',(0,-.36,.555),(.17,.037,.115),ivory,.014,actor)
    # Small object and hand share the same coordinate frame; the hand meets the handle.
    def sleeve(label,shoulder,wrist):
        start,end=Vector(shoulder),Vector(wrist)
        axis=end-start
        sleeve=globe(label,(start+end)/2,(.124,.125,axis.length/2+.04),expert_sleeve if role==1 else coat,actor)
        sleeve.rotation_euler=axis.to_track_quat('Z','Y').to_euler()
    grip=(-.31,-.335,.60)
    sleeve('执物袖',(-.43,-.075,.68),grip)
    other=(.42,-.205,.392) if role!=5 else (.59,-.24,.61)
    sleeve('另一只衣袖',(.408,-.026,.676),other)
    globe('另一只手',other,(.102,.081,.097),skin,actor)
    prop=empty('辨识物',grip,actor)
    globe('持物手',(0,0,-.012),(.11,.09,.10),skin,prop)
    if role==4:
        line('镜柄',[(.0,-.075,-.05),(.095,-.085,.19)],.037,navy,prop)
        oval_line('放大镜',(.16,-.09,.30),.153,.153,navy,prop,.035)
        oval_line('放大镜瓷沿',(.16,-.104,.30),.135,.135,ivory,prop,.013)
    else:
        board=empty('随身物件',(0,-.075,.15),prop);board.rotation_euler.y=-.10
        block('白瓷牌',(0,0,0),(.36,.064,.243),pine if role==1 else notecard if role==2 else ivory,.039,board)
        if role==3:
            tile('播放符号',[(-.053,-.039,-.069),(.07,-.039,0),(-.053,-.039,.069)],navy,board)
        elif role==5:
            for k in (-.075,0,.075):globe('对话点',(k,-.035,.006),(.022,.012,.019),navy,board)
            tile('对话尾角',[(-.10,-.01,-.09),(-.045,-.01,-.09),(-.105,-.01,-.175)],ivory,board)
        elif role==0:
            for k,h in enumerate((.065,.11,.15)):block('学情柱',(-.07+k*.07,-.038,-.075+h/2),(.041,.014,h),(chartblue,chartviolet,chartred)[k],.004,board)
        elif role==1:
            line('书页中缝',[(0,-.04,-.085),(0,-.04,.08)],.012,navy,board)
        else:
            line('设计图', [(-.12,-.04,-.058),(-.034,-.04,.032),(.014,-.04,.00),(.058,-.04,.042),(.116,-.04,-.058),(-.12,-.04,-.058)],.010,slate,board)
            oval_line('图中远日',(.061,-.041,.068),.021,.021,slate,board,.007)
    # A generic ceramic bell brooch matches the avatars' shared garment detail.
    bell=empty('陶铃别针',(.277,-.284,.630),actor)
    globe('铃顶环',(0,0,.071),(.016,.013,.025),stamp,bell)
    profile('陶铃',[(0,.061,.024),(.016,.059,.024),(.025,.044,.023),(.072,.026,.016)],stamp,bell)
    return actor


IDS=('analyst','expert','designer','producer','checker','assistant','teacher-female','teacher-male')
NAMES=(*ROLE_NAMES,'任课教师 · 女','任课教师 · 男')
pants=material('精纺深灰蓝','46555C',.64)
shoe=material('哑光深靛皮革','293543',.49)
terracotta=material('暖灰褐外套','927D72',.70)
hair_teacher=material('教师深黑棕发','393431',.5)
softrose=material('暖陶唇线','AA8073',.64)
coat_teacher=material('教师藏青呢','40576A',.66)
patina=material('低彩蓝绿封面','657F7D',.63)

def along(name,a,b,radius,material,parent):
    va,vb=Vector(a),Vector(b)
    ob=globe(name,(va+vb)/2,(radius,radius,(va-vb).length/2+min(radius*.35,.035)),material,parent)
    ob.rotation_euler=(vb-va).to_track_quat('Z','Y').to_euler()
    return ob

def pedestal(actor,radius):
    base=cyl('底座下盘',(0,0,.047),radius,.094,navy,actor)
    top=cyl('底座上面',(0,0,.109),radius*.96,.030,ivory,actor)
    return top.location.z+.015

def shoes_and_legs(actor,hips,leg_x,sole_z,leg_material,human=False):
    for sign in (-1,1):
        x=sign*leg_x
        leg=profile('裤腿',[(sole_z+.09,.116 if human else .132,.12),
                             (sole_z+.15,.128 if human else .144,.129),
                             (sole_z+.56*(hips-sole_z),.129 if human else .157,.141),
                             (hips-.10,.15 if human else .178,.166),(hips,.145 if human else .159,.17)],leg_material,actor)
        leg.location.x=x
        # The shoe sole is flat, with the bottom plane coincident with the pedestal.
        block('贴地鞋底',(x,-.048,sole_z+.025),(.256 if human else .287,.38,.05),shoe,.024,actor)
        globe('鞋帮',(x,-.064,sole_z+.082),(.13 if human else .144,.19,.077),shoe,actor)
        line('鞋面弧线',[(x-.083,-.184,sole_z+.108),(x,-.199,sole_z+.140),(x+.083,-.184,sole_z+.108)],.008,bronze,actor)
    profile('裤腰及髋部',[(hips-.19,leg_x+.11,.175),(hips-.095,leg_x+.16,.210),(hips+.024,leg_x+.135,.21)],leg_material,actor)

def make_agent(index):
    root=empty(IDS[index]); upper=cast(index,root,(0,0,.51),1,0)
    upper.name='上半身与手持工具'
    sole_z=pedestal(root,.64)
    shoes_and_legs(root,.773,.19,sole_z,pants if index not in (1,2) else hair_brown)
    coat=[pale,clay,ivory,navy,slate,denim][index]

    if index==1:
        # A real book has a spine, paper block and a second cover on its reverse side.
        held=next(ob for ob in upper.children_recursive if ob.name.startswith('随身物件'))
        block('书脊',(-.172,.002,0),(.050,.082,.244),pine,.013,held)
        block('书页',(0,.045,0),(.324,.047,.214),paper,.008,held)
        block('封底',(0,.077,0),(.356,.025,.242),pine,.012,held)
    if index==4:
        held=next(ob for ob in upper.children_recursive if ob.name.startswith('辨识物'))
        # Skin and object remain separate; the tick is raised inside the ceramic inspection lens.
        globe('磨砂检视镜片',(.16,-.09,.30),(.136,.025,.136),ivory,held)
        line('核查勾',[(.075,-.116,.298),(.142,-.117,.244),(.240,-.116,.355)],.020,rust,held)
    return root

def teacher_hair(parent,female):
    hair=hair_teacher
    n,m=48,14;vv=[];ff=[]
    def surf(a,t):
        front=max(0,-sin(a))
        bound=(2.155 if female else 1.82)-(.99 if female else .78)*front**1.7+.12*front*sin(3*a+1)
        if female:bound+=.14*cos(a)
        phi=.004+(bound-.004)*t
        return (.323*sin(phi)*cos(a),-.015+.276*sin(phi)*sin(a),2.703+.396*cos(phi))
    for j in range(m+1):
        for i in range(n):vv.append(surf(2*pi*i/n,j/m))
    for j in range(m):
        for i in range(n):ff.append((j*n+i,(j+1)*n+i,(j+1)*n+(i+1)%n,j*n+(i+1)%n))
    cap=mesh('教师整体发型',vv,ff,hair,parent,True)
    cap.modifiers.new('发缘厚度','SOLIDIFY').thickness=.022
    for a in (-2.68,-2.24,-1.93,-.85,-.46,.09,.67):
        line('梳理发束',[surf(a+.42*(1-t),t) for t in (.16,.28,.43,.58,.72,.88,.97)],.009,hair,parent)
    if female:
        globe('低束发髻',(.204,.150,2.497),(.163,.141,.175),hair,parent)
        sweep=globe('面侧长发',(.229,-.073,2.658),(.074,.129,.215),hair,parent)
        sweep.rotation_euler.y=-.15
        for k in (-1,1):
            line('侧发束',[(k*.182,-.19,2.909),(k*.259,-.137,2.785),(k*.272,-.092,2.653)],.022,hair,parent)
        line('哑釉发卡',[(.217,-.151,2.90),(.235,-.104,2.925)],.012,slate,parent)
    else:
        line('短发上缘',[(-.194,-.099,3.005),(-.078,-.122,3.072),(.049,-.095,3.093),(.14,-.10,3.072)],.028,hair,parent)

def make_teacher(female):
    actor=empty('teacher-female' if female else 'teacher-male')
    sole_z=pedestal(actor,.64)
    shoes_and_legs(actor,1.386,.164,sole_z,pants,True)
    coat=terracotta if female else coat_teacher
    width=.426 if female else .448
    profile('教员外套',[(1.215,.353,.225),(1.255,.383,.242),(1.44,.364,.240),(1.64,.342,.216),
                         (1.92,.395,.240),(2.087,width,.229),(2.185,.337,.174),(2.247,.17,.133)],coat,actor)
    profile('教师颈部',[(2.176,.126,.116),(2.338,.128,.114),(2.41,.148,.128)],skin,actor)
    # The shirt follows the changing depth of the jacket front from the collar to the lower V.
    levels=[(2.235,.132,-.165),(2.17,.125,-.212),(2.09,.112,-.239),(1.995,.09,-.252),(1.902,.055,-.251),(1.815,.026,-.247)]
    verts=[(sign*extent,y,z) for z,extent,y in levels for sign in (-1,1)]
    mesh('教师衬衫前片',verts,[(n,n+1,n+3,n+2) for n in range(0,len(verts)-2,2)],white,actor)
    if not female:
        tile('教师窄领带',[(-.032,-.218,2.169),(.032,-.218,2.169),(.038,-.252,2.013),
                          (.010,-.258,1.866),(-.035,-.250,2.013)],navy,actor)
        for sg in (-1,1):
            tile('衬衫翻领',[(sg*.132,-.17,2.235),(.0,-.191,2.211),(sg*.063,-.237,2.105),(sg*.132,-.215,2.182)],ivory,actor)
    else:
        line('圆领滚边',[(-.12,-.182,2.224),(-.065,-.202,2.194),(0,-.207,2.181),(.065,-.20,2.194),(.12,-.18,2.224)],.011,paper,actor)
    for sign in (-1,1):
        verts=[(sign*.145,-.147,2.237),(sign*.193,-.160,2.20),(sign*.291,-.177,2.104),
               (sign*.205,-.222,2.035),(sign*.242,-.211,2.008),(sign*.035,-.252,1.815),(sign*.117,-.241,2.084)]
        mesh('外套翻领',verts,[(0,1,6),(1,2,3,6),(3,4,5),(3,5,6)],clay if female else denim,actor)
    line('衣襟',[(.036,-.244,1.80),(.038,-.229,1.635),(.036,-.246,1.47),(.034,-.241,1.31)],.009,coat,actor)
    for z in (1.68,1.49):
        globe('衣扣',(.055,-.244,z),(.024,.013,.025),shoe,actor)
    face_rx=.27 if female else .299
    globe('成年面部',(0,-.018,2.68),(face_rx,.242,.370),skin,actor)
    for sign in (-1,1):
        globe('耳廓',(sign*(face_rx-.008),-.012,2.635),(.056,.038,.074),skin,actor)
        x=sign*.116;z=2.683
        y=-.018-.242*sqrt(1-(x/face_rx)**2-((z-2.68)/.37)**2)
        globe('墨釉眼睛',(x,y-.004,z),(.028,.017,.036),ink,actor)
        line('眉弧',[(sign*.06,-.258,2.763),(sign*.12,-.235,2.772),(sign*.174,-.20,2.757)],.014,hair_teacher,actor)
    globe('鼻梁',(0,-.245,2.625),(.033,.042,.059),skin,actor)
    line('嘴角',[(-.065,-.238,2.54),(0,-.250,2.530),(.065,-.238,2.545)],.009,softrose,actor)
    teacher_hair(actor,female)
    # Both teacher variants hold the same teaching tools and share their physical dimensions.
    left_wrist=(-.294,-.31,1.585);right_wrist=(.386,-.302,1.755)
    for side,shoulder,elbow,wrist in [('左',(-.369,0,2.086),(-.486,-.08,1.738),left_wrist),
                                    ('右',(.369,0,2.086),(.473,-.084,1.776),right_wrist)]:
        along(side+'上袖',shoulder,elbow,.121,coat,actor)
        along(side+'下袖',elbow,wrist,.107,coat,actor)
        globe(side+'手',wrist,(.082,.078,.093),skin,actor)
    folio=empty('教师用教案夹',left_wrist,actor);folio.rotation_euler.y=-.10;folio.rotation_euler.z=-.08
    block('纸张',(.043,-.040,.106),(.325,.057,.466),paper,.015,folio)
    for yy in (-.081,-.003):
        block('布面书封',(.040,yy,.107),(.358,.029,.493),patina,.021,folio)
    block('书脊',(-.125,-.042,.107),(.035,.096,.487),patina,.016,folio)
    line('封面双线',[(.047,-.101,.226),(.151,-.101,.226)],.008,paper,folio)
    line('封面短线',[(.078,-.101,.181),(.151,-.101,.181)],.006,paper,folio)
    pen=empty('教师用书写笔',right_wrist,actor)
    along('笔杆',(-.018,-.049,-.096),(.08,-.042,.212),.017,navy,pen)
    along('笔夹',(.066,-.057,.181),(.058,-.062,.103),.008,bronze,pen)
    along('笔锋',(-.018,-.049,-.096),(-.031,-.052,-.14),.009,bronze,pen)
    # Adult cues (teaching folio, collar, eyebrows, pen) remain while the figure uses a Q-style head ratio.
    body=empty('成人Q版衣身',(0,0,sole_z),actor)
    head=empty('成人Q版头部',(0,0,sole_z+(2.33-sole_z)*.82),actor)
    facial_names=('成年面部','耳廓','墨釉眼睛','眉弧','鼻梁','嘴角','教师整体发型','梳理发束','低束发髻','面侧长发','侧发束','哑釉发卡','短发上缘')
    for part in list(actor.children):
        if part in (body,head) or part.name.startswith('底座'):continue
        if part.name.split('.')[0] in facial_names:
            part.parent=head;part.location.z-=2.33
        else:
            part.parent=body;part.location.z-=sole_z
    body.scale.z=.82;head.scale=(1.52,1.50,1.48)
    return actor

def move_to_collection(root,collection):
    for ob in (root,*root.children_recursive):
        for old in list(ob.users_collection):old.objects.unlink(ob)
        collection.objects.link(ob)

def add_light(name,loc,power,size,color):
    bpy.ops.object.light_add(type='AREA',location=loc);ob=bpy.context.object
    ob.name=name;ob.data.energy=power;ob.data.size=size;ob.data.color=color
    ob.rotation_euler=(Vector((0,0,1.5))-ob.location).to_track_quat('-Z','Y').to_euler()
    for co in list(ob.users_collection):co.objects.unlink(ob)
    s.collection.objects.link(ob)
    return ob

def configure_camera(cam,overview=False):
    if overview:
        cam.location=(5,-13,7);target=(0,0,1.0);cam.data.ortho_scale=11.2
    else:
        cam.location=(1.30,-8.4,3.54);target=(0,0,1.51);cam.data.ortho_scale=3.40
    cam.rotation_euler=(Vector(target)-cam.location).to_track_quat('-Z','Y').to_euler()

def studio():
    bpy.ops.object.camera_add();cam=bpy.context.object;cam.name='正交人物摄影机';cam.data.type='ORTHO';s.camera=cam
    for co in list(cam.users_collection):co.objects.unlink(cam)
    s.collection.objects.link(cam)
    add_light('左上柔光',(-3.8,-4.5,6.5),530,4,(1,.94,.87))
    add_light('补光',(3.8,-3.3,3.0),150,3.5,(.87,.92,1))
    add_light('柔边光',(2.2,2.5,5.8),510,3.2,(1,.96,.89))
    s.world.use_nodes=True;s.world.node_tree.nodes['Background'].inputs[0].default_value=(.73,.76,.80,1)
    s.world.node_tree.nodes['Background'].inputs[1].default_value=.37
    s.render.use_stamp_filename = False
    s.render.engine='CYCLES';s.cycles.samples=18;s.cycles.use_denoising=True;s.cycles.max_bounces=4
    s.render.threads_mode='FIXED';s.render.threads=7;s.render.film_transparent=True
    s.render.resolution_x=800;s.render.resolution_y=920;s.render.resolution_percentage=100
    s.render.image_settings.file_format='PNG';s.render.image_settings.color_mode='RGBA';s.render.image_settings.color_depth='8'
    s.view_settings.view_transform='AgX';s.view_settings.look='AgX - Medium High Contrast'
    return cam

def export_joined(root,file):
    """The editable objects stay in .blend. Bake transforms and modifiers to one indexed mesh per GLB."""
    deps=bpy.context.evaluated_depsgraph_get()
    result_mesh=bpy.data.meshes.new(root.name+'-mesh')
    result=bpy.data.objects.new(root.name+'-web',result_mesh);s.collection.objects.link(result)
    copies=[]
    for source in root.children_recursive:
        if source.type not in ('MESH','CURVE'):continue
        ev=source.evaluated_get(deps)
        data=bpy.data.meshes.new_from_object(ev,depsgraph=deps)
        dup=bpy.data.objects.new('export-part',data);s.collection.objects.link(dup);dup.matrix_world=ev.matrix_world.copy()
        copies.append(dup)
    bpy.ops.object.select_all(action='DESELECT')
    for part in copies:part.select_set(True)
    result.select_set(True);bpy.context.view_layer.objects.active=result
    bpy.ops.object.join()
    bpy.ops.export_scene.gltf(filepath=str(file),export_format='GLB',use_selection=True,export_yup=True,export_apply=True,
                              export_texcoords=False,export_normals=True,export_tangents=False,export_cameras=False,
                              export_lights=False,export_animations=False,export_skins=False,export_morph=False,
                              export_attributes=False)
    bpy.data.objects.remove(result,do_unlink=True)
    # Export did not alter the editable scene hierarchy. Release temporary buffers before the next role.
    bpy.data.orphans_purge(do_recursive=True)

def validate_contacts(root):
    bpy.context.view_layer.update()
    def geom_z(obj):
        zs=[(obj.matrix_world@Vector(vertex)).z for vertex in obj.bound_box]
        return min(zs),max(zs)
    top=next(ob for ob in root.children_recursive if ob.name.startswith('底座上面'))
    shoes=[ob for ob in root.children_recursive if ob.name.startswith('贴地鞋底')]
    assert len(shoes)==2
    distances=[abs(geom_z(foot)[0]-geom_z(top)[1]) for foot in shoes]
    assert max(distances)<2e-5
    return distances
