"""Measure default-camera geometric occlusion from every triangle of the shipped GLB."""
import struct,json,hashlib
from pathlib import Path
import numpy as np
import cv2
from numba import njit
import sys
from glb_io import unpack

SEATS = ('analyst', 'expert', 'designer', 'producer', 'checker', 'assistant')

@njit
def raster(xyz,indices,depth):
    h,w=depth.shape
    for row in indices:
        a,b,c=xyz[row[0]],xyz[row[1]],xyz[row[2]]
        bx,by=b[0]-a[0],b[1]-a[1];cx,cy=c[0]-a[0],c[1]-a[1]
        denom=bx*cy-by*cx
        if abs(denom)<1e-8:continue
        loX=max(0,int(np.ceil(min(a[0],b[0],c[0])-.5)))
        hiX=min(w-1,int(np.floor(max(a[0],b[0],c[0])-.5)))
        loY=max(0,int(np.ceil(min(a[1],b[1],c[1])-.5)))
        hiY=min(h-1,int(np.floor(max(a[1],b[1],c[1])-.5)))
        for y in range(loY,hiY+1):
            for x in range(loX,hiX+1):
                dx,dy=x+.5-a[0],y+.5-a[1]
                wa=(dx*cy-dy*cx)/denom;wb=(bx*dy-by*dx)/denom
                if min(wa,wb,1.-wa-wb)<-1.e-8:continue
                z=a[2]+wa*(b[2]-a[2])+wb*(c[2]-a[2])
                if z<depth[y,x]:depth[y,x]=z

def unit(v):return v/np.linalg.norm(v)
def compare(path,cam):
    gl,tail=unpack(path);body=tail[8:]
    def acc(index):
        a=gl['accessors'][index];bv=gl['bufferViews'][a['bufferView']]
        typ={5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']]
        components={'SCALAR':1,'VEC3':3}[a['type']]
        size=np.dtype(typ).itemsize
        return np.ndarray((a['count'],components),typ,body,a.get('byteOffset',0)+bv.get('byteOffset',0),
                          (bv.get('byteStride',size*components),size))
    eye=np.array(cam['eye']);target=np.array(cam['target'])
    direction=unit(target-eye);right=unit(np.cross(direction,[0.,1.,0.]));up=unit(np.cross(right,direction));basis=np.array([right,up,direction])
    w,h=cam['pixelWidth'],cam['pixelHeight']
    groups=list(SEATS)+['desk','folio']
    depths=np.full((len(groups),h,w),np.inf,dtype=np.float32)
    parts={
        'face_and_eyes': ('嫩桃色脸', '柔黑胶囊眼', '脸颊浅珊瑚'),
        'hands_and_role_prop': ('米色素胎','草图纸面','色柱','档案纸','绿书封','绿封面','检视记号','陶 · 象牙','直瞳')
    }
    detail_depths={part:np.full((len(SEATS),h,w),np.inf,dtype=np.float32) for part in parts}
    shoes={}; positions={};support={};raw_bounds={}
    for n in gl['nodes']:
        name=n['name'];role=name.removeprefix('agent-')
        group=role if role in SEATS else ('folio' if name.startswith('folio-') else 'desk')
        gi=groups.index(group)
        x,y,z,q=n.get('rotation',(0,0,0,1))
        rot=np.array([[1-2*(y*y+z*z),2*(x*y-z*q),2*(x*z+y*q)],
                      [2*(x*y+z*q),1-2*(x*x+z*z),2*(y*z-x*q)],[2*(x*z-y*q),2*(y*z+x*q),1-2*(x*x+y*y)]])
        worldset=[]
        for prim in gl['meshes'][n['mesh']]['primitives']:
            verts=acc(prim['attributes']['POSITION'])
            world=(verts*n.get('scale',[1,1,1]))@rot.T+n.get('translation',[0,0,0])
            worldset.append(world)
            projected=(world-target)@basis.T
            projected[:,0]=w*(.5+projected[:,0]/cam['width'])
            projected[:,1]=h*(.5-projected[:,1]/cam['height'])
            tris=np.ascontiguousarray(acc(prim['indices']).reshape((-1,3)).astype('int32'))
            raster(projected,tris,depths[gi])
            if group in SEATS:
                material=gl['materials'][prim['material']]['name']
                for part, matches in parts.items():
                    if any(label in material for label in matches):
                        raster(projected,tris,detail_depths[part][gi])
        coords=np.concatenate(worldset)
        raw_bounds[name]=[coords.min(axis=0),coords.max(axis=0)]
        if group in SEATS:
            # Check the bottoms of each shoe from local left and right halves.
            tolocal=(coords-n.get('translation',[0,0,0]))@rot
            shoes[group]=[float(coords[tolocal[:,0]*s>.02,1].min()) for s in [-1,1]]
            positions[group]=n.get('translation')
    low=lambda n:raw_bounds[n][0][1]
    high=lambda n:raw_bounds[n][1][1]
    support['table on rail']=low('table-top-walnut')-high('apron-longitudinal')
    for side in ('left','right'):
        arch='trestle-'+side;support[arch+' on floor']=low(arch);support['rail on '+arch]=low('apron-longitudinal')-high(arch)
        for end in ('near','far'):
            mount='mount-'+side+'-'+end
            support['table on '+mount]=low('table-top-walnut')-high(mount)
            support[mount+' on arch']=low(mount)-high(arch)
    support['folder on mat']=low('folio-binding')-high('writing-inlay-sage')
    support['pencil on mat']=low('pencil-body')-high('writing-inlay-sage')
    assert max(abs(v) for v in support.values())<.00001
    assert max(abs(v) for pair in shoes.values() for v in pair)<.00001
    front=depths.argmin(axis=0);stats={}; projected_actors={}
    for i,g in enumerate(groups):
        mask=np.isfinite(depths[i]);y,x=np.nonzero(mask)
        visible=mask & (front==i)
        occluded=mask & ~visible
        bounds=[int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)]
        stats[g]={'isolated_pixels':int(mask.sum()),'visible_pixels':int(visible.sum()),'occluded_percent':round(float(occluded.sum()/mask.sum()*100),3),
                  'occluded_by':{k:int((occluded & (front==j)).sum()) for j,k in enumerate(groups) if np.any(occluded & (front==j))},'bbox_px':bounds}
        if g in SEATS or g=='folio':
            contours,_=cv2.findContours(visible.astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
            primary=max(contours, key=cv2.contourArea)
            contour=cv2.approxPolyDP(primary,1.5,True)[:,0,:].astype(float)+.5
            projected_actors[g]={'bounds':(np.array(bounds)/[w,h,w,h]).tolist(),
                                 'hitPolygon':np.round((contour-bounds[:2])/(np.array(bounds[2:])-bounds[:2]),5).tolist()}
        if g in SEATS:
            for part,buffer in detail_depths.items():
                own_surface=np.isfinite(buffer[i]) & (buffer[i] == depths[i])
                stats[g][part]={'silhouette_pixels':int(own_surface.sum()),
                                'hidden_pixels':int((own_surface & occluded).sum())}
            feet=np.array([positions[g][0],0,positions[g][2]])
            d=feet-target
            projected_actors[g]['feet']=[.5+d@right/cam['width'],.5-d@up/cam['height']]
    return {'pixels':[w,h],'groups':stats,'shoe_floor_gaps_m':shoes,'support_gaps_m':support},projected_actors

if __name__=='__main__':
    ROOT = Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
    spec=json.loads((ROOT/'camera.json').read_text())
    final,anchors=compare(ROOT/'assembly.glb',spec)
    book_page=anchors.pop('folio')
    spec.update(projectedActors=anchors,bookPage=book_page)
    for role in SEATS:
        actor=final['groups'][role]
        x0,y0,x1,y1=actor['bbox_px']
        assert min(x0,y0,spec['pixelWidth']-x1,spec['pixelHeight']-y1)>0
        for feature in ('face_and_eyes','hands_and_role_prop'):
            measured=actor[feature]
            assert measured['silhouette_pixels']>0 and measured['hidden_pixels']==0, (role,feature,measured)
        assert actor['occluded_percent']<10
        assert final['groups']['folio']['occluded_percent']==0
    (ROOT/'camera.json').write_text(json.dumps(spec,indent=2)+'\n')
    (ROOT/'visibility-audit.json').write_text(json.dumps({'method':'Pixel-centre triangle projection of the final GLBs using their respective default orthographic views. Feature statistics compare face and hands/props materials visible on each isolated figure with that figure in the full scene.',
        'sha256':hashlib.sha256((ROOT/'assembly.glb').read_bytes()).hexdigest(),'current':final},indent=2)+'\n')
