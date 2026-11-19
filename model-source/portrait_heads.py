"""Original, editable portrait sculpts for the six reference avatars. Local front is Blender -Y."""
from math import sin, cos, pi, sqrt, copysign, radians
from mathutils import Vector
from yincai_base import empty, globe, mesh, line, material

# Facial profile: (height, half width, half depth, depth offset). Keep the lower cheeks broad.
FACE = (
    (-.571,.006,.004,-.085),(-.555,.145,.135,-.083),(-.519,.312,.212,-.072),
    (-.461,.454,.302,-.054),(-.374,.546,.383,-.029),(-.244,.594,.429,-.016),
    (-.101,.613,.451,-.005),(.081,.610,.452,.001),(.237,.586,.434,.012),
    (.379,.515,.382,.025),(.491,.368,.294,.039),(.552,.201,.165,.047),(.581,.006,.012,.049)
)
COLOR = {}
def pigment(name,hex_value,rough=.88):
    if name not in COLOR:
        m=material(name,hex_value,rough)
        bs=m.node_tree.nodes.get('Principled BSDF')
        bs.inputs['Specular IOR Level'].default_value=.13
        COLOR[name]=m
    return COLOR[name]

def clamp(v,lo,hi):return max(lo,min(v,hi))

def cubic(a,b,c,d,t):
    """Catmull-Rom interpolation between inner controls; duplicates clamp the two endpoints."""
    return .5*((2*b)+(-a+c)*t+(2*a-5*b+4*c-d)*t*t+(-a+3*b-3*c+d)*t*t*t)

def samples(points,subdivisions):
    p=[Vector(x) for x in points]
    for i in range(len(p)-1):
        for j in range(subdivisions):
            yield cubic(p[max(0,i-1)],p[i],p[i+1],p[min(len(p)-1,i+2)],j/subdivisions)
    yield p[-1]

def ring_value(z,rows=FACE):
    if z<rows[0][0]:return rows[0][1:]
    for i in range(len(rows)-1):
        a,b=rows[i],rows[i+1]
        if z<=b[0]:
            u=(z-a[0])/(b[0]-a[0]);prev=rows[max(0,i-1)];nxt=rows[min(i+2,len(rows)-1)]
            # z-aware tangent avoids a crease where the cheek rings are closer to the chin.
            return tuple((2*u**3-3*u**2+1)*a[j]+(u**3-2*u**2+u)*(b[0]-a[0])*(b[j]-prev[j])/(b[0]-prev[0])
                         +(-2*u**3+3*u**2)*b[j]+(u**3-u**2)*(b[0]-a[0])*(nxt[j]-a[j])/(nxt[0]-a[0])
                         for j in (1,2,3))
    return rows[-1][1:]

def face_y(x,z):
    rx,ry,cy=ring_value(z)
    return cy-ry*(max(.001,1-(x/max(.001,rx))**2)**.43)

def face_shell(head,mat):
    n,m=64,48;v=[];f=[]
    for j in range(m+1):
        z=FACE[0][0]+(FACE[-1][0]-FACE[0][0])*(1-cos(pi*j/m))/2
        rx,ry,cy=ring_value(z)
        for i in range(n):
            a=2*pi*i/n
            v.append((rx*cos(a),cy+ry*copysign(abs(sin(a))**.86,sin(a)),z))
    for j in range(m):
        for i in range(n):f.append((j*n+i,j*n+(i+1)%n,(j+1)*n+(i+1)%n,(j+1)*n+i))
    f.extend([tuple(reversed(range(n))),tuple(range(m*n,(m+1)*n))])
    return mesh('手塑面部',v,f,mat,head,True)

def skin_patch(name,cx,cz,width,height,cap,relief,mat,head):
    """Project every vertex onto the face. The color patch follows the cheek, without a raised rim."""
    loop=[];r=width/2;half=height/2-r
    n=20
    if cap:
        for i in range(n+1):
            a=pi*i/n;loop.append((r*cos(a),half+r*sin(a)))
        for i in range(n+1):
            a=pi+pi*i/n;loop.append((r*cos(a),-half+r*sin(a)))
    else:
        loop=[(width*.5*cos(2*pi*i/40),height*.5*sin(2*pi*i/40)) for i in range(40)]
    points=[];faces=[];m=len(loop)
    # Coordinates are relative to the local object origin so eye direction can be verified from its transform.
    center=Vector((cx,face_y(cx,cz)-.0025,cz))
    for t in (.004,.26,.53,.77,.93,1.0):
        for ox,oz in loop:
            x,z=cx+ox*t,cz+oz*t
            points.append(Vector((x,face_y(x,z)-.0025-relief*(1-t*t),z))-center)
    for j in range(5):
        for k in range(m):faces.append((j*m+k,(j+1)*m+k,(j+1)*m+(k+1)%m,j*m+(k+1)%m))
    faces.append(tuple(range(m)))
    ob=mesh(name,points,faces,mat,head,True);ob.location=center
    return ob

def back_cap(head,role,hair):
    n,m=64,24;vv=[];ff=[]
    side=(2.40,1.77,2.05,2.04,2.11,1.85)[role]
    for j in range(m+1):
        for i in range(n):
            a=2*pi*i/n;front=max(0,-sin(a));back=max(0,sin(a))
            phi=.006+(side+(.16 if role!=0 else .10)*back-(side-(.89 if role!=1 else .75))*front**1.4-.006)*j/m
            vv.append((.712*sin(phi)*cos(a),.070+.532*sin(phi)*sin(a),.102+.586*cos(phi)))
    for j in range(m):
        for i in range(n):ff.append((j*n+i,(j+1)*n+i,(j+1)*n+(i+1)%n,j*n+(i+1)%n))
    cap=mesh('发型内层与后脑',vv,ff,hair,head,True)
    cap.modifiers.new('内侧厚度','SOLIDIFY').thickness=.025

def skull_front(x,z):
    return .063-.539*sqrt(max(.012,1-(x/.739)**2-((z-.103)/.610)**2))

def wave(name,path,mat,head,depth=-.025,thick=.10,highlight=False):
    """A broad swept lock. The convex front and back wrap around the skull at each cross section."""
    controls=list(samples(path,5));verts=[];faces=[];sections=16
    for i,q in enumerate(controls):
        x,z,w=q
        prev=controls[max(0,i-1)];after=controls[min(len(controls)-1,i+1)]
        dx,dz=after[0]-prev[0],after[1]-prev[1];mag=max(.001,sqrt(dx*dx+dz*dz))
        nx,nz=-dz/mag,dx/mag
        w=max(.002,w)
        thickness=min(thick,w*.79+.002)
        for j in range(sections):
            a=2*pi*j/sections;across=w*cos(a)
            px=x+nx*across;pz=z+nz*across
            y=skull_front(px,pz)+depth-thickness*sin(a)
            verts.append((px,y,pz))
    for i in range(len(controls)-1):
        for j in range(sections):
            faces.append((i*sections+j,i*sections+(j+1)%sections,(i+1)*sections+(j+1)%sections,(i+1)*sections+j))
    faces.extend([tuple(reversed(range(sections))),tuple(range((len(controls)-1)*sections,len(controls)*sections))])
    ob=mesh(name,verts,faces,mat,head,True)
    return ob

def cord(name,points,mat,head):
    """A spatial lock with tapered free tip and varied soft cross section."""
    ob=line(name,[p[:3] for p in points],1,mat,head)
    for point,p in zip(ob.data.splines[0].bezier_points,points):point.radius=max(.002,p[3])
    ob.data.use_fill_caps=True
    return ob

def glasses(head,expert,frame):
    z=-.105 if expert else -.111
    centers=(-.255,.255)
    for x in centers:
        pts=[]
        for i in range(40):
            a=2*pi*i/40
            if expert:
                xx=x+.183*copysign(abs(cos(a))**.42,cos(a));zz=z+.127*copysign(abs(sin(a))**.42,sin(a))
            else:
                xx=x+.188*cos(a);zz=z+.163*sin(a)
            pts.append((xx,face_y(xx,zz)-.026,zz))
        line('方镜框' if expert else '圆镜框',pts,.017 if expert else .0125,frame,head,True)
        side=-1 if x<0 else 1;ex=x+(.185 if expert else .188)*side
        line('眼镜侧梁',[(ex,face_y(ex,z)-.026,z),(side*.567,-.244,z+.047),(side*.624,-.086,z+.073)],.014,frame,head)
    l=centers[0]+(.183 if expert else .188);r=-l
    line('鼻梁架',[(l,face_y(l,z)-.025,z+.014),(0,face_y(0,z+.049)-.028,z+.049),(r,face_y(r,z)-.025,z+.014)],.014,frame,head)

def side_layers(head,hair,role):
    low=[-.42,-.16,-.23,-.34,-.36,-.22][role]
    for sign in (-1,1):
        wave('包侧短鬓' if role==5 else '鬓侧发尾',
             [(sign*.48,.41,.014),(sign*.62,.30,.070),(sign*.67,.14,.088),
              (sign*.68,-.004,.070),(sign*.631,low+.061,.040),(sign*.596,low,.004)],
             hair,head,.010,.069)
    if role==0:
        for sign in (-1,1):
            bob=globe('波波头外侧体积',(sign*.590,.114,-.047),(.157,.277,.343),hair,head)
            bob.rotation_euler.y=sign*.12
            wave('齐下颌波波发',[(sign*.51,.41,.018),(sign*.65,.20,.087),(sign*.707,-.005,.097),
                              (sign*.694,-.215,.093),(sign*.61,-.395,.060),(sign*.491,-.423,.004)],hair,head,.045,.075)

def parted(head,hair,role):
    # The left-facing end of each broad lock curls away from the face. These are solid sculpted forms.
    if role in (0,3,4):
        wave('顶侧发束',[(.105,.57,.014),(-.062,.638,.107),(-.29,.56,.126),(-.477,.42,.136),
                        (-.624,.314,.096),(-.683,.31,.040),(-.697,.333,.005)],hair,head,.028,.089)
        tip={0:(-.68,-.17),3:(-.626,-.375),4:(-.646,-.14)}[role]
        wave('额前大侧分',[(.103,.487,.028),(.013,.501,.104),(-.118,.417,.155),(-.275,.264,.162),
                        (-.452,.140,.146),(-.574,.069,.115),(tip[0],tip[1],.004)],hair,head,-.041,.096)
        wave('右侧分缝',[(.063,.50,.022),(.212,.477,.123),(.350,.377,.144),(.472,.257,.125),
                        (.605,.177,.096),(.682,.091,.050),(.67,-.03,.004)],hair,head,-.030,.082)
    else:
        wave('男生上层横向发浪',[(.113,.566,.015),(-.043,.620,.101),(-.272,.558,.127),
                           (-.462,.438,.126),(-.608,.376,.103),(-.687,.387,.061),(-.702,.439,.004)],hair,head,.025,.085)
        wave('男生宽扁左掠刘海',[(.102,.462,.025),(.001,.493,.114),(-.166,.411,.164),
                           (-.319,.259,.164),(-.484,.170,.146),(-.619,.135,.106),
                           (-.705,.141,.058),(-.719,.168,.004)],hair,head,-.060,.100)
        wave('男生短右分',[(.09,.452,.025),(.214,.462,.116),(.359,.367,.144),(.475,.254,.135),
                       (.593,.183,.111),(.68,.182,.073),(.715,.226,.004)],hair,head,-.048,.092)
        cord('顶部单翘',[(.113,.069,.610,.062),(.142,.046,.708,.074),(.112,.044,.774,.060),
                    (.052,.039,.807,.046),(-.042,.021,.801,.004)],hair,head)
        # These upper ears are visible below the short hair. No long side locks or ponytail.
        head['reference_landmark']='额前大分缝、左掠发尾、短鬓、双耳与顶部单翘'

def mature_hair(head,hair):
    for side,width in ((-1,1),(1,.78)):
        path=[(.095*side,.545,.010),(.247*side,.575,.077),(.414*side,.501,.093),(.521*side,.414,.092),
              (.623*side,.355,.076),(.680*side,.355,.039),(.691*side,.394,.004)]
        wave('银灰侧梳',[(x,z,w*width) for x,z,w in path],hair,head,-.026,.072)
        wave('短鬓侧卷',[(.458*side,.421,.012),(.585*side,.300,.063),(.653*side,.198,.066),
                    (.671*side,.096,.049),(.643*side,.03,.004)],hair,head,.005,.061)
    beard=pigment('短灰胡须','BBB2B6')
    for side in (-1,1):
        cord('贴颌短胡须',[(side*.565,-.149,-.246,.035),(side*.532,-.220,-.330,.053),
                       (side*.421,-.263,-.420,.064),(side*.295,-.263,-.468,.059),(side*.215,-.259,-.493,.036)],beard,head)
    chin=globe('下颌灰胡须',(0,-.274,-.486),(.276,.094,.080),beard,head)
    chin.rotation_euler.x=-.16

def curls(head,hair):
    # The large gathered curls belong behind the face, plus two deliberately separate S-shaped fringe clusters.
    for x,y,z,rx,ry,rz in ((-.28,.13,.566,.307,.239,.239),(-.434,.165,.446,.250,.217,.214),
                            (-.56,.137,.301,.175,.17,.172),(-.57,.12,.158,.148,.161,.135),
                            (.30,.17,.46,.205,.175,.160),(.52,.12,.32,.160,.155,.151)):
        globe('盘起的栗色卷发',(x,y,z),(rx,ry,rz),hair,head)
    cord('发顶卷环',[(-.20,.14,.64,.056),(-.16,.105,.795,.065),(-.045,.077,.836,.045),
                   (.036,.053,.756,.028),(.015,.045,.69,.003)],hair,head)
    # S-shaped layered coils have rounded ends and an open silhouette. Spatial controls
    # avoid a ribbon intersecting itself at the tight turn.
    cord('左侧卷起的刘海',[(.088,-.313,.439,.027),(-.014,-.347,.460,.087),(-.140,-.392,.414,.110),
                       (-.236,-.430,.283,.119),(-.307,-.459,.195,.108),(-.414,-.454,.174,.089),
                       (-.467,-.411,.217,.060),(-.456,-.382,.287,.008)],hair,head)
    cord('右侧翻卷',[(.050,-.321,.430,.028),(.158,-.347,.448,.093),(.290,-.385,.393,.115),
                 (.397,-.405,.266,.118),(.513,-.384,.201,.108),(.626,-.318,.225,.083),
                 (.669,-.260,.302,.047),(.657,-.220,.364,.005)],hair,head)
    cord('鬓边反卷',[(-.322,-.281,.412,.035),(-.450,-.300,.388,.082),(-.530,-.323,.292,.099),
                 (-.568,-.335,.193,.083),(-.629,-.291,.139,.059),(-.677,-.227,.163,.027)],hair,head)

def producer(head,hair):
    for x,y,z,rx,ry,rz in ((-.288,.16,.64,.295,.236,.211),(-.364,.17,.556,.222,.212,.173)):
        globe('深褐丸子头',(x,y,z),(rx,ry,rz),hair,head)
    cord('盘发外缘',[(-.409,.117,.51,.040),(-.566,.12,.579,.053),(-.528,.12,.727,.058),
                   (-.393,.117,.800,.05),(-.264,.09,.795,.006)],hair,head)
    purple=pigment('低饱和紫挑染','836297')
    wave('嵌入刘海的紫挑染',[(.018,.526,.003),(-.055,.486,.028),(-.152,.400,.043),
                        (-.269,.259,.047),(-.405,.146,.043),(-.521,.057,.029),(-.591,-.111,.006)],
         purple,head,-.144,.013)
    pads=pigment('哑光耳机','332B37')
    cord('耳机头带',[(.699*cos(i*pi/30),.037,.025+.671*sin(i*pi/30),.039) for i in range(31)],pads,head)
    for sign in (-1,1):
        ear=globe('耳机外罩',(sign*.681,-.014,-.038),(.101,.158,.190),pads,head)
        ear.rotation_euler.y=sign*.13

def inspector(head,hair):
    pony=globe('低马尾',(.525,.26,-.325),(.236,.19,.31),hair,head);pony.rotation_euler.y=-.45
    cord('低马尾外卷',[(.476,.18,-.115,.040),(.650,.18,-.230,.086),(.686,.18,-.391,.091),
                    (.605,.205,-.526,.056),(.535,.21,-.555,.008)],hair,head)
    clip=pigment('红发夹','B85C56')
    cord('侧边红发夹',[(.612,-.386,.046,.017),(.654,-.349,.115,.028),(.687,-.293,.178,.019)],clip,head)

def build_portrait(role,actor):
    """Add the complete, independent head under actor and return its anatomical pivot."""
    names=('analyst','expert','designer','producer','checker','assistant')
    if isinstance(role,str):role=names.index(role)
    head=empty('Q版头部',(0,-.015,1.459),actor)
    head.rotation_euler.y=radians((-8,-6,-9,-8,-8,-9.25)[role])
    # The undeformed pivot lies behind the cheek at mid-head height; the neck remains attached below.
    head['blender_front']='-Y';head['role_id']=names[role];head['tilt_degrees']=(-8,-6,-9,-8,-8,-9.25)[role]
    peach=pigment('嫩桃色脸','FFD0B4',.90)
    blush=pigment('脸颊浅珊瑚','F2A893',.93)
    eye=pigment('柔黑胶囊眼','272122',.88)
    hair=pigment(('柔黑短发','银灰发束','栗色卷发','低明度深褐发','酒栗低马尾','男生柔黑短发')[role],
                 ('29272C','CEC5C5','59372C','392B2D','654038','312B30')[role],.94)
    face_shell(head,peach)
    for sign in (-1,1):
        ear=globe('耳廓',(sign*.603,-.003,-.217),(.094,.113,.125),peach,head)
        ear.rotation_euler.y=sign*.21
        ex=sign*(.255 if role in (1,5) else .25)
        skin_patch('墨釉眼睛',ex,-.142,.090 if role!=1 else .078,.208 if role!=1 else .178,True,.013,eye,head)
        skin_patch('陶粉腮红',sign*.427,-.290,.149,.135,False,.001,blush,head)
        if role==4:globe('珍珠耳钉',(sign*.649,-.095,-.273),(.032,.030,.031),pigment('珍珠耳珠','F1E9DE'),head)
    back_cap(head,role,hair);side_layers(head,hair,role)
    if role==1:mature_hair(head,hair)
    elif role==2:curls(head,hair)
    else:parted(head,hair,role)
    if role==3:producer(head,hair)
    if role==4:inspector(head,hair)
    if role in (0,1):
        glasses(head,role==1,pigment('专家深方镜','493B36') if role==1 else pigment('分析师灰紫圆镜','987D99'))
    return head
