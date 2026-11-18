"""STONE SANCTUM: original geometry with offline Poly Haven CC0 PBR maps.
Copyright 2026 Song Youngwoon. SPDX-License-Identifier: Apache-2.0
Run from any directory: python tools/generate_stone_sanctum.py
Uses the shared original Glb mesh helpers in generate_moon_garden.py, standard library only.
Textures/HDRI are checked in: no network or third-party Python modules are required.
"""
from collections import defaultdict
from pathlib import Path
import hashlib,json,math,random,struct
from generate_moon_garden import Glb,add,sub,mul,dot,cross,norm,mix,rotate,euler,quat,TAU,rgb
ROOT=Path(__file__).resolve().parents[1]/'worlds'/'stone-sanctum'
SOURCE=ROOT/'sources'
RNG=random.Random(307171)

class StoneMesh(Glb):
 def __init__(self,name):
  super().__init__(name)
  self.doc['asset']['generator']='LINK Stone Sanctum original architectural geometry 1.0'
  self.doc['asset']['copyright']='Original geometry: Copyright 2026 Song Youngwoon, Apache-2.0. Embedded material maps: Poly Haven, CC0-1.0. See sources/polyhaven-materials.json.'
 def geometry(self,mat,p,n,uv,indices,color=(1,1,1,1),bone=0,weights=None,colors=None):
  # glTF COLOR_0 is normalized linear color: tint variation must stay in range.
  clamp_color=lambda rgba:tuple(max(0.,min(1.,float(v))) for v in rgba)
  return super().geometry(mat,p,n,uv,indices,clamp_color(color),bone,weights,[clamp_color(c) for c in colors] if colors is not None else None)
 def image(self,filename):
  if filename not in self.images:
   data=(SOURCE/filename).read_bytes();view=self.raw(data)
   self.doc['images'].append({'name':filename,'bufferView':view,'mimeType':'image/png' if filename.endswith('.png') else 'image/jpeg'})
   self.doc['textures'].append({'sampler':0,'source':len(self.doc['images'])-1});self.images[filename]=len(self.doc['textures'])-1
  return self.images[filename]
 def pbr(self,name,asset,tint='#FFFFFF',normal=1.,occlusion=.75,roughness=1):
  base=self.image(asset+'_diff_1k.jpg');nor=self.image(asset+'_nor_gl_1k.png');arm=self.image(asset+'_arm_1k.jpg')
  self.materials[name]=len(self.doc['materials'])
  self.doc['materials'].append({'name':name,'pbrMetallicRoughness':{'baseColorFactor':[*rgb(tint),1],'metallicFactor':0,'roughnessFactor':roughness,'baseColorTexture':{'index':base},'metallicRoughnessTexture':{'index':arm}},'normalTexture':{'index':nor,'scale':normal},'occlusionTexture':{'index':arm,'strength':occlusion}})
 def plain(self,name,color,metal=0,rough=.8,emissive=None,unlit=False):
  super().material(name,color,metallic=metal,roughness=rough,emissive=emissive,unlit=unlit)
 def physical_quad(self,mat,points,metres=2.6,color=(1,1,1,1)):
  n=norm(cross(sub(points[1],points[0]),sub(points[2],points[0])));axis=max(range(3),key=lambda a:abs(n[a]))
  # Fixed world projection makes adjacent masonry texture scales consistent.
  axes={0:(2,1),1:(0,2),2:(0,1)}[axis]
  uv=[(p[axes[0]]/metres,p[axes[1]]/metres) for p in points]
  # Mirroring a face's UV is valid; derivative TBN keeps normals aligned to UV0.
  self.quad(mat,points,uv,color)
 def face(self,mat,points,outward,metres=2.6,color=(1,1,1,1)):
  n=cross(sub(points[1],points[0]),sub(points[2],points[0]))
  if dot(n,outward)<0:points=list(reversed(points))
  if len(points)==4:self.physical_quad(mat,points,metres,color)
  else:
   normal=norm(cross(sub(points[1],points[0]),sub(points[2],points[0])));axis=max(range(3),key=lambda a:abs(normal[a]));axes={0:(2,1),1:(0,2),2:(0,1)}[axis]
   self.geometry(mat,points,[normal]*len(points),[(p[axes[0]]/metres,p[axes[1]]/metres) for p in points],[0,1,2],color)
 def block(self,mat,c,size,bevel=.035,q=(0,0,0,1),tint=1.,metres=2.6,seed=0):
  """Closed 26-face chamfered stone; shallow chips vary silhouette deterministically."""
  half=mul(size,.5);bevel=min(bevel,min(half)*.43);local=random.Random(seed+73)
  color=(tint,tint*.985,tint*.96,1)
  def world(points):return [add(c,rotate(p,q)) for p in points]
  def face(points,outward):self.face(mat,world(points),rotate(outward,q),metres,color)
  # Six broad face rectangles.
  for axis in range(3):
   other=[a for a in range(3) if a!=axis]
   for sign in (-1,1):
    ps=[]
    for u,v in ((-1,-1),(-1,1),(1,1),(1,-1)):
     p=[0.,0.,0.];p[axis]=sign*half[axis];p[other[0]]=u*(half[other[0]]-bevel);p[other[1]]=v*(half[other[1]]-bevel);ps.append(tuple(p))
    n=[0.,0.,0.];n[axis]=sign;face(ps,n)
  # Twelve bevel faces, one for every box edge.
  for free in range(3):
   a,b=[i for i in range(3) if i!=free]
   for sa in (-1,1):
    for sb in (-1,1):
     ps=[]
     for which,end in ((0,-1),(1,-1),(1,1),(0,1)):
      p=[0.,0.,0.];p[free]=end*(half[free]-bevel);p[a]=sa*(half[a]-(bevel if which else 0));p[b]=sb*(half[b]-(0 if which else bevel));ps.append(tuple(p))
     n=[0.,0.,0.];n[a]=sa;n[b]=sb;face(ps,n)
  # Eight small corner triangles.
  for sx in (-1,1):
   for sy in (-1,1):
    for sz in (-1,1):
     s=(sx,sy,sz);ps=[]
     for axis in range(3):ps.append(tuple(s[a]*(half[a]-(0 if a==axis else bevel)) for a in range(3)))
     face(ps,s)
 def arch(self,mat,center,inner,outer,depth,start=0,end=math.pi,steps=17,orientation=0,tint=.96):
  q=euler(0,orientation,0);cx,cy,cz=center
  for k in range(steps):
   a=start+(end-start)*k/steps+.003;b=start+(end-start)*(k+1)/steps-.003
   ps=[]
   for z in (-depth/2,depth/2):
    for r,t in ((inner,a),(inner,b),(outer,b),(outer,a)):ps.append(add(center,rotate((r*math.cos(t),r*math.sin(t),z),q)))
   color=(tint+.025*math.sin(k*2.3),tint*.98,tint*.94,1)
   for face in ((0,3,2,1),(4,5,6,7),(0,4,7,3),(1,2,6,5),(0,1,5,4),(3,7,6,2)):
    points=[ps[i] for i in face];middle=tuple(sum(v[a] for v in points)/4 for a in range(3));blockcenter=tuple(sum(v[a] for v in ps)/8 for a in range(3));self.face(mat,points,sub(middle,blockcenter),2.,color)
 def fluted_column(self,center,height=4.15,radius=.32):
  x,y,z=center
  self.block('trim',(x,y+.10,z),(1.02,.2,1.02),.04,metres=1.5,tint=.90)
  self.block('trim',(x,y+.25,z),(.86,.14,.86),.035,metres=1.5,tint=.95)
  self.lathe('trim',center,[(.30,.43,.43),(.34,.43,.43),(.40,.36,.36),(.48,.36,.36),(.54,.31,.31)],32)
  p=[];n=[];uv=[];indices=[];rings=10;segs=48
  for r in range(rings+1):
   h=.53+(height-1.08)*r/rings;bulge=1+.065*math.sin(math.pi*r/rings)
   for j in range(segs+1):
    a=j/segs*TAU;flute=1-.055*(.5+.5*math.cos(a*16));rr=radius*flute*bulge
    p.append((x+rr*math.cos(a),y+h,z+rr*math.sin(a)));n.append(norm((math.cos(a),-.02*math.cos(r/rings*math.pi),math.sin(a))));uv.append((a*radius/1.4,h/1.4))
  for r in range(rings):
   for j in range(segs):a=r*(segs+1)+j;b=a+segs+1;indices.extend((a,b,a+1,a+1,b,b+1))
  self.geometry('trim',p,n,uv,indices)
  self.lathe('trim',center,[(height-.56,.32,.32),(height-.50,.37,.37),(height-.43,.42,.42),(height-.33,.44,.44),(height-.27,.38,.38)],32)
  self.block('trim',(x,y+height-.20,z),(.91,.15,.91),.03,metres=1.6)
  self.block('trim',(x,y+height-.07,z),(1.04,.13,1.04),.025,metres=1.6,tint=.94)
  # Relief rosettes on the front of the capital, not painted flat decals.
  for side in (-1,1):self.rosette((x+side*.22,y+height-.30,z+.42),.11,petals=7,relief=.026)
 def rosette(self,c,r,petals=12,relief=.03):
  for j in range(petals):
   a=j/petals*TAU;mid=add(c,(math.cos(a)*r*.56,math.sin(a)*r*.56,0))
   self.ellipsoid('trim',mid,(r*.37,r*.13,relief),8,4,q=euler(0,0,math.degrees(a)),color=(.92,.88,.82,1))
  self.ellipsoid('trim',add(c,(0,0,relief*.4)),(r*.17,r*.17,relief),12,5,color=(.78,.74,.69,1))
 def rock(self,mat,c,size,seed,detail=9):
  rng=random.Random(seed);p=[];uv=[];n=[];indices=[];rings=5;segs=detail
  radii=[rng.uniform(.78,1.19) for _ in range((rings+1)*segs)]
  for i in range(rings+1):
   t=.045+(math.pi-.09)*i/rings
   for j in range(segs+1):
    a=j/segs*TAU;r=radii[i*segs+(j%segs)];v=(math.sin(t)*math.cos(a),math.cos(t),math.sin(t)*math.sin(a));p.append(add(c,tuple(v[k]*size[k]*(1 if k==1 else r)*.5 for k in range(3))));n.append(norm(tuple(v[k]/max(size[k],.01) for k in range(3))));uv.append((a/TAU*max(size)/1.5,t/math.pi*max(size)/1.5))
  for i in range(rings):
   for j in range(segs):a=i*(segs+1)+j;b=a+segs+1;indices.extend((a,a+1,b,a+1,b+1,b))
  self.geometry(mat,p,n,uv,indices,color=(rng.uniform(.78,1),rng.uniform(.77,.96),rng.uniform(.72,.91),1))


def architecture():
 g=StoneMesh('Stone Sanctum - weathered architecture')
 g.pbr('masonry','sandstone_blocks_04',normal=.65,occlusion=.75)
 g.pbr('trim','sandstone_cracks',normal=.60,occlusion=.6)
 g.plain('bronze','#806B41',metal=.83,rough=.34)
 g.pbr('recess','sandstone_blocks_04',tint='#8D7963',normal=.6,occlusion=.8)
 g.plain('flame_core','#FFE9B3',emissive='#FFE9B3',unlit=True)
 # Thick foundation with courses and individual chamfered stone at every joint.
 for side in (-1,1):
  x=side*4.7
  for row in range(7):
   y=.34+row*.65
   for j in range(11):
    z=4.35-j*1.56-(.72 if row%2 else 0)
    if z<-12.2:continue
    # A broken opening near the front admits a low shaft of sunlight.
    if side<0 and -1.7<z<1.5 and row>=2 and row<=5:continue
    if side>0 and -7.3<z<-4.8 and row>=3 and row<=5:continue
    size=(.7,.62,1.50);g.block('masonry',(x,y,z),size,.025,tint=.92+RNG.random()*.08,metres=2.9,seed=row*22+j)
  for y,depth,height in ((.24,.90,.20),(1.0,.78,.09),(4.6,1.08,.19),(4.86,1.19,.18)):
   g.block('trim',(x,y,-3.5),(depth,height,18.2),.027,metres=2.2,tint=.91)
  # Window jambs and deep carved reveals.
  for centerz in (1.5,-1.65) if side<0 else (-7.3,-4.8):
   for layer in range(3):g.block('trim',(x-side*(.28+layer*.055),2.35,centerz),(.18,.0+2.15,.12),.02,metres=1.8)
 # Two nave arcades. Columns define a usable central walking lane.
 positions=(2.55,-1.1,-4.75,-8.4,-11.75)
 for side in (-1,1):
  x=side*3.3
  for j,z in enumerate(positions):
   if side>0 and j==1:
    # One fallen column: its surviving plinth and a damaged shaft stump.
    g.block('trim',(x,.14,z),(1.08,.28,1.08),.05,metres=1.6,tint=.86)
    g.lathe('trim',(x,0,z),[(.3,.37,.37),(.6,.32,.32),(.81,.30,.30),(.93,.32,.32)],24)
   else:g.fluted_column((x,0,z),4.35)
  for j in range(len(positions)-1):
   z=(positions[j]+positions[j+1])/2
   g.arch('trim',(x,3.85,z),1.35,1.62,.57,steps=17,orientation=90,tint=.96)
   # Spandrel stones above arches leave real voids below.
   for k in range(4):g.block('masonry',(x,5.38,z-1.25+k*.83),(.72,.54,.80),.024,tint=.94,metres=2.8)
  for y,w,h in ((5.1,.98,.16),(5.7,1.05,.19),(5.9,1.14,.16)):
   g.block('trim',(x,y,-4.65),(w,h,17.6),.025,metres=2.1,tint=.94)
  # Low relief egg-and-dart / geometric ornament under the upper cornice.
  for j in range(48):
   z=3.7-j*.36
   if z<-12.8:continue
   g.block('trim',(x-side*.52,5.57,z),(.075,.19,.19),.018,q=euler(0,0,side*5),tint=.85,metres=1.1)
 # Three high transverse barrel ribs, the middle one partially collapsed.
 for rib,z in enumerate((2.55,-4.75,-11.75)):
  if rib==1:
   g.arch('trim',(0,4.3,z),3.12,3.42,.50,start=0,end=math.pi*.38,steps=9,tint=.92)
   g.arch('trim',(0,4.3,z),3.12,3.42,.50,start=math.pi*.76,end=math.pi,steps=6,tint=.94)
  else:g.arch('trim',(0,4.3,z),3.12,3.42,.54,steps=27,tint=.94)
 # Side aisle roof sections give the sun actual occluders and pools of shade.
 for side in (-1,1):
  for j in range(5):
   z=2.1-j*3.6
   if side<0 and j in (0,2):continue
   g.block('masonry',(side*4.0,5.10,z),(1.6,.28,3.25),.025,metres=2.6,tint=.86)
 # Incomplete nave roof: ribbed slabs above the entry and at the far end only.
 for z in (2.8,1.8,-10.65,-11.65):
  g.block('masonry',(-1.05,6.25,z),(3.65,.23,.95),.035,q=euler(0,0,9),tint=.91)
 # Apse wall with its deep black doorway and decorative three-layer surround.
 for side in (-1,1):
  for row in range(8):
   for j in range(3):
    x=side*(1.7+j*1.05);y=.35+row*.66
    if y>4.9 and j>1:continue
    g.block('masonry',(x,y,-12.25),(1.0,.63,.72),.025,tint=.88+RNG.random()*.1,metres=3.)
 # Real thick-walled 2.4m-deep side-lit recess, with correctly oriented interior faces.
 # Closed boxes also occlude the sun from both sides during the shadow pass.
 g.box('recess',(0,-.11,-13.15),(2.3,.2,2.6))
 g.box('recess',(-1.22,1.975,-13.15),(.2,3.95,2.6))
 g.box('recess',(1.22,1.975,-13.15),(.2,3.95,2.6))
 g.box('recess',(0,4.05,-13.15),(2.3,.2,2.6))
 g.box('recess',(0,1.975,-14.5),(2.3,3.95,.2))
 g.box('recess',(0,.08,-13.85),(2.16,.16,.95),color=(.8,.78,.74,1))
 for layer in range(3):
  r=1.13+layer*.24
  g.arch('trim',(0,2.85,-11.74+layer*.055),r,r+.20,.30,steps=21,tint=.98-layer*.035)
  for side in (-1,1):g.block('trim',(side*(r+.10),1.43,-11.74+layer*.055),(.20,2.85,.30),.025,metres=2.)
 # Central sun rosette and concentric carved borders, above the doorway.
 g.rosette((0,4.62,-11.66),.59,petals=16,relief=.055)
 for radius,width in ((.66,.035),(.76,.045)):
  g.ring('trim',(0,4.62,-11.69),radius,radius+width,80,q=euler(90,0,0),color=(.95,.89,.80,1))
 # A long repeated relief frieze gives a strong close-up of real silhouette detail.
 for side in (-1,1):
  for j in range(15):
   x=side*(1.8+j*.18)
   if abs(x)>4.6:continue
   g.block('trim',(x,4.25,-11.76),(.13,.16,.11),.014,q=euler(0,0,45 if j%2 else 0),tint=.91,metres=1.1)
 # Altar with chamfered mouldings and stepped pedestal; passage remains around it.
 for y,size in ((.07,(2.55,.14,1.48)),(.20,(2.28,.16,1.23)),(.39,(1.87,.22,.99)),(.65,(1.62,.30,.87)),(.84,(1.94,.10,1.10)),(.94,(2.13,.10,1.22))):
  g.block('trim',(0,y,-9.45),size,.035,metres=1.65,tint=.93)
 g.rosette((0,.66,-8.99),.23,petals=10,relief=.035)
 for side in (-1,1):
  # Metal braziers near the apse create believable warm reflected local light.
  c=(side*1.82,0,-9.72)
  g.lathe('bronze',c,[(.03,.20,.20),(.09,.20,.20),(.16,.12,.12),(.96,.06,.06),(1.06,.16,.16),(1.18,.26,.26),(1.28,.28,.28)],24)
  g.ellipsoid('flame_core',add(c,(0,1.35,0)),(.075,.18,.075),12,8)
  for k in range(7):
   a=k/7*TAU;g.tube('bronze',add(c,(math.cos(a)*.13,1.1,math.sin(a)*.13)),add(c,(math.cos(a)*.29,1.36,math.sin(a)*.29)),[.018,.012],6)
 return g


def floor():
 g=StoneMesh('Stone Sanctum - worn paving')
 g.pbr('paving','stone_floor',normal=.65,occlusion=.8)
 # Real scan tiles at calibrated repeating scale, on wide subtly chipped paving slabs.
 for zrow in range(15):
  z=4.5-zrow*1.12
  for xcol in range(8):
   x=-4.2+xcol*1.2+(RNG.uniform(-.022,.022))
   if (xcol in (0,7) and RNG.random()<.12):continue
   y=-.09+RNG.uniform(-.006,.004)
   g.block('paving',(x,y,z),(1.17,.16,1.085),.016,tint=RNG.uniform(.84,1.),metres=3.6,seed=100+zrow*8+xcol)
 return g


def rubble():
 g=StoneMesh('Stone Sanctum - fallen stone and canyon')
 g.pbr('rock','sandstone_cracks',normal=.7,occlusion=.75)
 g.pbr('blocks','sandstone_blocks_04',normal=.65,occlusion=.75)
 # Fallen side column and detached carved drums, away from the central route.
 for j in range(6):
  x=2.6+j*.13;z=-.9-j*.48
  g.block('rock',(x,.28,z),(.66,.51,.67),.07,q=euler(RNG.uniform(-12,12),RNG.uniform(-28,28),RNG.uniform(-9,9)),tint=RNG.uniform(.79,.96),metres=1.8,seed=j)
 # Rubble only along margins, no boulders hidden under the walking route.
 for i in range(110):
  side=-1 if i%2 else 1;x=side*RNG.uniform(3.8,4.5);z=RNG.uniform(-11.4,3.8);scale=RNG.uniform(.09,.45)
  if i<12:scale=RNG.uniform(.4,.8)
  g.rock('rock',(x,scale*.18,z),(scale,scale*.5,scale*.8),i+992)
 # Displaced masonry blocks and fragments at the open entrance.
 for i in range(18):
  side=-1 if i%2 else 1;x=side*RNG.uniform(2.9,5.8);z=RNG.uniform(4.8,8.2);s=RNG.uniform(.28,.75)
  g.block('blocks',(x,s*.24,z),(s,.48*s,s*.8),.06,q=euler(RNG.uniform(-16,16),RNG.uniform(0,180),RNG.uniform(-12,12)),tint=.9,metres=2.8,seed=i)
 # Eroded canyon walls extend beyond the reachable room and frame the broken vault.
 for side in (-1,1):
  for i in range(7):
   x=side*(7.8+RNG.uniform(0,1.1));z=4-i*3.3;y=3.9+RNG.uniform(-.8,1.4)
   g.rock('rock',(x,y,z),(4.5,RNG.uniform(8.,12.),4.9),2340+i+(10 if side>0 else 0),detail=14)
 # Behind the apse, a natural slope catches warm light above the roof line.
 for i in range(5):g.rock('rock',(-7+i*3.5,5.4+RNG.uniform(-.8,1.8),-16.5),(6.,11.,5.),1800+i,detail=14)
 return g

WORLD={
 'version':'0.1','id':'stone-sanctum','name':'STONE SANCTUM - The Sunlit Archive',
 'elements':'scene.element','style':'appearance.style','scripts':[],
 'extensions':['models-v1','lighting-v1'],
 'entry':{'position':[2.15,1.68,3.2],'target':[-.45,2.15,-7.8]},
 'views':[
  {'name':'Entry - nave and carved apse','position':[2.15,1.68,3.2],'target':[-.45,2.15,-7.8]},
  {'name':'Stone detail - capital and relief','position':[-1.55,2.25,-8.1],'target':[-3.28,3.35,-8.4]},
  {'name':'Corridor - pillars and broken vault','position':[-3.85,1.68,2.8],'target':[-3.7,2.55,-9.9]},
  {'name':'Altar - layered doorway and sun carving','position':[1.55,1.82,-6.75],'target':[0,2.7,-11.7]}],
 'environment':{'background':'#B5C4CD','grid':False,'fog':{'color':'#B5C4CD','start':28,'end':65},'lighting':{
  'sunDirection':[-.55,.78,.30],'sunColor':'#FFF0D9','sunIntensity':3.2,
  'skyColor':'#9BBBD6','groundColor':'#5E4B36','ambientIntensity':.12,'exposure':.9,
  'environmentMap':'lighting/quarry_01_1k.hdr','environmentIntensity':.28,
  'shadow':{'enabled':True,'resolution':2048,'center':[0,2,-4.6],'extent':16,'bias':.0015,'normalBias':.02},
  'points':[{'position':[-1.82,1.5,-9.72],'color':'#FFAC58','intensity':12,'range':4.2},{'position':[1.82,1.5,-9.72],'color':'#FFAC58','intensity':12,'range':4.2},{'position':[.65,1.6,-13.2],'color':'#FFD2A0','intensity':2.5,'range':2.8}]}},
 'walk':{'min':[-2.65,0,-8.2],'max':[2.65,3,3.8],'eyeHeight':1.68,'speed':1.8}}
SCENE="""// Original architecture. PBR maps and HDR environment: Poly Haven CC0.
scene {
 object stone_sanctum {
  name: "STONE SANCTUM - The Sunlit Archive";
  component sanctuary {
   name: "Weathered nave, arcade and carved apse";
   raycast:false;
   element architecture_model { geometry:{type:"model",source:"models/sanctuary.glb"};style:"stone"; }
   element paving_model { geometry:{type:"model",source:"models/paving.glb"};style:"stone"; }
   element rubble_model { geometry:{type:"model",source:"models/rubble.glb"};style:"stone"; }
  }
 }
}
"""
STYLE="""defaults { color:"#FFFFFF";opacity:1;emission:0; }
material stone { color:"#FFFFFF";shading:"pbr";outline:0; }
"""

def write_world():
 lines=['world {']
 for key,value in WORLD.items():lines.append(' '+key+':'+json.dumps(value,separators=(',',':'))+';')
 lines.append('}')
 (ROOT/'world.link').write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
 (ROOT/'scene.element').write_text(SCENE,encoding='utf-8',newline='\n')
 (ROOT/'appearance.style').write_text(STYLE,encoding='utf-8',newline='\n')

def main():
 global RNG
 RNG=random.Random(307171)
 manifest=json.loads((SOURCE/'polyhaven-materials.json').read_text(encoding='utf-8'))
 for asset in manifest['assets']:
  for item in asset['files']:
   p=SOURCE/item['path'];assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256'],p
 (ROOT/'models').mkdir(exist_ok=True)
 reports=[]
 for name,generate in [('sanctuary',architecture),('paving',floor),('rubble',rubble)]:
  g=generate();report=g.save(ROOT/'models'/(name+'.glb'))
  embedded=sum(g.doc['bufferViews'][im['bufferView']]['byteLength'] for im in g.doc['images'])
  assert embedded<=8*1024*1024,(name,'compressed image budget',embedded)
  assert report['bytes']<=16*1024*1024,(name,'file budget')
  report['compressedImageBytes']=embedded;reports.append(report)
 write_world()
 report={'world':'stone-sanctum','generator':'tools/generate_stone_sanctum.py','geometryLicense':'Apache-2.0','textures':'Poly Haven CC0-1.0','assets':reports,'totalVertices':sum(r['vertices'] for r in reports),'totalTriangles':sum(r['triangles'] for r in reports)}
 assert report['totalVertices']<=200000 and report['totalTriangles']<=200000
 (ROOT/'asset-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
