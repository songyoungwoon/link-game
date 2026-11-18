"""Original ASTERFALL world. All geometry, palette and game presentation are authored here.

Re-run with Python 3; no downloaded image, mesh, font asset or external package is used.
Server snapshots own every combat and progress decision. Scripts only present that state.
"""
from pathlib import Path
import json
import math
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT))
from server.world_data import BOUNDS, SPAWNS, RESOURCE_SPAWNS

ROOT = Path(__file__).resolve().parents[1] / "worlds" / "link-game"

class Scene:
    def __init__(self): self.roots = []; self.count = 0
    def node(self, kind, identifier, parent=None, **fields):
        self.count += 1
        node = [kind, identifier, fields, []]
        (self.roots if parent is None else parent[3]).append(node)
        return node
    def component(self, identifier, parent, **fields): return self.node("component", identifier, parent, **fields)
    def element(self, identifier, parent, shape, material, position=(0,0,0), **fields):
        return self.node("element", identifier, parent, geometry=shape, style=material, position=list(position), **fields)
    def box(self, identifier, parent, size, material, position=(0,0,0), **fields):
        return self.element(identifier,parent,{"type":"box","size":list(size)},material,position,**fields)
    def sphere(self, identifier, parent, radius, material, position=(0,0,0), **fields):
        return self.element(identifier,parent,{"type":"sphere","radius":radius},material,position,**fields)
    def cylinder(self, identifier, parent, radius, top, height, material, position=(0,0,0), **fields):
        return self.element(identifier,parent,{"type":"cylinder","radius":radius,"radiusTop":top,"height":height},material,position,**fields)
    def text(self, identifier, parent, size, content, position, material="letter", **fields):
        return self.element(identifier,parent,{"type":"plane","size":list(size)},material,position,text=content,raycast=False,**fields)
    def render(self):
        seen=set()
        def emit(node,depth):
            kind,key,fields,children=node
            if key in seen: raise ValueError("Duplicate Element ID: "+key)
            seen.add(key);pad="  "*depth
            out=[f"{pad}{kind} {key} {{"]
            for field,val in fields.items(): out.append(f"{pad}  {field}: {json.dumps(val,ensure_ascii=False,separators=(',',':'))};")
            for child in children: out.extend(emit(child,depth+1))
            out.append(pad+"}");return out
        out=["// Original procedural ASTERFALL scene; reproducible via tools/generate_world.py.","scene {"]
        for root in self.roots: out.extend(emit(root,1))
        out.append("}")
        return "\n".join(out)+"\n"

scene=Scene()
world=scene.node("object","asterfall",name="ASTERFALL · The Open Meadow")
land=scene.component("meadow_landscape",world,raycast=False)
# The entire walk rectangle has level ground. Hills and cliffs are scenery.
scene.box("meadow_island",land,[242,14,252],"cliff",(0,-7.2,-15))
scene.box("meadow_surface",land,[242,.4,252],"grass",(0,-.2,-15))
scene.box("old_pilgrims_road",land,[5.0,.035,220],"path",(0,.02,-20))
scene.box("spawn_plaza",land,[16,.045,18],"paving",(0,.027,26))
def path_segment(identifier,start,end,width=3.6):
    dx=end[0]-start[0];dz=end[1]-start[1]
    scene.box(identifier,land,[width,.026,math.hypot(dx,dz)],"path",((start[0]+end[0])/2,.025,(start[1]+end[1])/2),rotation=[0,math.degrees(math.atan2(dx,dz)),0])
path_segment("forest_trail",(0,10),(-66,-25))
path_segment("ruins_trail",(0,-24),(64,-33))
path_segment("garden_trail",(0,48),(-27,80))
path_segment("east_meadow_trail",(0,40),(60,66),2.8)
for index,(x,z,sx,sy,sz) in enumerate([(-131,-65,25,20,48),(130,-50,26,28,42),(-70,-145,50,20,18),(78,-145,46,23,20),(-121,92,28,16,27),(120,91,28,21,25)]):
    scene.sphere(f"meadow_rise_{index}",land,1,"hill",(x,-8,z),scale=[sx,sy,sz])
for index,(x,z,scale) in enumerate([(-35,5,3.0),(36,1,2.5),(-94,-75,5.5),(90,-103,6.5),(-95,71,4.3),(71,86,4.1)]):
    scene.sphere(f"weathered_boulder_{index}",land,1,"rock",(x,.4,z),scale=[scale,scale*.65,scale*.85],rotation=[0,index*37,13])

sky=scene.component("distant_evening",world,raycast=False)
scene.sphere("evening_sun",sky,22,"sun",(-90,55,-225))
scene.sphere("first_evening_star",sky,1.5,"rune",(70,69,-240))
for index,(x,y,z) in enumerate([(-106,47,-148),(94,52,-180),(-42,61,-255),(125,34,55)]):
    scene.sphere(f"evening_cloud_{index}",sky,1,"cloud",(x,y,z),scale=[28+index*5,3.1,9])

ancient=scene.component("mother_of_the_meadow",world,position=[-70,0,-28],raycast=False)
scene.cylinder("ancient_trunk",ancient,2.7,1.45,32,"bark",(0,16,0),rotation=[0,0,-6])
for index,(x,y,z,angle) in enumerate([(-4,23,0,51),(4.2,26,-1,-48),(1,28,4,35)]):
    scene.cylinder(f"ancient_branch_{index}",ancient,1.0,.35,16,"bark",(x,y,z),rotation=[17,0,angle])
for index,(x,y,z,sx,sy,sz) in enumerate([(-9,33,0,17,5.1,12),(5,37,-1,17,5,13),(-1,41,2,14,4.2,12)]):
    scene.sphere(f"ancient_crown_{index}",ancient,1,"forest_canopy",(x,y,z),scale=[sx,sy,sz])
scene.text("forest_waymark",ancient,[8.0,.65],"WEST / THE WHISPERWOOD",[0,5,8],"letter")
for index,(x,z,height) in enumerate([(-35,-14,12),(-50,-50,16),(-89,-21,17),(-95,-55,14),(-75,15,15),(-106,8,12),(-52,2,11),(36,28,12),(70,42,14),(-66,81,13)]):
    tree=scene.component(f"meadow_tree_{index}",world,position=[x,0,z],raycast=False)
    scene.cylinder(f"tree_trunk_{index}",tree,.58,.27,height,"bark",(0,height/2,0))
    scene.sphere(f"tree_crown_{index}",tree,1,"forest_canopy" if x<0 else "canopy",(0,height,0),scale=[height*.54,height*.32,height*.47])

ruins=scene.component("the_unfinished_gate",world,position=[0,0,-125],raycast=False)
scene.box("warden_court",ruins,[28,.055,23],"paving",(0,.032,9))
for index in range(14):
    angle=2*math.pi*index/14
    scene.box(f"ancient_ring_{index:02}",ruins,[4.7,1.0,2.3],"ruin",(10.5*math.cos(angle),10.7+10.5*math.sin(angle),0),rotation=[0,0,round(math.degrees(angle)+90,4)])
for side in [-1,1]:
    label="left" if side<0 else "right"
    scene.cylinder("gate_anchor_"+label,ruins,1.7,1.1,7,"ruin",(side*13,3.5,0))
    scene.sphere("gate_fire_"+label,ruins,.38,"rune",(side*13,7.3,0))
scene.text("sanctum_waymark",ruins,[10,.75],"NORTH / THE DAWN SANCTUM",[0,3,2],"letter")

hall=scene.component("eastern_observatory",world,position=[64,0,-33],raycast=False)
scene.box("observatory_floor",hall,[24,.06,20],"paving",(0,.025,0))
scene.box("observatory_roof",hall,[23,.6,19],"roof",(0,7.0,0))
for index,(x,z) in enumerate([(-9,-7),(0,-7),(9,-7),(-9,7),(0,7),(9,7)]):
    scene.cylinder(f"observatory_column_{index}",hall,.65,.49,6.7,"ruin",(x,3.35,z))
scene.box("observatory_arch_left",hall,[1.1,4.8,1.2],"ruin",(-3.8,2.4,-6))
scene.box("observatory_arch_right",hall,[1.1,4.8,1.2],"ruin",(3.8,2.4,-6))
scene.box("observatory_arch_top",hall,[8.7,1.0,1.2],"ruin",(0,4.8,-6))
scene.sphere("observatory_oracle",hall,.65,"rune",(0,1.4,-2))
scene.text("observatory_waymark",hall,[8,.6],"EAST / THE OPEN OBSERVATORY",[0,5.8,8],"letter")

shore=scene.component("southern_gardens",world,position=[-28,0,80],raycast=False)
scene.element("garden_pool",shore,{"type":"plane","size":[37,25]},"water",(0,.022,0),rotation=[-90,0,0])
scene.box("garden_bridge",shore,[4.0,.09,30],"wood",(0,.045,0))
for side in [-1,1]:
    scene.box("garden_bridge_rail_"+str(side).replace("-","m"),shore,[.12,.12,28],"gold",(side*2.1,.9,0))
    scene.box("garden_bridge_post_"+str(side).replace("-","m"),shore,[.18,.95,.18],"wood",(side*2.1,.475,-10))
scene.box("garden_pavilion_roof",shore,[12,.4,8],"roof",(0,4.6,21))
for index,(x,z) in enumerate([(-5,18),(5,18),(-5,24),(5,24)]):
    scene.cylinder(f"garden_pavilion_column_{index}",shore,.35,.3,4.4,"ruin",(x,2.2,z))
scene.text("garden_waymark",shore,[8,.55],"SOUTH / THE STILLWATER GARDENS",[0,3.2,-13],"letter")

camp=scene.component("arrival_camp",world,raycast=False)
scene.cylinder("camp_hearth",camp,.65,.65,.18,"rock",(-6,.09,27))
scene.sphere("camp_fire",camp,.33,"fire",(-6,.42,27),scale=[1,1.55,1])
scene.box("camp_bench",camp,[2.1,.3,.65],"wood",(-7.8,.42,28.8),rotation=[0,-25,0])
scene.box("camp_shelter_back",camp,[4,1.7,.14],"canvas",(-11,.9,29),rotation=[0,-12,0])
scene.box("camp_shelter_roof",camp,[4.5,.12,3.3],"canvas",(-11,2.1,28),rotation=[10,-12,0])
scene.text("world_title",camp,[6.8,1.1],"ASTERFALL\nTHE OPEN MEADOW",[-6.2,4.1,13],"title")
scene.text("world_welcome",camp,[6.5,.3],"Gather. Wander. Return with a story.",[-6.2,3.25,13],"letter")

# Interaction targets and positions exactly match the authoritative server contract.
def altar(identifier,position,weapon,label,material):
    node=scene.component(identifier,world,position=list(position),script="scripts/interaction.script",config={"action":"equip","target":identifier})
    scene.cylinder(identifier+"_base",node,.6,.52,.32,"ruin",(0,.16,0))
    scene.box(identifier+"_blade",node,[.075,.8,.035],material,(0,1.0,0),rotation=[0,0,5])
    scene.box(identifier+"_guard",node,[.38,.045,.09],"gold",(-.03,.62,0))
    scene.cylinder(identifier+"_grip",node,.04,.04,.22,"wood",(-.03,.47,0))
    scene.sphere(identifier+"_pommel",node,.065,material,(-.03,.34,0))
    scene.text(identifier+"_label",node,[1.45,.26],label,[0,.47,.7],"inscription")
    return node
altar("starter_altar",[0,0,24],"starter","WAYFARER\nStarter Sword","steel")
altar("iron_altar",[3,0,24],"iron","IRON OATH\nFree to claim","iron")
altar("star_altar",[-3,0,24],"star","DAWNSONG\nQuest I / 100 G","star")
rest=scene.component("rest_shrine",world,position=[0,0,30],script="scripts/interaction.script",config={"action":"rest","target":"rest_shrine"})
scene.cylinder("rest_shrine_base",rest,.85,.75,.35,"ruin",(0,.175,0))
scene.sphere("rest_shrine_heart",rest,.3,"healing",(0,.95,0))
scene.text("rest_shrine_label",rest,[1.8,.25],"REST / HEAL",[0,1.35,.3],"letter")
quest=scene.component("quest_stone",world,position=[0,0,20],script="scripts/interaction.script",config={"action":"claim","target":"quest_stone"})
scene.cylinder("quest_stone_base",quest,1.05,.9,.35,"ruin",(0,.175,0))
scene.box("quest_stone_tablet",quest,[1.15,1.65,.4],"ruin",(0,1.05,0),rotation=[0,0,-4])
scene.box("quest_stone_rune",quest,[.065,.95,.04],"rune",(0,1.1,.23))
scene.text("quest_stone_label",quest,[1.8,.55],"MEADOW CALLS\nDefeat five creatures.\nThen face the Warden.",[0,1.15,.25],"inscription")

MONSTERS=SPAWNS
for index,(identifier,kind,x,z) in enumerate(MONSTERS):
    colors={"slime":"#8BC7A8","wolf":"#A4A9AF","golem":"#A0B1A4","warden":"#D6B888"}
    names={"slime":"Meadow Wisp","wolf":"Bramble Wolf","golem":"Mossbound","warden":"The First Warden"}
    body_height={"slime":.65,"wolf":.85,"golem":1.2,"warden":1.65}[kind]
    m=scene.component(identifier,world,name=names[kind],position=[x,0,z],visible=False,script="scripts/monster.script",config={"index":index,"target":identifier,"kind":kind,"x":x,"z":z,"phase":index*.83,"bodyHeight":body_height,"color":colors[kind]})
    body=scene.component(identifier+"_body",m,position=[0,body_height,0])
    if kind=="slime":
        scene.sphere(identifier+"_skin",body,.68,"slime",scale=[1.1,.85,1])
        scene.sphere(identifier+"_eye_left",body,.065,"eye",(-.23,.1,.58))
        scene.sphere(identifier+"_eye_right",body,.065,"eye",(.23,.1,.58))
        scene.sphere(identifier+"_heart",body,.12,"healing",(0,.28,.53))
    elif kind=="wolf":
        scene.sphere(identifier+"_skin",body,.62,"wolf",scale=[.75,.85,1.7])
        scene.sphere(identifier+"_muzzle",body,.35,"wolf",(0,.32,.91),scale=[.82,.86,1.2])
        for side in [-1,1]: scene.sphere(identifier+"_wolf_eye_"+("left" if side<0 else "right"),body,.045,"eye",(side*.13,.46,1.19))
        for side in [-1,1]: scene.cylinder(identifier+"_ear_"+("l" if side<0 else "r"),body,.15,0,.4,"wolf",(side*.24,.72,.86),rotation=[0,0,side*-12])
        for leg_name,leg_z in [("front",.65),("back",-.65)]:
            joint=scene.component(identifier+"_"+leg_name,m,position=[0,.6,leg_z])
            for side in [-1,1]: scene.box(identifier+"_"+leg_name+("_l" if side<0 else "_r"),joint,[.18,.65,.22],"wolf",(side*.4,-.22,0))
    else:
        large=1.38 if kind=="warden" else 1
        scene.box(identifier+"_skin",body,[1.05*large,1.3*large,.7*large],"warden" if kind=="warden" else "golem")
        scene.box(identifier+"_head",body,[.65*large,.55*large,.6*large],"ruin",(0,.98*large,0))
        scene.box(identifier+"_gaze",body,[.45*large,.06*large,.04],"rune",(0,1.04*large,.32*large))
        for side in [-1,1]:
            label="left" if side<0 else "right"
            arm=scene.component(identifier+"_"+label,body,position=[side*.83*large,.38*large,0])
            scene.box(identifier+"_"+label+"_fist",arm,[.43*large,1.1*large,.5*large],"warden" if kind=="warden" else "golem",(0,-.42*large,0))
            scene.box(identifier+"_leg_"+label,m,[.44*large,.85*large,.57*large],"ruin",(side*.34*large,.425*large,0))
    health=scene.component(identifier+"_health",m,position=[0,2.3 if kind in ["slime","wolf"] else (4.3 if kind=="warden" else 3.2),0],raycast=False)
    scene.box(identifier+"_hp_bg",health,[1.12,.065,.035],"hp_back")
    scene.box(identifier+"_hp",health,[1.04,.045,.045],"hp",(0,0,.025))
    if kind in ("golem","warden"): scene.text(identifier+"_name",health,[2.5,.25],names[kind],[0,.23,0],"letter")

for index,(identifier,kind,x,z) in enumerate(RESOURCE_SPAWNS):
    plant=scene.component(identifier,world,name={"moonleaf":"달빛잎","sunbloom":"햇살꽃","wildberry":"산딸기"}[kind],position=[x,0,z],visible=False,script="scripts/gather.script",config={"index":index,"target":identifier,"kind":kind})
    scene.cylinder(identifier+"_stem",plant,.055,.035,.6,"plant_stem",(0,.3,0))
    if kind=="moonleaf":scene.sphere(identifier+"_bloom",plant,.36,"moonleaf",(0,.57,0),scale=[1.3,.48,1.5],rotation=[0,index*37,18])
    elif kind=="sunbloom":scene.sphere(identifier+"_bloom",plant,.34,"sunbloom",(0,.77,0),scale=[1,.65,1])
    else:scene.sphere(identifier+"_bloom",plant,.4,"wildberry",(0,.5,0),scale=[1.3,.85,1.1])

for slot in range(8):
    prefix=f"party_{slot}"
    p=scene.component(prefix,world,name=f"Explorer slot {slot+1}",visible=False,script="scripts/player.script",config={"slot":slot})
    body=scene.component(prefix+"_body",p)
    scene.box(prefix+"_torso",body,[.57,.65,.31],"traveler",(0,1.08,0))
    scene.sphere(prefix+"_head",body,.23,"skin",(0,1.68,0))
    scene.box(prefix+"_arm_left",body,[.18,.68,.2],"traveler",(-.4,1.1,0))
    scene.box(prefix+"_arm_right",body,[.18,.68,.2],"traveler",(.4,1.1,0))
    for side in [-1,1]: scene.box(prefix+("_leg_left" if side<0 else "_leg_right"),body,[.21,.72,.24],"boots",(side*.17,.39,0))
    scene.box(prefix+"_blade",body,[.06,.04,.95],"steel",(.45,.85,.47),rotation=[0,0,-8])
    scene.box(prefix+"_hp_bg",p,[.9,.055,.03],"hp_back",(0,2.17,0),raycast=False)
    scene.box(prefix+"_hp",p,[.84,.04,.04],"hp",(0,2.17,.015),raycast=False)
    scene.text(prefix+"_name",p,[1.9,.2],"Explorer",[0,2.43,0],"letter")

weapon=scene.component("weapon_control",world,visible=False,raycast=False,scale=[.7,.7,.7],state={"swing":0},script="scripts/weapon.script")
scene.box("held_blade",weapon,[.075,.035,1.05],"steel",(0,0,-.62))
scene.box("held_blade_edge",weapon,[.015,.045,.96],"blade_edge",(.028,0,-.61))
scene.box("held_guard",weapon,[.24,.025,.065],"gold",(0,0,-.075))
scene.cylinder("held_grip",weapon,.028,.028,.20,"wood",(0,0,.07),rotation=[90,0,0])
scene.sphere("held_pommel",weapon,.045,"gold",(0,0,.20))
hud=scene.component("journey_hud",world,raycast=False,state={"statusOpen":False},script="scripts/hud.script")
scene.element("journey_plate",hud,{"type":"plane","size":[1.92,.35]},"hud_back",(0,-.015,0))
scene.text("journey_status",hud,[1.78,.10],"ASTERFALL · 서버에 연결하는 중",[0,.085,.012],"hud")
scene.text("journey_notice",hud,[1.78,.18],"풍경을 둘러보며 잠시 기다려주세요.",[0,-.065,.012],"hud")
# The detailed personal menu starts hidden and stays outside selection rays.
status=scene.component("status_panel",world,visible=False,raycast=False)
scene.element("status_panel_back",status,{"type":"plane","size":[1.92,1.62]},"status_back")
scene.box("status_panel_rule",status,[1.72,.009,.008],"status_accent",(0,.455,.014))
scene.text("status_heading",status,[1.72,.13],"STATUS / INVENTORY",[0,.66,.018],"status_title")
scene.text("status_identity",status,[1.72,.12],"서버에 연결하는 중",[0,.51,.018],"hud")
scene.text("status_vitals",status,[1.72,.16],"HP — / —\nXP —",[0,.30,.018],"hud")
scene.text("status_equipment",status,[1.72,.11],"무기 —   ·   골드 —",[0,.12,.018],"hud")
scene.text("status_quest",status,[1.72,.15],"처치 —\n여정을 준비하고 있습니다",[0,-.05,.018],"hud")
scene.text("status_inventory",status,[1.72,.36],"INVENTORY\n가방이 비어 있습니다",[0,-.36,.018],"hud")
scene.text("status_help",status,[1.72,.07],"TAB / LEFT Y · CLOSE",[0,-.695,.018],"status_hint")


STYLE='''
defaults { color:"#C7C1AD";roughness:.86;metalness:0;opacity:1;emission:0; }
material grass {color:"#8B9B70";}
material forest_canopy {color:"#698B76";}
material roof {color:"#768F89";}
material water {color:"#619FAD";metalness:.25;roughness:.25;}
material plant_stem {color:"#578363";}
material moonleaf {color:"#A8E7D2";emission:.22;}
material sunbloom {color:"#F6CF72";emission:.2;}
material wildberry {color:"#B985B3";emission:.12;}
material hill {color:"#9AA87D";}
material cliff {color:"#776E6B";}
material far_cliff {color:"#8A7F7C";}
material path {color:"#BEA888";}
material path_edge {color:"#D8C099";}
material paving {color:"#B1AF99";}
material inlay {color:"#D7C4A0";}
material rock {color:"#929B8C";}
material ruin {color:"#B7B3A0";roughness:.96;}
material bark {color:"#79695A";}
material canopy {color:"#A3AD80";}
material leaf_light {color:"#BDC08D";}
material wood {color:"#705847";}
material canvas {color:"#B78F70";}
material flower {color:"#EDD59D";emission:.12;}
material cloud {color:"#EDD5BF";}
material sun {color:"#FFD4A6";emission:1.5;}
material rune {color:"#A5F2DE";emission:1.1;}
material fire {color:"#FFCC87";emission:1.7;}
material healing {color:"#8DE3C0";emission:.65;}
material gold {color:"#D6B77D";metalness:.45;}
material steel {color:"#C9D8DA";metalness:.65;roughness:.3;}
material iron {color:"#91B4B7";metalness:.7;roughness:.3;}
material star {color:"#A2EDDF";metalness:.55;emission:.7;}
material blade_edge {color:"#F3F4D6";emission:.35;}
material slime {color:"#8BC7A8";roughness:.6;}
material wolf {color:"#A4A9AF";}
material golem {color:"#A0B1A4";}
material warden {color:"#D6B888";metalness:.22;}
material eye {color:"#294449";}
material hp_back {color:"#454D49";}
material hp {color:"#81D8B4";emission:.22;}
material traveler {color:"#77B2B4";}
material boots {color:"#665A51";}
material skin {color:"#DBC7AD";}
material title {color:"#FFF0C8";textBackground:false;opacity:.97;}
material letter {color:"#FFF1D5";textBackground:false;opacity:.95;}
material hud {color:"#F8F1DD";textBackground:false;opacity:.98;}
material hud_back {color:"#1F3933";opacity:.45;}
material status_back {color:"#142C2B";opacity:.93;}
material status_accent {color:"#8DD8BC";emission:.3;}
material status_title {color:"#E3D3A3";textBackground:false;opacity:1;}
material status_hint {color:"#B1CCBF";textBackground:false;opacity:1;}
material inscription {color:"#294C40";textBackground:false;opacity:.96;}
'''
SCRIPTS={
"monster.script":r'''// Snapshot-only presentation. All damage, death, loot and respawns belong to the server.
on onStart(ctx) {
  store x = ctx.config.x;
  store z = ctx.config.z;
  store yaw = 180;
  store t = ctx.config.phase;
  store previousHp = 0;
  store previousAttack = 0;
  store wasAlive = false;
  store hurt = 0;
  store strike = 0;
}
on onUpdate(ctx, deltaSeconds) {
  t = t + deltaSeconds;
  hurt = max(0, hurt - deltaSeconds);
  strike = max(0, strike - deltaSeconds);
  let snapshot = ctx.getSharedState();
  if (snapshot == null) {
    ctx.setTransform({visible:false});
    wasAlive = false;
  } else {
    let monster = snapshot.monsters[ctx.config.index];
    let alive = monster.active && monster.hp > 0;
    ctx.setTransform({visible:alive});
    if (alive) {
      let targetYaw = monster.yaw + 180;
      if (!wasAlive) {
        x = monster.position[0];
        z = monster.position[2];
        yaw = targetYaw;
        previousHp = monster.hp;
        previousAttack = monster.attack;
      }
      let movement = clamp(abs(monster.position[0] - x) + abs(monster.position[2] - z), 0, 1);
      x = mix(x, monster.position[0], min(1, deltaSeconds * 11));
      z = mix(z, monster.position[2], min(1, deltaSeconds * 11));
      yaw = (yaw + ((targetYaw - yaw + 540) % 360 - 180) * min(1, deltaSeconds * 11) + 360) % 360;
      if (monster.hp < previousHp) { hurt = .22; }
      if (monster.attack > previousAttack) { strike = .34; }
      previousHp = monster.hp;
      previousAttack = monster.attack;
      let id = ctx.config.target;
      let pulse = sin((.34 - strike) / .34 * 3.14159265);
      let breathing = 1 + sin(t * 2.1) * .027;
      ctx.setTransform({position:[x,0,z],rotation:[0,yaw,0]});
      ctx.setTransform(id + "_body", {position:[0,ctx.config.bodyHeight + sin(t * 2.1) * .035 + abs(sin(t * 6)) * movement * .1,0],rotation:[pulse * 11,0,hurt * 27],scale:[breathing,1 / breathing,breathing]});
      if (hurt > 0) { ctx.setStyle(id + "_skin", {color:"#FFF3DF",emission:.3}); }
      else { ctx.setStyle(id + "_skin", {color:ctx.config.color,emission:0}); }
      if (ctx.config.kind == "wolf") {
        ctx.setTransform(id + "_front", {rotation:[sin(t * 8) * 29 * movement - pulse * 23,0,0]});
        ctx.setTransform(id + "_back", {rotation:[-sin(t * 8) * 29 * movement + pulse * 13,0,0]});
      }
      if (ctx.config.kind == "golem" || ctx.config.kind == "warden") {
        ctx.setTransform(id + "_left", {rotation:[sin(t * 4) * 12 * movement - pulse * 58,0,-5]});
        ctx.setTransform(id + "_right", {rotation:[-sin(t * 4) * 12 * movement - pulse * 74,0,5]});
      }
      let health = clamp(monster.hp / max(1, monster.maxHp), .001, 1);
      let viewer = ctx.getViewer();
      ctx.setTransform(id + "_health", {rotation:[0,viewer.rotation[1] - yaw,0]});
      ctx.setTransform(id + "_hp", {scale:[health,1,1]});
    }
    wasAlive = alive;
  }
}
on onInteract(ctx, event) {
  let snapshot = ctx.getSharedState();
  if (snapshot != null) {
    ctx.sendAction("attack", {target:ctx.config.target});
    let weapon = ctx.getState("weapon_control");
    ctx.setState("weapon_control", {swing:weapon.swing + 1});
  }
}
''',
"player.script":r'''// Stable slots are populated by the server; the local player never renders twice.
on onStart(ctx) {
  store x = 0;
  store z = 0;
  store y = 0;
  store yaw = 0;
  store t = ctx.config.slot;
  store wasActive = false;
  store previousRespawn = -1;
  store previousAttack = 0;
  store strike = 0;
}
on onUpdate(ctx, deltaSeconds) {
  t = t + deltaSeconds;
  strike = max(0,strike - deltaSeconds);
  let snapshot = ctx.getSharedState();
  if (snapshot == null) {
    ctx.setTransform({visible:false});
    wasActive = false;
  } else {
    let player = snapshot.players[ctx.config.slot];
    let separation = length(vsub(player.position,ctx.getViewer().position));
    let visible = player.active && player.id != snapshot.self.id && separation > .65;
    ctx.setTransform({visible:visible});
    if (visible) {
      let targetYaw = player.yaw + 180;
      if (!wasActive || player.respawn != previousRespawn) {
        x = player.position[0];z = player.position[2];y = player.position[1] - 1.65;
        yaw = targetYaw;
        previousAttack = player.attack;
      }
      let movement = clamp(abs(player.position[0] - x) + abs(player.position[2] - z),0,1);
      x = mix(x,player.position[0],min(1,deltaSeconds * 12));
      y = mix(y,player.position[1] - 1.65,min(1,deltaSeconds * 12));
      z = mix(z,player.position[2],min(1,deltaSeconds * 12));
      yaw = (yaw + ((targetYaw - yaw + 540) % 360 - 180) * min(1,deltaSeconds * 12) + 360) % 360;
      if (player.attack > previousAttack) { strike = .3; }
      previousAttack = player.attack;previousRespawn = player.respawn;
      let id = "party_" + str(ctx.config.slot);
      let pulse = sin((.3 - strike) / .3 * 3.14159265);
      ctx.setTransform({position:[x,y,z],rotation:[0,yaw,0]});
      if (player.hp > 0) {
        ctx.setTransform(id + "_body", {position:[0,abs(sin(t * 7)) * movement * .04,0],rotation:[0,0,sin(t * 3) * movement * 2]});
      } else {
        ctx.setTransform(id + "_body", {position:[0,.2,0],rotation:[85,0,0]});
      }
      ctx.setTransform(id + "_leg_left", {rotation:[sin(t * 7) * 19 * movement,0,0]});
      ctx.setTransform(id + "_leg_right", {rotation:[-sin(t * 7) * 19 * movement,0,0]});
      ctx.setTransform(id + "_arm_right", {rotation:[-pulse * 65,0,0]});
      ctx.setTransform(id + "_blade", {rotation:[-pulse * 65,0,-8]});
      let health = clamp(player.hp / max(1,player.maxHp),.001,1);
      let viewer = ctx.getViewer();
      ctx.setTransform(id + "_hp", {scale:[health,1,1],rotation:[0,viewer.rotation[1] - yaw,0],visible:player.hp > 0});
      ctx.setTransform(id + "_hp_bg", {rotation:[0,viewer.rotation[1] - yaw,0],visible:player.hp > 0});
      ctx.setTransform(id + "_name", {rotation:[0,viewer.rotation[1] - yaw,0]});
      ctx.setText(id + "_name",player.name + "  ·  Lv " + str(player.level));
      if (player.weapon == "star") { ctx.setStyle(id + "_blade", {color:"#A2EDDF",emission:.65}); }
      else { if (player.weapon == "iron") { ctx.setStyle(id + "_blade", {color:"#91B4B7",emission:0}); }
      else { ctx.setStyle(id + "_blade", {color:"#C9D8DA",emission:0}); } }
    }
    wasActive = visible;
  }
}
''',
"interaction.script":r'''// Requests describe intent only. The server validates distance, unlocks and costs.
on onInteract(ctx, event) {
  let snapshot = ctx.getSharedState();
  if (snapshot != null) { ctx.sendAction(ctx.config.action, {target:ctx.config.target}); }
}
''',
"gather.script":r'''// Gathering is a server-owned claim, never a client inventory write.
on onUpdate(ctx,deltaSeconds) {
  let snapshot = ctx.getSharedState();
  if (snapshot == null) { ctx.setTransform({visible:false}); }
  else {
    let plant = snapshot.resources[ctx.config.index];
    ctx.setTransform({visible:plant.active,position:plant.position});
  }
}
on onInteract(ctx,event) {
  let snapshot = ctx.getSharedState();
  if (snapshot != null) { ctx.sendAction("gather",{target:ctx.config.target}); }
}
''',
"weapon.script":r'''// The local hand pose comes from the desktop/VR viewer, never from a second avatar.
on onStart(ctx) {
  store swing = 0;
  store previousSwing = 0;
  store previousAttack = 0;
  store t = 0;
}
on onUpdate(ctx, deltaSeconds) {
  t = t + deltaSeconds;
  swing = max(0,swing - deltaSeconds);
  let snapshot = ctx.getSharedState();
  if (snapshot == null) { ctx.setTransform({visible:false}); }
  else {
    let self = snapshot.self;
    let state = ctx.getState();
    if (state.swing != previousSwing || self.attack > previousAttack) { swing = .3; }
    previousSwing = state.swing;previousAttack = self.attack;
    let viewer = ctx.getViewer();
    let pulse = sin((.3 - swing) / .3 * 3.14159265);
    ctx.setTransform({visible:self.hp > 0 && !ctx.getState("journey_hud").statusOpen,position:viewer.weaponPosition,rotation:[viewer.weaponRotation[0] + pulse * 67,viewer.weaponRotation[1] + pulse * 10,viewer.weaponRotation[2] - pulse * 17]});
    if (self.weapon == "star") { ctx.setStyle("held_blade", {color:"#A2EDDF",emission:.7}); }
    else { if (self.weapon == "iron") { ctx.setStyle("held_blade", {color:"#91B4B7",emission:.08}); }
    else { ctx.setStyle("held_blade", {color:"#C9D8DA",emission:0}); } }
  }
}
''',
"hud.script":r'''// Personal menus use semantic input; combat/progress still belong to the server.
on onStart(ctx) {
  store statusOpen = false;
  ctx.setState({statusOpen:false});
  ctx.setTransform("status_panel",{visible:false});
}
on onInput(ctx, event) {
  if (event.action == "menu" && event.phase == "pressed") {
    statusOpen = !statusOpen;
    ctx.setState({statusOpen:statusOpen});
    let viewer = ctx.getViewer();
    ctx.setTransform("status_panel",{visible:statusOpen,position:[viewer.position[0] + viewer.forward[0] * 2.35,viewer.position[1] + viewer.forward[1] * 2.35 - .05,viewer.position[2] + viewer.forward[2] * 2.35],rotation:viewer.rotation});
  }
}
on onUpdate(ctx, deltaSeconds) {
  let viewer = ctx.getViewer();
  ctx.setTransform({position:[viewer.position[0] + viewer.forward[0] * 2.6,viewer.position[1] + viewer.forward[1] * 2.6 - .84,viewer.position[2] + viewer.forward[2] * 2.6],rotation:viewer.rotation});
  if (statusOpen) {
    ctx.setTransform("status_panel",{position:[viewer.position[0] + viewer.forward[0] * 2.35,viewer.position[1] + viewer.forward[1] * 2.35 - .05,viewer.position[2] + viewer.forward[2] * 2.35],rotation:viewer.rotation});
  }
  let snapshot = ctx.getSharedState();
  if (snapshot == null) {
    ctx.setText("journey_status","ASTERFALL · 서버에 연결하는 중");
    ctx.setText("journey_notice","스테이터스: Tab / 왼손 Y");
    if (statusOpen) {
      ctx.setText("status_identity","서버에 연결하는 중");
      ctx.setText("status_vitals","HP — / —\nXP —");
      ctx.setText("status_equipment","무기 —   ·   골드 —");
      ctx.setText("status_quest","처치 —\n여정을 준비하고 있습니다");
      ctx.setText("status_inventory","INVENTORY\n서버에 연결하는 중");
    }
  } else {
    let self = snapshot.self;
    let region = "도착의 초원";
    if (viewer.position[2] < -75) { region = "새벽의 성소"; }
    else { if (viewer.position[2] > 55) { region = "고요한 정원"; }
    else { if (viewer.position[0] < -38) { region = "속삭이는 숲"; }
    else { if (viewer.position[0] > 38) { region = "열린 관측소"; } } } }
    ctx.setText("journey_status","Lv " + str(self.level) + "   HP " + str(self.hp) + "/" + str(self.maxHp) + "   ·   " + region);
    let progress = "초원의 부름 " + str(min(self.kills,5)) + "/5";
    if (self.quest == 1) { progress = "고대 원환 아래의 파수꾼을 이겨내세요"; }
    if (self.quest == 2) { progress = "THE FIRST MEADOW · 첫 여정 완수"; }
    if (self.hp <= 0) { progress = "잠시 후 야영지에서 다시 일어납니다"; }
    ctx.setText("journey_notice",progress + "   ·   Tab / Y: Inventory\n" + snapshot.notice + "\n");
    if (statusOpen) {
      let weapon = "여행자의 검";
      if (self.weapon == "iron") { weapon = "철검"; }
      if (self.weapon == "star") { weapon = "별검"; }
      ctx.setText("status_identity",self.name + "   ·   Lv " + str(self.level));
      ctx.setText("status_vitals","HP " + str(self.hp) + " / " + str(self.maxHp) + "\nXP " + str(self.xp));
      ctx.setText("status_equipment","무기 " + weapon + "   ·   골드 " + str(self.gold));
      ctx.setText("status_quest","처치 " + str(self.kills) + "\n" + progress);
      let bag = "INVENTORY";
      let entries = 0;
      for (let item of snapshot.inventory) {
        let itemName = "고대 조각";
        if (item.item == "moonleaf") { itemName = "달빛잎"; }
        if (item.item == "sunbloom") { itemName = "햇살꽃"; }
        if (item.item == "wildberry") { itemName = "산딸기"; }
        if (item.item == "slime_gel") { itemName = "슬라임 젤"; }
        if (item.item == "wolf_fang") { itemName = "늑대 송곳니"; }
        if (entries % 2 == 0) { bag = bag + "\n"; }
        else { bag = bag + "     ·     "; }
        bag = bag + itemName + " " + str(item.count);
        entries = entries + 1;
      }
      if (entries == 0) { bag = bag + "\n가방이 비어 있습니다\n꽃과 잎을 클릭하거나 트리거로 채집하세요"; }
      ctx.setText("status_inventory",bag);
    }
  }
}
'''
}

def generate():
    ROOT.mkdir(parents=True,exist_ok=True)
    (ROOT/"scripts").mkdir(exist_ok=True)
    source=scene.render()
    if scene.count>500: raise ValueError(f"World authoring budget exceeded: {scene.count}")
    if source.count("text:")>32: raise ValueError("Text-plane budget exceeded")
    (ROOT/"scene.element").write_text(source,encoding="utf-8")
    (ROOT/"appearance.style").write_text(STYLE.strip()+"\n",encoding="utf-8")
    for name,text in SCRIPTS.items(): (ROOT/"scripts"/name).write_text(text,encoding="utf-8")
    manifest={"version":"0.1","id":"link-game","name":"ASTERFALL · The Open Meadow","elements":"scene.element","style":"appearance.style","scripts":["scripts/"+name for name in SCRIPTS],"extensions":["shared-state-v1","input-v1"],"entry":{"position":[0,1.65,28],"target":[0,1.65,-8]},"environment":{"background":"#DCAF94","grid":False,"fog":{"color":"#DCAF94","start":135,"end":310}},"walk":{"min":BOUNDS["min"],"max":BOUNDS["max"],"eyeHeight":1.65,"speed":3.6}}
    (ROOT/"world.link").write_text("world {\n"+"\n".join("  "+key+": "+json.dumps(value,ensure_ascii=False,separators=(",",":"))+";" for key,value in manifest.items())+"\n}\n",encoding="utf-8")
    print(f"ASTERFALL: {scene.count} nodes, {len(SCRIPTS)} scripts, {len(source.encode('utf-8')):,} Element bytes")

if __name__=="__main__": generate()
