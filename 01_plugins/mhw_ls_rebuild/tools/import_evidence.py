"""Read the user's World and GU data; generate stage-B execution definitions.

This importer does not import a previous moveset controller or edit game data.
The two-bit input-window interpretation remains explicitly provisional.
"""
from pathlib import Path
import hashlib
import json
import struct
import sys

ROOT=Path(r"C:\gumod")
PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/".cache/mhw_anim_tools_core"))
sys.path.insert(0,str(ROOT/"05_reference/MHGURecomp/tools"))
from core.formats.lmt.reader import read_lmt_file
from core.formats.lmt.decoder import decode_action_tracks
from core.formats.timl.reader import read_timl_data_bytes
from core.formats.timl.semantics import TIMELINE_PARAMETER_LABELS, DATATYPE_HASH_LABELS
from nso import Nso

world=Path(r"D:\MHW_extract\MHW_LS_WORLD\hm\wp\wp03\mot\w03_00\w03_00.lmt")
fsm=Path(r"C:\gumod\.cache\ls_world_retarget\mhw_fsm\wp03_action.fsm.json")
gu=ROOT/"Windows-MHGURecomp/data/exefs/main"
gu_lmt=ROOT/"04_assets/hit_w07/player/mot/w07/w07"
nso=Nso(gu)
assert nso.build_id.startswith('fb08f1d20fd1204f')
raw=world.read_bytes(); target=gu_lmt.read_bytes()
lm=read_lmt_file(world); actions={a.id:a for a in lm.actions}
graph=json.loads(fsm.read_text(encoding="utf8"))
report={"status":"stage-B prototype, not World behavior certification",
 "sources":{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [world,fsm,gu,gu_lmt]},
 "gu_build_id":nso.build_id,"world_lmt_version":lm.header.version,
 "fsm_nodes":graph['root']['mpRootCluster']['mpNodeList'],
 "condition_trees":graph['root']['mpConditionTree']['mpTreeList'],
 "notes":["Window pair semantics and World/GU time correspondence remain candidates.",
          "GU28/29 are lateral fades; GU48 plays the Spirit Step clip.",
          "Native action identity, binding generation and semantic state are separate."],"moves":[]}

# (semantic, World clip, GU action, expected GU clip, descriptor offset/optional)
rows=[('THRUST',105,4,105,None),('FADE_BACK',103,8,103,0x182624c),
      ('FADE_LEFT',127,29,128,0x182699c+24),('FADE_RIGHT',128,28,129,0x182699c),
      ('SPIRIT_STEP',110,48,130,0x182693c),('SPIRIT_III',108,26,108,0x182684c),
      ('ROUND',109,30,127,None),('UPPER',107,7,107,None)]
generated=[]
for ident,(name,source,native,clip,descriptor) in enumerate(rows,1):
 a=actions[source]
 offset=struct.unpack_from('<I',target,8+4*clip)[0]
 frames=struct.unpack_from('<I',target,offset+8)[0]
 assert frames==a.header.frame_count,(name,frames,a.header.frame_count)
 if descriptor is not None:assert nso.u32(descriptor)==5000+clip,(name,hex(descriptor))
 data=read_timl_data_bytes(raw,data_offset=a.header.timl_offset,entry_id=source)
 tracks={}
 for typ in data.types:
  if TIMELINE_PARAMETER_LABELS.get(typ.timeline_parameter_hash)!='PlMotionInput':continue
  for track in typ.transforms:
   tracks[DATATYPE_HASH_LABELS.get(track.datatype_hash,hex(track.datatype_hash))]=[(k.frame_timing,int(k.value)) for k in track.keyframes]
 keys=tracks['mFlag']
 shift=14 if name in ['ROUND','SPIRIT_III'] else 30
 pairs=[]
 for t,v in keys:
  value=(v>>shift)&3
  if not pairs or pairs[-1][1]!=value:pairs.append((t,value))
 opens=[t for t,v in pairs if v==3]
 opened=opens[-1] if name=='SPIRIT_III' else opens[0]
 buffered=max(t for t,v in pairs if v==1 and t<=opened)
 decoded=decode_action_tracks(a)
 root=next(t for t in decoded.tracks if t.bone_id==-1 and t.usage==4)
 item={"semantic":name,"world_clip":source,"gu_action":native,"gu_clip":clip,
       "frames":frames,"buffer_candidate":buffered,"open_candidate":opened,
       "raw_input":tracks,"world_root_end":root.tail_value,
       "descriptor":hex(descriptor) if descriptor else None}
 report['moves'].append(item)
 generated.append(f'    {{ ML_{name}, {source}u, {native}u, {clip}u, {frames}.0f, {buffered:.1f}f, {opened:.1f}f }},')
assert report['moves'][2]['world_root_end'][0]<0<report['moves'][3]['world_root_end'][0]
slots={0x324:0x11998b0,0x318:0x2cbfcc,0x31c:0x2e5810,0xc4:0x2a1d8c,0x2f8:0x119f7a0}
for off,value in slots.items():assert nso.u32(0x174cf64+off)==value
report['vtable_guards']={hex(k):hex(v) for k,v in slots.items()}
report['request_guard']=[hex(nso.u32(0x2ab670+i*4)) for i in range(2)]
(PROJECT/'c/source_moves.h').write_text('/* Generated from local source files by tools/import_evidence.py. */\nstatic const MLMove ml_moves[] = {\n'+ '\n'.join(generated)+'\n};\n',encoding='utf8')
(PROJECT/'research/source_evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
print('Verified 8 semantic/native bindings; captured raw World input, root motion and FSM evidence.')
