"""Original MOON GARDEN art, embedded-texture GLB2 models, skeleton and clips.
Python 3 standard library only. Re-run: python tools/generate_moon_garden.py
No downloaded assets or copyrighted character references. Deterministic output.
"""
from collections import defaultdict
from pathlib import Path
import hashlib,json,math,random,struct,zlib
ROOT=Path(__file__).resolve().parents[1]/'worlds'/'moon-garden'
TAU=math.tau

def add(a,b):return tuple(x+y for x,y in zip(a,b))
def sub(a,b):return tuple(x-y for x,y in zip(a,b))
def mul(a,s):return tuple(x*s for x in a)
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def norm(a):
 s=math.sqrt(dot(a,a));return mul(a,1/s) if s>1e-10 else (0,1,0)
def mix(a,b,t):return tuple(x+(y-x)*t for x,y in zip(a,b))
def clamp(v,lo=0,hi=1):return max(lo,min(hi,v))
def rgb(h):return tuple((int(h[i:i+2],16)/255)**2.2 for i in (1,3,5))
def quat(axis,d):
 a=math.radians(d)/2;return (*mul(norm(axis),math.sin(a)),math.cos(a))
def qmul(a,b):
 x,y,z,w=a;X,Y,Z,W=b;return (w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z)
def euler(x=0,y=0,z=0):return qmul(quat((0,0,1),z),qmul(quat((0,1,0),y),quat((1,0,0),x)))
def rotate(v,q):
 u=q[:3];s=q[3];return add(add(mul(u,2*dot(u,v)),mul(v,s*s-dot(u,u))),mul(cross(u,v),2*s))
def png(n,p):
 def chunk(t,d):return struct.pack('>I',len(d))+t+d+struct.pack('>I',zlib.crc32(t+d)&0xffffffff)
 scan=b''.join(b'\0'+bytes(p[y*n*3:(y+1)*n*3]) for y in range(n))
 return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',n,n,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(scan,9))+chunk(b'IEND',b'')
class Bitmap:
 def __init__(self,n,c):self.n=n;self.p=bytearray(list(c)*(n*n))
 def pixel(self,x,y,c):
  if 0<=x<self.n and 0<=y<self.n:
   k=(int(y)*self.n+int(x))*3
   for i in range(3):self.p[k+i]=int(clamp(c[i],0,255))
 def line(self,x0,y0,x1,y1,c):
  steps=max(1,int(max(abs(x1-x0),abs(y1-y0))*1.3))
  for i in range(steps+1):self.pixel(round(x0+(x1-x0)*i/steps),round(y0+(y1-y0)*i/steps),c)
 def encoded(self):return png(self.n,self.p)
def make_textures():
 rng=random.Random(24817);out={};n=256
 for kind,base in [('stone',(214,203,177)),('grass',(100,135,103)),('water',(48,128,143)),('cloth',(227,236,224)),('bark',(112,87,64)),('leaf',(89,131,108))]:
  im=Bitmap(n,base)
  for y in range(n):
   for x in range(n):
    noise=rng.uniform(-6,6)
    if kind=='stone':
     noise+=4*math.sin(x*.081+y*.032)+2*math.sin(y*.43)
     joint=min(x%128,127-x%128,y%64,63-y%64);noise+=-27 if joint<1 else (-10 if joint<3 else 0)
     c=[v+noise for v in base]
    elif kind=='grass':
     noise+=9*math.sin(x*.033)*math.sin(y*.038)+3*math.sin((x+y)*.18);c=[99+noise*.8,133+noise,101+noise*.65]
    elif kind=='water':
     a=math.sin(x*.098+1.8*math.sin(y*.052));b=math.sin(y*.103+2.1*math.sin(x*.049));light=max(0,1-abs(a+b)*1.5)**7*63;d=7*math.sin((x+y)*.021)
     c=(45+light*.6+d,126+light+d,145+light+d)
    elif kind=='cloth':
     w=(3 if x%3==0 else 0)+(2 if y%3==0 else 0)+noise*.4-(11 if min(x%64,63-x%64)<2 else 0);c=(228+w,235+w,226+w)
    elif kind=='bark':
     a=10*math.sin(x*.31+math.sin(y*.024)*.8)+5*math.sin(x*.8+y*.006)+noise;c=(111+a,88+a*.8,65+a*.6)
    else:
     a=12 if abs(x-n/2)<2 or abs(((y+abs(x-n/2)*.65)%36)-18)<1.3 else 0;t=math.sin(math.pi*x/n)*8+noise
     c=(81+t+a,128+t+a,103+t+a*.8)
    im.pixel(x,y,c)
  if kind=='stone':
   for i in range(22):
    x=rng.randrange(n);y=rng.randrange(n)
    for j in range(rng.randrange(2,7)):
     xx=x+rng.randrange(-8,9);yy=y+rng.randrange(4,17);im.line(x,y,xx,yy,(155,149,128));x,y=xx,yy
  if kind=='grass':
   for i in range(1900):
    x=rng.randrange(n);y=rng.randrange(n);tone=rng.uniform(-12,12);im.line(x,y,x+rng.randrange(-1,2),y-rng.randrange(2,5),(97+tone*.6,132+tone,102+tone*.75))
  if kind=='cloth':
   for cy in (32,96,160,224):
    for cx in (32,96,160,224):
     for a,b in [((cx,cy-9),(cx+5,cy)),((cx+5,cy),(cx,cy+9)),((cx,cy+9),(cx-5,cy)),((cx-5,cy),(cx,cy-9))]:im.line(*a,*b,(193,182,135))
  out[kind]=im.encoded()
 out['face']=face_texture()
 return out
def face_texture():
 # UVs match the head lathe: front u=.25, bottom-to-top v.
 # The eyes and smile stay on one surface, avoiding nested outline shells.
 n=512;im=Bitmap(n,(243,202,181))
 for y in range(n):
  v=y/n
  for x in range(n):
   u=x/n;c=[243.,202.,181.]
   blush=sum(math.exp(-(((u-a)/.045)**2+((v-.405)/.044)**2)*2) for a in (.145,.355))*.19
   c=[c[k]*(1-blush)+(233,139,133)[k]*blush for k in range(3)]
   for e in (.169,.331):
    dx=(u-e)/.055;dy=(v-.505)/.048
    lid=.76+.24*(1-min(1,abs(dx)))
    if dx*dx+(dy/lid)**2<1.10:c=[31,44,50]
    if dx*dx+((dy+.025)/lid)**2<.80:c=[255,245,230]
    ix=(u-e)/.021;iy=(v-.50)/.037
    if ix*ix+iy*iy<1:c=[33+32*max(0,-iy),100+76*max(0,-iy),120+77*max(0,-iy)]
    if ((u-e)/.007)**2+((v-.506)/.028)**2<1:c=[19,37,48]
    if ((u-e+.007)/.006)**2+((v-.521)/.010)**2<1:c=[255,255,247]
    if ((u-e-.007)/.003)**2+((v-.485)/.005)**2<1:c=[183,242,235]
    # a fine, softly arched brow and an outside upper-lid wing
    if abs(u-e)<.043 and abs(v-(.585+.014*(1-((u-e)/.043)**2)))<.004:c=[55,60,59]
   # Tiny understated nose and mouth.
   if ((u-.25)/.006)**2+((v-.414)/.012)**2<1:c=[213,164,147]
   if abs(u-.25)<.023 and abs(v-(.338-.006*(1-((u-.25)/.023)**2)))<.003:c=[155,108,105]
   im.pixel(x,y,c)
 return im.encoded()

TEXTURES={}
class Glb:
 def __init__(self,name):
  self.doc={'asset':{'version':'2.0','generator':'LINK Moon Garden original art 1.0','copyright':'Copyright 2026 Song Youngwoon. Apache-2.0.'},'scene':0,'scenes':[{'nodes':[]}],'nodes':[],'meshes':[],'materials':[],'bufferViews':[],'accessors':[],'buffers':[],'images':[],'textures':[],'samplers':[{'magFilter':9729,'minFilter':9987,'wrapS':10497,'wrapT':10497}]}
  self.name=name;self.bin=bytearray();self.groups=defaultdict(lambda:[[],[]]);self.materials={};self.images={};self.skinned=False;self.bones=[]
 def raw(self,data,target=None):
  while len(self.bin)%4:self.bin.append(0)
  v={'buffer':0,'byteOffset':len(self.bin),'byteLength':len(data)}
  if target:v['target']=target
  self.bin.extend(data);self.doc['bufferViews'].append(v);return len(self.doc['bufferViews'])-1
 def accessor(self,values,typ='VEC3',component=5126,target=34962,bounds=False):
  size={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[typ];flat=list(values) if size==1 else [v for row in values for v in row]
  view=self.raw(struct.pack('<'+{5126:'f',5123:'H',5125:'I'}[component]*len(flat),*flat),target)
  a={'bufferView':view,'componentType':component,'count':len(flat)//size,'type':typ}
  if bounds:
   rows=[[v] for v in values] if size==1 else values;a['min']=[min(row[i] for row in rows) for i in range(size)];a['max']=[max(row[i] for row in rows) for i in range(size)]
  self.doc['accessors'].append(a);return len(self.doc['accessors'])-1
 def material(self,name,color='#FFFFFF',texture=None,metallic=0,roughness=.8,emissive=None,double=False,unlit=False):
  if texture is not None and texture not in self.images:
   view=self.raw(TEXTURES[texture]);self.doc['images'].append({'name':texture,'bufferView':view,'mimeType':'image/png'});self.doc['textures'].append({'sampler':0,'source':len(self.doc['images'])-1});self.images[texture]=len(self.doc['textures'])-1
  mat={'name':name,'pbrMetallicRoughness':{'baseColorFactor':[*rgb(color),1],'metallicFactor':metallic,'roughnessFactor':roughness},'doubleSided':double}
  if texture is not None:mat['pbrMetallicRoughness']['baseColorTexture']={'index':self.images[texture]}
  if emissive:mat['emissiveFactor']=list(rgb(emissive))
  if unlit:mat['extensions']={'KHR_materials_unlit':{}};self.doc['extensionsUsed']=['KHR_materials_unlit']
  self.materials[name]=len(self.doc['materials']);self.doc['materials'].append(mat)
 def geometry(self,mat,p,n,uv,indices,color=(1,1,1,1),bone=0,weights=None,colors=None):
  group=self.groups[mat];offset=len(group[0])
  for i,pos in enumerate(p):
   w=weights[i] if weights is not None else [(bone,1.)];j=[j for j,w in w]+[0]*4;ww=[v for j,v in w]+[0.]*4
   group[0].append((pos,norm(n[i]),uv[i],colors[i] if colors is not None else color,tuple(j[:4]),tuple(ww[:4])))
  group[1].extend(i+offset for i in indices)
 def quad(self,mat,p,uv=None,color=(1,1,1,1),bone=0):
  n=norm(cross(sub(p[1],p[0]),sub(p[2],p[0])));self.geometry(mat,p,[n]*4,uv or [(0,0),(1,0),(1,1),(0,1)],[0,1,2,0,2,3],color,bone)
 def box(self,mat,c,s,q=(0,0,0,1),bone=0,color=(1,1,1,1),uvscale=1):
  x,y,z=mul(s,.5);faces=[[(x,-y,-z),(x,y,-z),(x,y,z),(x,-y,z)],[(-x,-y,z),(-x,y,z),(-x,y,-z),(-x,-y,-z)],[(-x,y,-z),(-x,y,z),(x,y,z),(x,y,-z)],[(-x,-y,z),(-x,-y,-z),(x,-y,-z),(x,-y,z)],[(-x,-y,z),(x,-y,z),(x,y,z),(-x,y,z)],[(x,-y,-z),(-x,-y,-z),(-x,y,-z),(x,y,-z)]]
  for f in faces:self.quad(mat,[add(c,rotate(v,q)) for v in f],[(0,0),(uvscale,0),(uvscale,uvscale),(0,uvscale)],color,bone)
 def ellipsoid(self,mat,c,r,segs=16,rings=10,bone=0,q=(0,0,0,1),color=(1,1,1,1)):
  p=[];n=[];uv=[];ii=[]
  for i in range(rings+1):
   t=math.pi*i/rings
   for j in range(segs+1):
    a=TAU*j/segs-math.pi;v=(math.sin(t)*math.sin(a),math.cos(t),math.sin(t)*math.cos(a));p.append(add(c,rotate(tuple(v[k]*r[k] for k in range(3)),q)));n.append(rotate(norm(tuple(v[k]/max(r[k],.0001) for k in range(3))),q));uv.append((j/segs,i/rings))
  for i in range(rings):
   for j in range(segs):
    a=i*(segs+1)+j;b=a+segs+1
    if i>0:ii.extend([a,b,a+1])
    if i<rings-1:ii.extend([a+1,b,b+1])
  self.geometry(mat,p,n,uv,ii,color,bone)
 def tube(self,mat,start,end,radii,segs=12,bone=0,color=(1,1,1,1),weights=None):
  axis=norm(sub(end,start));e1=norm(cross((0,0,1) if abs(axis[2])<.9 else (1,0,0),axis));e2=cross(e1,axis);p=[];n=[];uv=[];ws=[];ii=[]
  for i,r in enumerate(radii):
   t=i/(len(radii)-1);c=mix(start,end,t)
   for j in range(segs+1):
    a=j/segs*TAU;v=add(mul(e1,math.cos(a)),mul(e2,math.sin(a)));p.append(add(c,mul(v,r)));n.append(v);uv.append((j/segs,t*max(.25,math.dist(start,end))));ws.append(weights(t) if weights else [(bone,1.)])
  for i in range(len(radii)-1):
   for j in range(segs):a=i*(segs+1)+j;b=a+segs+1;ii.extend([a,b,a+1,a+1,b,b+1])
  self.geometry(mat,p,n,uv,ii,color,bone,ws)
  for end_index,normal in [(0,mul(axis,-1)),(len(radii)-1,axis)]:
   ring=p[end_index*(segs+1):(end_index+1)*(segs+1)];cap=[start if end_index==0 else end]+ring;idx=[]
   for j in range(segs):idx.extend([0,j+1,j+2] if end_index==0 else [0,j+2,j+1])
   self.geometry(mat,cap,[normal]*len(cap),[(.5,.5)]+[(.5+.5*math.cos(j/segs*TAU),.5+.5*math.sin(j/segs*TAU)) for j in range(segs+1)],idx,color,bone,weights=[weights(0 if end_index==0 else 1) if weights else [(bone,1.)]]*len(cap))
 def lathe(self,mat,c,profile,segs=20,bone=0,color=(1,1,1,1)):
  p=[];n=[];uv=[];ii=[]
  for i,(y,rx,rz) in enumerate(profile):
   prev=profile[max(0,i-1)];nxt=profile[min(len(profile)-1,i+1)];slope=((nxt[1]-prev[1])+(nxt[2]-prev[2]))*.5/max(.001,nxt[0]-prev[0])
   for j in range(segs+1):
    a=j/segs*TAU;p.append(add(c,(rx*math.cos(a),y,rz*math.sin(a))));n.append(norm((math.cos(a),-slope,math.sin(a))));uv.append((j/segs,i/(len(profile)-1)))
  for i in range(len(profile)-1):
   for j in range(segs):a=i*(segs+1)+j;b=a+segs+1;ii.extend([a,b,a+1,a+1,b,b+1])
  self.geometry(mat,p,n,uv,ii,color,bone)
 def ring(self,mat,c,inner,outer,segs=64,q=(0,0,0,1),color=(1,1,1,1)):
  p=[];n=[];uv=[];ii=[]
  for i in range(segs+1):
   a=i/segs*TAU
   for r in (inner,outer):
    v=(math.cos(a)*r,0,math.sin(a)*r);p.append(add(c,rotate(v,q)));n.append(rotate((0,1,0),q));uv.append((v[0]/3,v[2]/3))
  for i in range(segs):a=i*2;ii.extend([a,a+2,a+1,a+1,a+2,a+3])
  self.geometry(mat,p,n,uv,ii,color)
 def disk(self,mat,c,rx,rz,segs=48,color=(1,1,1,1),edge=None):
  p=[c];uv=[(c[0]/3,c[2]/3)];colors=[color];ii=[]
  for i in range(segs+1):
   a=i/segs*TAU;x=c[0]+rx*math.cos(a);z=c[2]+rz*math.sin(a);p.append((x,c[1],z));uv.append((x/3,z/3));colors.append(edge or color)
  for i in range(segs):ii.extend([0,i+2,i+1])
  self.geometry(mat,p,[(0,1,0)]*len(p),uv,ii,colors=colors)
 def leaf(self,mat,start,end,width,bone=0,color=(1,1,1,1)):
  axis=sub(end,start);side=norm(cross(norm(axis),(0,1,0)))
  if abs(dot(norm(axis),(0,1,0)))>.93:side=(1,0,0)
  mid=mix(start,end,.52);p=[start,add(mid,mul(side,width)),end,sub(mid,mul(side,width)),add(mid,(0,width*.16,0))]
  self.geometry(mat,p,[norm(add((0,1,0),mul(norm(axis),.25)))]*5,[(.5,1),(0,.5),(.5,0),(1,.5),(.5,.5)],[0,1,4,1,2,4,2,3,4,3,0,4],color,bone)
 def save(self,path):
  primitives=[];verts=tris=0
  for mat,(v,ii) in self.groups.items():
   if not ii:continue
   att={'POSITION':self.accessor([x[0] for x in v],bounds=True),'NORMAL':self.accessor([x[1] for x in v]),'TEXCOORD_0':self.accessor([x[2] for x in v],'VEC2'),'COLOR_0':self.accessor([x[3] for x in v],'VEC4')}
   if self.skinned:att['JOINTS_0']=self.accessor([x[4] for x in v],'VEC4',5123);att['WEIGHTS_0']=self.accessor([x[5] for x in v],'VEC4')
   primitives.append({'attributes':att,'indices':self.accessor(ii,'SCALAR',5123 if len(v)<=65535 else 5125,34963),'material':self.materials[mat],'mode':4});verts+=len(v);tris+=len(ii)//3
  self.doc['meshes']=[{'name':self.name,'primitives':primitives}];self.doc['nodes'].insert(0,{'name':self.name,'mesh':0,**({'skin':0} if self.skinned else {})});self.doc['scenes'][0]['nodes']=[0]+([1] if self.skinned else [])
  if self.skinned:
   # Separate unskinned transparent mesh: follows the Element, not the hip bob.
   self.material('contact_shadow','#14232B',unlit=True)
   self.doc['materials'][-1]['alphaMode']='BLEND'
   p=[(0,.024,.06)];uv=[(.5,.5)];colors=[(1,1,1,.16)];ii=[];segments=32
   for radius,alpha in ((.55,.095),(1,0)):
    for i in range(segments+1):
     a=i/segments*TAU;p.append((math.cos(a)*.31*radius,.024,.06+math.sin(a)*.20*radius));uv.append((.5+math.cos(a)*radius*.5,.5+math.sin(a)*radius*.5));colors.append((1,1,1,alpha))
   for i in range(segments):
    ii.extend([0,i+2,i+1]);a=i+1;b=a+segments+1;ii.extend([a,b+1,b,a,a+1,b+1])
   attrs={'POSITION':self.accessor(p,bounds=True),'NORMAL':self.accessor([(0,1,0)]*len(p)),'TEXCOORD_0':self.accessor(uv,'VEC2'),'COLOR_0':self.accessor(colors,'VEC4')}
   shadow={'attributes':attrs,'indices':self.accessor(ii,'SCALAR',5123,34963),'material':self.materials['contact_shadow'],'mode':4}
   self.doc['meshes'].append({'name':'Soft local contact shade','primitives':[shadow]});self.doc['nodes'].append({'name':'Contact shade - unskinned','mesh':1});self.doc['scenes'][0]['nodes'].append(len(self.doc['nodes'])-1)
   verts+=len(p);tris+=len(ii)//3
  self.doc['buffers']=[{'byteLength':len(self.bin)}]
  j=json.dumps(self.doc,separators=(',',':'),ensure_ascii=True).encode();j+=b' '*((-len(j))%4);b=bytes(self.bin);b+=b'\0'*((-len(b))%4)
  data=struct.pack('<4sII',b'glTF',2,28+len(j)+len(b))+struct.pack('<I4s',len(j),b'JSON')+j+struct.pack('<I4s',len(b),b'BIN\0')+b
  assert verts<=65536 and tris<=65536 and len(self.doc['nodes'])<=256 and len(self.doc['materials'])<=32 and len(self.doc['images'])<=8,(verts,tris)
  path.write_bytes(data)
  return {'file':path.name,'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'vertices':verts,'triangles':tris,'primitives':sum(len(m['primitives']) for m in self.doc['meshes']),'nodes':len(self.doc['nodes']),'joints':len(self.bones),'images':len(self.doc['images']),'clips':[a['name'] for a in self.doc.get('animations',[])]}
def build_hero():
 g=Glb('Liora - Original Garden Wayfarer');g.skinned=True
 for name,color,rough,metal in [('blue','#286082',.72,0),('navy','#183247',.75,0),('skin','#F3CAB5',.9,0),('hair','#243A45',.7,0),('hairlight','#45636B',.63,0),('gold','#D6B879',.36,.55),('leather','#514C48',.82,0),('silver','#CBDDE2',.27,.72),('edge','#F0F6E8',.2,.55),('eye_white','#FFF4E8',.6,0),('iris','#4CA8BC',.25,0),('ink','#182B36',.65,0)]:g.material(name,color,metallic=metal,roughness=rough)
 g.material('ivory',texture='cloth',roughness=.88);g.material('face',texture='face',roughness=.9);g.material('light','#FFFDF1',roughness=.2,emissive='#514C3B');g.material('gem','#63D2CC',metallic=.3,roughness=.24,emissive='#0C302D')
 bones=[('root',None,(0,0,0)),('hips','root',(0,.88,0)),('spine','hips',(0,1.08,0)),('chest','spine',(0,1.31,0)),('neck','chest',(0,1.47,0)),('head','neck',(0,1.58,0)),('upper_arm_r','chest',(-.225,1.36,0)),('forearm_r','upper_arm_r',(-.30,1.11,.012)),('hand_r','forearm_r',(-.345,.91,.035)),('upper_arm_l','chest',(.225,1.36,0)),('forearm_l','upper_arm_l',(.30,1.11,.012)),('hand_l','forearm_l',(.345,.91,.035)),('thigh_r','hips',(-.105,.86,0)),('shin_r','thigh_r',(-.105,.47,.012)),('foot_r','shin_r',(-.105,.14,.025)),('thigh_l','hips',(.105,.86,0)),('shin_l','thigh_l',(.105,.47,.012)),('foot_l','shin_l',(.105,.14,.025)),('coat_r','hips',(-.13,.95,-.04)),('coat_l','hips',(.13,.95,-.04)),('scarf','chest',(.08,1.43,-.07))]
 ids={b[0]:i for i,b in enumerate(bones)};B=lambda name:ids[name];g.bones=bones
 for name,parent,pos in bones:
  node={'name':name,'translation':list(sub(pos,bones[B(parent)][2]) if parent else pos)};children=[i+1 for i,b in enumerate(bones) if b[1]==name]
  if children:node['children']=children
  g.doc['nodes'].append(node)
 inv=[[1,0,0,0,0,1,0,0,0,0,1,0,-p[0],-p[1],-p[2],1] for _,_,p in bones]
 g.doc['skins']=[{'name':'Wayfarer Skeleton','joints':[i+1 for i in range(len(bones))],'skeleton':1,'inverseBindMatrices':g.accessor(inv,'MAT4',target=None)}]
 for side in (-1,1):
  b=B('coat_r' if side<0 else 'coat_l');g.ellipsoid('ivory',(side*.145,.88,-.065),(.125,.245,.115),16,8,b,q=euler(0,0,side*7));g.tube('gold',(side*.22,.69,-.10),(side*.245,1.04,-.10),[.008,.008],6,b)
 g.lathe('navy',(0,0,0),[(.89,.14,.10),(.96,.16,.105),(1.10,.155,.106),(1.26,.195,.125),(1.37,.205,.10),(1.40,.135,.085)],24,B('spine'))
 g.lathe('ivory',(0,0,0),[(1.09,.158,.112),(1.17,.174,.12),(1.32,.207,.134),(1.395,.17,.10)],24,B('chest'))
 for side in (-1,1):
  g.ellipsoid('blue',(side*.101,1.235,.102),(.093,.18,.044),14,10,B('chest'),q=euler(0,0,side*-9));g.tube('gold',(side*.037,1.08,.135),(side*.082,1.395,.115),[.007,.006],6,B('chest'));g.box('ivory',(side*.069,1.417,.075),(.105,.06,.075),euler(0,0,side*-20),B('chest'))
 g.lathe('leather',(0,.99,0),[(-.035,.169,.118),(.035,.165,.119)],24,B('hips'));g.box('gold',(0,.995,.127),(.092,.062,.018),bone=B('hips'));g.box('navy',(0,.995,.14),(.051,.031,.006),bone=B('hips'))
 g.lathe('blue',(0,1.435,0),[(-.025,.09,.075),(.025,.085,.07)],20,B('neck'));g.ellipsoid('gold',(0,1.385,.145),(.035,.041,.012),12,8,B('chest'));g.ellipsoid('gem',(0,1.387,.157),(.019,.025,.008),12,8,B('chest'));g.leaf('blue',(.08,1.445,-.075),(.27,1.18,-.16),.065,B('scarf'));g.leaf('gold',(.10,1.43,-.08),(.30,1.17,-.165),.012,B('scarf'))
 g.tube('skin',(0,1.40,0),(0,1.57,0),[.061,.060],14,B('neck'))
 g.lathe('face',(0,1.575,0),[(-.15,.012,.04),(-.12,.069,.084),(-.08,.109,.11),(-.01,.133,.126),(.07,.135,.128),(.13,.111,.10),(.17,.065,.06),(.175,0,0)],32,B('head'))
 for side in (-1,1):g.ellipsoid('skin',(side*.135,1.60,-.001),(.026,.042,.022),12,8,B('head'))
 g.ellipsoid('hair',(0,1.686,-.025),(.149,.129,.135),24,14,B('head'))
 for i in range(9):
  x=-.125+i*.031;end_y=1.64+abs(x)*.23+(.015 if i%3==0 else 0);g.tube('hairlight' if i%3==0 else 'hair',(x*.77,1.765,.04),(x,end_y,.133),[.026,.032,.021,.001],10,B('head'))
 for side in (-1,1):
  for i in range(3):g.tube('hairlight' if i==0 else 'hair',(side*(.11+.006*i),1.72,-.018-i*.032),(side*(.145+.012*i),1.50-i*.022,-.035-i*.029),[.027,.035,.026,.001],10,B('head'))
 for i in range(5):
  x=(i-2)*.05;g.tube('hair',(x,1.72,-.113),(x*1.12,1.47,-.11),[.032,.034,.025,.001],9,B('head'))
 g.tube('hairlight',(-.035,1.77,.015),(.018,1.837,-.024),[.015,.019,.001],8,B('head'))
 for side,label in [(-1,'r'),(1,'l')]:
  upper=B('upper_arm_'+label);fore=B('forearm_'+label);hand=B('hand_'+label);shoulder=(side*.219,1.36,0);elbow=(side*.30,1.11,.012);wrist=(side*.345,.91,.035)
  g.ellipsoid('blue',add(shoulder,(0,-.027,0)),(.108,.115,.099),16,10,upper);g.tube('ivory',shoulder,elbow,[.078,.081,.068,.063],14,upper);g.tube('gold',mix(shoulder,elbow,.18),mix(shoulder,elbow,.23),[.083,.082],14,upper);g.ellipsoid('ivory',elbow,(.065,.068,.065),14,8,fore);g.tube('ivory',elbow,wrist,[.065,.071,.061,.049],14,fore);g.tube('blue',mix(elbow,wrist,.68),mix(elbow,wrist,.96),[.061,.056,.048],14,fore);g.tube('gold',mix(elbow,wrist,.74),mix(elbow,wrist,.78),[.062,.060],14,fore);g.ellipsoid('leather',add(wrist,(0,-.04,.004)),(.044,.061,.041),14,9,hand);g.ellipsoid('skin',add(wrist,(side*-.028,-.042,.030)),(.018,.035,.022),10,7,hand);g.ellipsoid('gold',mix(elbow,wrist,.80),(.018,.024,.062),10,6,fore)
 for side,label in [(-1,'r'),(1,'l')]:
  thigh=B('thigh_'+label);shin=B('shin_'+label);foot=B('foot_'+label);x=side*.105
  g.tube('navy',(x,.87,0),(x,.45,.012),[.099,.102,.082,.068],16,thigh);g.ellipsoid('ivory',(x,.68,.058),(.064,.15,.053),16,10,thigh);g.ellipsoid('silver',(x,.467,.061),(.073,.086,.034),16,10,shin);g.tube('leather',(x,.48,.012),(x,.15,.025),[.069,.075,.066,.055],16,shin);g.tube('blue',(x,.46,.012),(x,.40,.015),[.075,.076],16,shin);g.tube('gold',(x,.412,.015),(x,.399,.017),[.077,.077],16,shin);g.ellipsoid('leather',(x,.108,.076),(.077,.105,.165),18,10,foot);g.ellipsoid('navy',(x,.041,.085),(.082,.037,.171),18,8,foot);g.box('gold',(x,.20,.075),(.057,.026,.05),bone=shin)
 hand=B('hand_r');cx=-.345;g.tube('navy',(cx,.86,.045),(cx,.72,.045),[.024,.023],12,hand)
 for i in range(5):g.tube('gold',(cx,.73+i*.025,.045),(cx,.736+i*.025,.045),[.025,.025],10,hand)
 g.ellipsoid('gold',(cx,.883,.045),(.031,.029,.026),12,8,hand);g.ellipsoid('gem',(cx,.887,.068),(.013,.016,.006),10,6,hand);g.box('gold',(cx,.71,.045),(.23,.032,.055),q=euler(0,0,-4),bone=hand)
 for side in (-1,1):
  g.ellipsoid('gold',(cx+side*.119,.71,.045),(.022,.019,.025),10,6,hand)
  front=[(cx,.69,.061),(cx+side*.042,.68,.045),(cx+side*.031,.22,.045),(cx,.14,.045)];back=[(cx,.69,.029),(cx,.14,.045),(cx+side*.031,.22,.045),(cx+side*.042,.68,.045)];g.quad('silver' if side<0 else 'edge',front if side<0 else front[::-1],bone=hand);g.quad('silver',back if side<0 else back[::-1],bone=hand)
 g.tube('gem',(cx,.63,.063),(cx,.34,.057),[.003,.003],6,hand)
 g.doc['animations']=[]
 def clip(name,times,channels):
  a={'name':name,'samplers':[],'channels':[]};tin=g.accessor(times,'SCALAR',target=None,bounds=True)
  for bone,path,values in channels:
   out=g.accessor(values,'VEC4' if path=='rotation' else 'VEC3',target=None);idx=len(a['samplers']);a['samplers'].append({'input':tin,'output':out,'interpolation':'LINEAR'});a['channels'].append({'sampler':idx,'target':{'node':B(bone)+1,'path':path}})
  g.doc['animations'].append(a)
 clip('Idle',[0,.75,1.5,2.25,3],[('chest','rotation',[euler(0,0,a) for a in (0,1,0,-1,0)]),('head','rotation',[euler(a,b,0) for a,b in ((0,-3),(1,0),(0,3),(-1,0),(0,-3))]),('hips','translation',[(0,.88+a,0) for a in (0,.008,0,-.005,0)]),('scarf','rotation',[euler(a,0,0) for a in (5,-3,5,-3,5)])])
 times=[i*.125 for i in range(9)];channels=[]
 for label,phase in [('r',0),('l',math.pi)]:
  s=[math.sin(i/8*TAU+phase) for i in range(9)];channels += [('thigh_'+label,'rotation',[euler(25*v,0,0) for v in s]),('shin_'+label,'rotation',[euler(-max(0,-v)*34,0,0) for v in s]),('foot_'+label,'rotation',[euler(-max(0,v)*12,0,0) for v in s]),('upper_arm_'+label,'rotation',[euler(-20*v,0,-3 if label=='r' else 3) for v in s]),('forearm_'+label,'rotation',[euler(-9-max(0,v)*10,0,0) for v in s]),('coat_'+label,'rotation',[euler(-v*12,0,0) for v in s])]
 channels += [('hips','translation',[(0,.88+.015*math.sin(i/8*TAU*2),0) for i in range(9)]),('chest','rotation',[euler(0,4*math.sin(i/8*TAU),0) for i in range(9)]),('scarf','rotation',[euler(12+6*math.sin(i/8*TAU),0,-6) for i in range(9)])];clip('Walk',times,channels)
 clip('Attack',[0,.20,.38,.48,.61,.78,1.05,1.35],[('upper_arm_r','rotation',[euler(x,y,z) for x,y,z in ((0,0,0),(-115,-20,-20),(-157,-10,-8),(-95,5,8),(-36,22,15),(-22,7,3),(-8,0,0),(0,0,0))]),('forearm_r','rotation',[euler(x,0,0) for x in (0,-32,-28,18,22,10,0,0)]),('hand_r','rotation',[euler(0,0,z) for z in (0,-15,-21,9,14,5,0,0)]),('chest','rotation',[euler(0,y,z) for y,z in ((0,0),(-15,4),(-21,4),(9,-6),(20,-4),(9,0),(1,0),(0,0))]),('upper_arm_l','rotation',[euler(x,0,z) for x,z in ((0,0),(-28,12),(-34,16),(-25,23),(-8,20),(0,10),(0,0),(0,0))]),('hips','translation',[(0,.88+y,z) for y,z in ((0,0),(-.035,-.02),(-.04,-.03),(-.02,.03),(-.03,.04),(-.01,.02),(0,0),(0,0))]),('head','rotation',[euler(0,y,0) for y in (0,7,12,-5,-9,-4,0,0)]),('coat_r','rotation',[euler(x,0,0) for x in (0,6,8,-13,-18,-9,-3,0)]),('coat_l','rotation',[euler(x,0,0) for x in (0,-5,-7,8,13,6,2,0)])])
 return g
def build_garden():
 g=Glb('Moon Garden - Original Courtyard')
 g.material('marble',texture='stone',roughness=.92);g.material('lightstone','#F0E3C5',texture='stone',roughness=.9);g.material('darkstone','#7D8B83',texture='stone',roughness=.94);g.material('grass',texture='grass',roughness=1);g.material('gold','#CDB27A',metallic=.48,roughness=.42);g.material('water',texture='water',metallic=.22,roughness=.21);g.material('bark',texture='bark',roughness=1);g.material('leaf',texture='leaf',roughness=.95,double=True)
 for name,color in [('leaf_light','#B2CA99'),('leaf_dark','#547B6C'),('petal','#EFC3B6'),('petal_light','#F8E1C6'),('purple','#A8A2C7')]:g.material(name,color,roughness=.9,double=True)
 g.material('cloth','#82A4B4',texture='cloth',roughness=.9,double=True);g.material('glow','#F9E5B6',emissive='#887152',unlit=True);g.material('moonstone','#A0CDC9',metallic=.32,roughness=.3,emissive='#123A3B');g.material('mountain','#8EA7A1',roughness=1);g.material('mountain_far','#B9B9AB',roughness=1);g.material('cloud','#F0D8BD',roughness=1,unlit=True)
 rng=random.Random(92851)
 g.box('darkstone',(0,-.36,-4),(24,.7,28),uvscale=4)
 g.quad('grass',[(-12,-.007,10),(12,-.007,10),(12,-.007,-18),(-12,-.007,-18)],uv=[(-4,10/3),(4,10/3),(4,-6),(-4,-6)])
 def shadow(x,z,rx,rz,strength=.58):g.disk('grass',(x,-.002,z),rx,rz,color=(strength,strength*.99,strength*.95,1),edge=(1,1,1,1))
 for x,z,rx,rz in [(-9,-11,3.3,3),(8,-8,4.3,3.5),(8,1,3.5,2.1),(-8,4,2.2,2),(-7,-4,2,3)]:shadow(x,z,rx,rz)
 g.disk('marble',(0,.005,-5),3.35,3.35,96,color=(.96,.97,.94,1));g.ring('gold',(0,.012,-5),3.17,3.20,96);g.ring('darkstone',(0,.014,-5),2.97,3.05,96);g.ring('gold',(0,.017,-5),1.1,1.13,64)
 for z in [8.7-i*1.03 for i in range(23)]:
  for col in (-1,0,1):
   if math.hypot(col*.74,z+5)<3.3:continue
   g.box('marble',(col*.74,.009,z),(.69,.035,.96),q=euler(0,rng.uniform(-1,1),0),uvscale=.62,color=(rng.uniform(.88,1),rng.uniform(.9,1),.95,1))
 for i in range(8):
  a=i/8*TAU;g.box('gold',(math.cos(a)*2.67,.019,-5+math.sin(a)*2.67),(.035,.013,.35 if i%2 else .56),q=euler(0,-math.degrees(a)+90,0))
 px=-6.15;pz=-5.6;sx=3.85;sz=9.3
 g.box('darkstone',(px,-.055,pz),(sx+.45,.12,sz+.45),uvscale=3)
 g.quad('water',[(px-sx/2,.018,pz+sz/2),(px+sx/2,.018,pz+sz/2),(px+sx/2,.018,pz-sz/2),(px-sx/2,.018,pz-sz/2)],uv=[(0,0),(1.5,0),(1.5,3),(0,3)])
 for side in (-1,1):
  g.box('lightstone',(px+side*(sx/2+.12),.09,pz),(.26,.18,sz+.5),uvscale=3);g.box('lightstone',(px,.09,pz+side*(sz/2+.12)),(sx+.5,.18,.26),uvscale=2);g.box('gold',(px+side*(sx/2-.015),.03,pz),(.024,.018,sz))
 for i in range(13):
  x=px+rng.uniform(-1.4,1.4);z=pz+rng.uniform(-3.9,3.9);r=rng.uniform(.12,.25);g.disk('leaf_dark',(x,.028,z),r,r*.78,16,color=(.9,1,.94,1))
  if i%3==0:
   for j in range(6):
    a=j/6*TAU;g.leaf('petal_light',(x,.035,z),(x+math.cos(a)*.17,.12,z+math.sin(a)*.17),.045)
   g.ellipsoid('gold',(x,.08,z),(.028,.035,.028),8,5)
 for i in range(9):
  x=px+rng.uniform(-1.4,1.4);z=pz+rng.uniform(-3.7,3.7);g.ring('moonstone',(x,.022,z),.2+i*.012,.209+i*.012,32,color=(.65,.85,.8,1))
 gatez=-13.9;gatey=3.05;inside=2.18;outside=2.81
 def column(x,z,h=3.1):
  g.box('darkstone',(x,.1,z),(1.13,.2,1.13),uvscale=.7);g.box('marble',(x,.27,z),(.96,.18,.96),uvscale=.7)
  g.lathe('marble',(x,0,z),[(.32,.48,.48),(.42,.48,.48),(.49,.38,.38),(.57,.35,.35),(h-.4,.29,.29),(h-.28,.36,.36),(h-.18,.4,.4)],24)
  for j in range(12):
   a=j/12*TAU;g.tube('lightstone',(x+math.cos(a)*.305,.6,z+math.sin(a)*.305),(x+math.cos(a)*.285,h-.38,z+math.sin(a)*.285),[.032,.025],6,color=(.92,.94,.93,1))
  g.box('marble',(x,h-.11,z),(.94,.23,.94),uvscale=.8);g.box('gold',(x,.4,z),(.982,.022,.982))
 for side in (-1,1):
  column(side*2.5,gatez,3.13);g.box('marble',(side*2.5,1.65,gatez),(.7,2.9,.98),uvscale=1.4);g.box('gold',(side*2.5,1.82,gatez+.505),(.07,1.83,.014));g.ellipsoid('moonstone',(side*2.5,2.9,gatez+.52),(.09,.11,.035),12,8)
 for i in range(19):
  a=i/19*math.pi+.007;b=(i+1)/19*math.pi-.007;p=[(math.cos(t)*r,gatey+math.sin(t)*r,z) for z in (gatez-.48,gatez+.48) for t,r in ((a,inside),(a,outside),(b,outside),(b,inside))]
  for face in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(3,7,6,2),(0,4,7,3),(1,2,6,5)]:g.quad('lightstone' if i%4==0 else 'marble',[p[k] for k in face],color=(.94+i%3*.02,.95+i%2*.02,.94,1))
 for i in range(40):
  a=i/40*math.pi;b=(i+1)/40*math.pi;g.tube('gold',(math.cos(a)*2.23,gatey+math.sin(a)*2.23,gatez+.494),(math.cos(b)*2.23,gatey+math.sin(b)*2.23,gatez+.494),[.018,.018],6)
 g.ellipsoid('moonstone',(0,3.55,gatez+.02),(.37,.37,.37),24,14);g.ring('gold',(0,3.55,gatez+.04),.61,.645,72,q=euler(90,0,0));g.ring('gold',(0,3.55,gatez+.04),.78,.801,72,q=euler(55,0,28))
 for i in range(8):
  a=i/8*TAU;g.ellipsoid('glow',(.88*math.cos(a),3.55+.88*math.sin(a),gatez+.08),(.026,.026,.026),8,5)
 for side in (-1,1):
  for i in range(5):
   x=side*(3.5+i*1.2);h=3.4-i*.39+rng.uniform(-.25,.25);g.box('marble',(x,h/2,gatez),(1.15,h,.65),uvscale=1.3,color=(.87,.9,.86,1));g.box('lightstone',(x,h+.07,gatez),(1.2,.14,.72),q=euler(0,0,rng.uniform(-3,3)),uvscale=.5)
   if i%2==0:g.box('gold',(x,1.4,gatez+.334),(.035,.90,.018))
  for i in range(6):
   x=side*rng.uniform(3.5,9);z=gatez+rng.uniform(.7,2.3);g.box('marble',(x,.14,z),(rng.uniform(.22,.52),.25,rng.uniform(.25,.65)),q=euler(0,rng.randrange(180),rng.uniform(-7,7)),uvscale=.5,color=(.8,.85,.78,1))
 column(-9.7,-11.6,2.52);column(9.8,-12,2.08);g.box('marble',(-9.7,2.67,-11.6),(1.05,.27,1.13),q=euler(0,0,-7),uvscale=.6)
 for x,z in [(6,-2),(10,-2),(6,3),(10,3)]:column(x,z,2.9)
 for z in (-2,3):g.box('bark',(8,2.86,z),(4.8,.15,.15),uvscale=2)
 p=[];n=[];uv=[];ii=[];steps=12
 for iz in range(steps+1):
  for ix in range(steps+1):
   u=ix/steps;v=iz/steps;x=5.8+u*4.4;z=-2.25+v*5.5;y=3.07-.4*math.sin(u*math.pi)*math.sin(v*math.pi);p.append((x,y,z));n.append(norm((.4*math.pi*math.cos(u*math.pi)*math.sin(v*math.pi)/4.4,1,.4*math.pi*math.sin(u*math.pi)*math.cos(v*math.pi)/5.5)));uv.append((u*2,v*2))
 for iz in range(steps):
  for ix in range(steps):a=iz*(steps+1)+ix;ii.extend([a,a+steps+1,a+1,a+1,a+steps+1,a+steps+2])
 g.geometry('cloth',p,n,uv,ii,color=(.88,.95,1,1))
 for z in (-2.2,3.2):g.tube('gold',(5.8,3.07,z),(10.2,3.07,z),[.025,.025],8)
 shadow(8,.2,3.2,3.9,.63)
 for x,z,angle in [(8,1.2,0),(-8,5,90),(4,-10,25)]:
  q=euler(0,angle,0);g.box('lightstone',(x,.48,z),(2.5,.17,.68),q=q,uvscale=1)
  for side in (-1,1):g.box('darkstone',add((x,.22,z),rotate((side*.89,0,0),q)),(.29,.43,.51),q=q,uvscale=.6)
 for x,z in [(-3.5,2),(3.5,2),(-3.5,-10.5),(3.5,-10.5)]:
  g.lathe('marble',(x,0,z),[(0,.26,.26),(.1,.26,.26),(.18,.17,.17),(.65,.13,.13),(.72,.22,.22)],12);g.ellipsoid('glow',(x,.85,z),(.12,.16,.12),12,8);g.lathe('gold',(x,0,z),[(.7,.21,.21),(.74,.2,.2),(.98,.1,.1),(1.07,0,0)],12)
 def tree(x,z,h,kind='olive'):
  shadow(x,z,h*.75,h*.57,.54);g.tube('bark',(x,-.02,z),(x+.12,h*.67,z-.1),[.27,.23,.17,.08],12)
  for j in range(5):
   a=j/5*TAU+.3;end=(x+math.cos(a)*h*.38,h*.78+rng.uniform(-.1,.7),z+math.sin(a)*h*.35);g.tube('bark',(x+.07,h*.42+j*.12,z),end,[.105,.075,.025],9)
   for k in range(2):
    c=add(end,(rng.uniform(-.6,.6),rng.uniform(.05,.55),rng.uniform(-.5,.5)));mat='leaf_light' if j%3==0 else 'leaf';g.ellipsoid(mat,c,(h*.25,h*.16,h*.23),14,8,q=euler(rng.randrange(20),rng.randrange(180),rng.randrange(15)),color=(rng.uniform(.85,1),rng.uniform(.9,1),.97,1))
    for leaf_index in range(22):
     angle=rng.random()*TAU;lift=rng.uniform(-.6,.8);offset=(math.cos(angle)*h*.23,rng.uniform(-.2,.3)+lift*h*.12,math.sin(angle)*h*.21);lp=add(c,offset);la=rng.random()*TAU;length=rng.uniform(.18,.35);g.leaf('leaf_light' if leaf_index%4==0 else 'leaf',lp,add(lp,(math.cos(la)*length,.04,math.sin(la)*length)),.07,color=(.78,.94,.83,1))
  for j in range(5):
   a=j/5*TAU;g.tube('bark',(x,.05,z),(x+math.cos(a)*.75,.015,z+math.sin(a)*.75),[.16,.08,.015],8)
 tree(8,-8,5.9);tree(-9.2,-10.8,5,'blossom');tree(-9,4.5,3.7)
 for x,z,h in [(-10.6,-16.2,6.5),(8.5,-16.5,6),(10.9,-14.5,4.5),(-6.4,-16.7,5.1)]:
  g.tube('bark',(x,0,z),(x,h*.7,z),[.15,.08],10);g.lathe('leaf_dark',(x,0,z),[(.7,.3,.3),(1.2,.7,.64),(h*.5,.78,.7),(h*.72,.57,.55),(h*.88,.29,.29),(h+.18,0,0)],16);g.lathe('leaf',(x+.08,.18,z+.08),[(1,.24,.24),(1.5,.53,.5),(h*.5,.56,.5),(h*.76,.3,.32),(h*.96,0,0)],14,color=(.9,.97,.93,1))
 beds=[(-10,-2,1.25,3),(-2.9,5.8,1.15,2),(3.5,4.5,1.1,2.5),(4.8,-6.8,1.1,2),(-8,-14.7,2.4,.75),(7,-14.7,2,.75)]
 for bx,bz,rx,rz in beds:
  for j in range(10):
   a=j/10*TAU;x=bx+math.cos(a)*rx;z=bz+math.sin(a)*rz;g.ellipsoid('darkstone',(x,.06,z),(.28,.13,.22),9,5,q=euler(0,rng.randrange(180),0),color=(.86,.91,.85,1))
  for j in range(14):
   a=rng.random()*TAU;r=math.sqrt(rng.random());x=bx+math.cos(a)*rx*r*.9;z=bz+math.sin(a)*rz*r*.9
   for k in range(7):
    a=k/7*TAU+rng.random()*.3;l=rng.uniform(.25,.55);g.leaf('leaf' if k%3 else 'leaf_light',(x,.01,z),(x+math.cos(a)*l,.1+rng.uniform(.15,.4),z+math.sin(a)*l),rng.uniform(.065,.12),color=(.85+j%3*.05,.94,.88,1))
   if j%2==0:
    y=rng.uniform(.35,.7);g.tube('leaf_dark',(x,0,z),(x,y,z),[.013,.008],5);mat='purple' if (j+int(bx))%3==0 else ('petal_light' if j%3 else 'petal')
    for k in range(5):
     a=k/5*TAU;g.leaf(mat,(x,y-.03,z),(x+math.cos(a)*.15,y+.025,z+math.sin(a)*.15),.068)
    g.ellipsoid('gold',(x,y+.017,z),(.038,.025,.038),8,5)
 for i in range(180):
  x=rng.uniform(-11.5,11.5);z=rng.uniform(-17,9)
  if abs(x)<1.4 or math.hypot(x,z+5)<3.6 or (abs(x-px)<2.2 and abs(z-pz)<5) or (5.5<x<10.5 and -2.8<z<3.5):continue
  for k in range(4):
   a=rng.random()*TAU;h=rng.uniform(.16,.42);g.leaf('leaf_dark' if k%2 else 'leaf',(x,.005,z),(x+math.cos(a)*h*.55,h,z+math.sin(a)*h*.55),.024,color=(.83,.93,.82,1))
 for side in (-1,1):
  for j in range(4):
   x=side*(3.2+j*.65);h=2.6-j*.34;z=gatez+.36;points=[(x+.12*math.sin(k*.9),h-k*.19,z+.04*math.cos(k)) for k in range(13)]
   for k in range(len(points)-1):
    g.tube('leaf_dark',points[k],points[k+1],[.014,.011],5);p=points[k];d=-1 if k%2 else 1;g.leaf('leaf',p,add(p,(d*.24,-.09,.03)),.08,color=(.85,.95,.87,1))
 for i in range(37):g.ellipsoid('petal_light',(rng.uniform(-10,-4),rng.uniform(.02,3.4),rng.uniform(-12,-4)),(.027,.009,.045),6,4,q=euler(rng.randrange(180),rng.randrange(180),rng.randrange(180)))
 # Four continuous, layered ridgelines replace isolated triangle mountains.
 for layer_index in range(4):
  depth=-51+layer_index*5.2;p=[];uv=[];ii=[];steps=80
  for i in range(steps+1):
   x=-55+i/steps*110
   h=2.3+sum(amplitude*math.exp(-((x-center)/width)**2) for center,width,amplitude in [(-34,13,6.5),(-13,10,4.4),(9,17,6.2),(35,12,7.6)])
   h=h*(1-layer_index*.13)+math.sin(x*.15+layer_index*.8)*.45
   p.extend([(x,-2,depth),(x,h,depth)]);uv.extend([(i/steps,0),(i/steps,1)])
  for i in range(steps):a=i*2;ii.extend([a,a+2,a+1,a+1,a+2,a+3])
  shade=1-layer_index*.035;g.geometry('mountain_far' if layer_index<2 else 'mountain',p,[(0,.35,.94)]*len(p),uv,ii,color=(shade,shade,shade,1))
 g.ellipsoid('glow',(-17,16,-40),(3.6,3.6,3.6),32,18)
 for c,r in [((-18,12,-37),(6,.85,1.4)),((15,14,-42),(8,.65,1.2)),((7,18,-48),(4,.48,1))]:g.ellipsoid('cloud',c,r,20,8)
 return g

WORLD='''world {
 version:"0.1";
 id:"moon-garden";
 name:"MOON GARDEN - A Wayfarer's First Light";
 elements:"scene.element";
 style:"appearance.style";
 scripts:["scripts/wayfarer.script"];
 extensions:["models-v1"];
 entry:{"position":[2.4,1.65,2.2],"target":[0,1.15,-5]};
 environment:{"background":"#E3CBB3","grid":false,"fog":{"color":"#E3CBB3","start":34,"end":92}};
 walk:{"min":[-12,0,-18],"max":[12,4,10],"eyeHeight":1.65,"speed":2.2};
}
'''
SCENE='''// Original art generated by tools/generate_moon_garden.py.
scene {
 object moon_garden {
  name:"MOON GARDEN";
  component courtyard {
   raycast:false;
   element garden_model {geometry:{"type":"model","source":"models/garden.glb"};style:"garden";}
  }
  component hero_controller {
   name:"Liora - Garden Wayfarer";
   script:"scripts/wayfarer.script";
   element hero_model {geometry:{"type":"model","source":"models/hero.glb"};style:"hero";position:[0,0,-5];}
  }
  component inscriptions {
   raycast:false;
   element garden_name {geometry:{"type":"plane","size":[5.2,.55]};style:"title";position:[0,6.3,-13.6];text:"M O O N   G A R D E N";}
   element garden_subtitle {geometry:{"type":"plane","size":[4.7,.24]};style:"inscription";position:[0,5.88,-13.59];text:"A WAYFARER'S FIRST LIGHT";}
   element invitation {geometry:{"type":"plane","size":[3.5,.28]};style:"inscription";position:[0,.44,-1.5];rotation:[-28,0,0];text:"Explore the garden. Select Liora to see her sword technique.";}
  }
 }
}
'''
STYLE='''defaults {color:"#FFFFFF";opacity:1;emission:0;}
material garden {color:"#FFFFFF";shading:"pbr";outline:0;}
material hero {color:"#FFFFFF";shading:"toon";outline:.0048;}
material title {color:"#FFF1CF";textBackground:false;opacity:1;emission:.15;}
material inscription {color:"#EDE4CA";textBackground:false;opacity:1;}
'''
SCRIPT='''// Local animation presentation. No changes to multiplayer RPG progress.
on onStart(ctx) {
 store elapsed = 0;
 store phase = 0;
 store attackLeft = 0;
 store currentX = 0;
 ctx.playAnimation("hero_model","Idle",true,1);
}
on onUpdate(ctx, deltaSeconds) {
 elapsed = elapsed + deltaSeconds;
 attackLeft = max(0,attackLeft - deltaSeconds);
 if (attackLeft > 0) {
  ctx.setTransform("hero_model",{position:[currentX,0,-5],rotation:[0,0,0]});
 } else {
  if (phase == 3) {phase = 0;elapsed = 0;ctx.playAnimation("hero_model","Idle",true,1);}
  if (phase == 0 && elapsed > 3.5) {phase = 1;elapsed = 0;ctx.playAnimation("hero_model","Walk",true,.88);}
  if (phase == 1) {
   currentX = sin(min(elapsed / 5,1) * 6.2831853) * 1.65;
   let facing = 90;
   if (elapsed > 1.25 && elapsed < 3.75) {facing = -90;}
   ctx.setTransform("hero_model",{position:[currentX,0,-5],rotation:[0,facing,0]});
   if (elapsed >= 5) {phase = 2;elapsed = 0;currentX = 0;ctx.setTransform("hero_model",{position:[0,0,-5],rotation:[0,0,0]});ctx.playAnimation("hero_model","Attack",false,1);}
  }
  if (phase == 2 && elapsed > 2) {phase = 0;elapsed = 0;ctx.playAnimation("hero_model","Idle",true,1);}
 }
}
on onInteract(ctx, event) {
 phase = 3;elapsed = 0;attackLeft = 1.4;
 ctx.playAnimation("hero_model","Attack",false,1);
}
'''
def main():
 global TEXTURES
 TEXTURES=make_textures();(ROOT/'models').mkdir(parents=True,exist_ok=True);(ROOT/'scripts').mkdir(exist_ok=True)
 reports=[build_hero().save(ROOT/'models'/'hero.glb'),build_garden().save(ROOT/'models'/'garden.glb')]
 for name,data in [('world.link',WORLD),('scene.element',SCENE),('appearance.style',STYLE),('scripts/wayfarer.script',SCRIPT)]: (ROOT/name).write_text(data,encoding='utf-8',newline='\n')
 report={'generator':'tools/generate_moon_garden.py','license':'Apache-2.0','units':'meters','up':'+Y','characterFront':'+Z','character':'Liora - original Garden Wayfarer','assets':reports}
 (ROOT/'asset-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
