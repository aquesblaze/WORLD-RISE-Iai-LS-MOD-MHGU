"""Build an isolated ground-animation bank, preserving stock GU motions.

The inventory comes from native constructors/handlers and retained FSM helper
nodes. It is intentionally separate from the old deployed six-move build.
No root-path repair inferred from endpoints is applied here: the raw World
root/pose contract remains available for native trajectory comparison.
"""
import argparse
import json
import re
import struct
import sys
import animation_port as p
sys.path.insert(0,str(p.ROOT/'.cache/mhw_anim_tools_core'))
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
sys.path.insert(0,str(p.ROOT/'06_tools'))
from arc_tool import read_entries,unpack_one

OUT=p.ROOT/'.cache/mhw_ls_ground_rebuild'
COMMON=p.WORLD.parents[4]/'common/mot/co00_00/co00_00.lmt'

def source_actions():
    # Empty weapon slots resolve to the common hunter bank in World.
    result={a.id:(a,COMMON)for a in p.read_lmt_file(COMMON).actions}
    result.update({a.id:(a,p.WORLD)for a in p.read_lmt_file(p.WORLD).actions})
    return result

def inventory():
    native=json.loads((p.PROJECT/'research/world_ground_native.json').read_text(encoding='utf8'))
    graph=json.loads((p.PROJECT/'research/world_ground_contract.json').read_text(encoding='utf8'))
    text=(p.ROOT/'.cache/mhw_native/text.bin').read_bytes();cs=Cs(CS_ARCH_X86,CS_MODE_64)
    found={}
    def add(clip,evidence):
        if clip:found.setdefault(clip,[]).append(evidence)
    for name,row in native.items():
        if not name.startswith('nHmAction'):continue
        lines=[]
        for i in cs.disasm(text[row['factory']-4096:row['factory']-4096+256],0x140000000+row['factory']):
            if i.mnemonic=='int3':break
            lines.append(f'{i.address-0x140000000:08x} {i.mnemonic} {i.op_str}')
        for h in row['handlers'].values():lines+=h['instructions']
        for line in lines:
            m=re.search(r'^[0-9a-f]+ mov .*?, 0xc([01][0-9a-f]{2})$',line)
            if m:add(int(m[1],16),{'class':name,'instruction':line})
    for n in graph['nodes']:
        for proc in n['processes']:
            if proc['kind']=='link_motion':
                for key in ('motion','phase1_motion'):
                    if proc[key]>=0:add(proc[key],{'fsm_node':n['node'],'parameter':key})
    # Already established special-action handlers have rank-dependent IDs.
    for clip,slot,name in p.CLIPS:add(clip,{'special_action':name,'existing_slot':slot})
    return found

def plan():
    source=p.ROOT/'Windows-MHGURecomp/data/romfs/nativeNX/arc/player/quest/w07.arc'
    raw,_,entries=read_entries(source)
    row=next(e for e in entries if e['name'].replace('\\','/')=='player/mot/w07/w07')
    stock,_=unpack_one(raw,row);count=struct.unpack_from('<H',stock,6)[0]
    old={clip:slot for clip,slot,_ in p.CLIPS};used=set(old.values())
    free=[slot for slot in range(132,count) if slot not in used and not struct.unpack_from('<I',stock,8+slot*4)[0]]
    required=inventory();clips=[]
    actions=source_actions()
    for clip,evidence in sorted(required.items()):
        if clip not in actions:raise ValueError(('Missing original clip',clip))
        slot=old[clip] if clip in old else free.pop(0)
        a,path=actions[clip]
        clips.append({'world_clip':clip,'gu_slot':slot,'frames':a.header.frame_count,'source_bank':str(path),
                      'evidence':evidence})
    return {'world_lmt_sha256':p.sha(p.WORLD),'stock_arc_sha256':p.sha(source),'clips':clips,
        'root_motion':'Original source curves retained; World/GU extraction conventions require runtime comparison.',
        'acceptance':'PENDING: isolated assets; not installed as a completed fix'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--bake',action='store_true');args=ap.parse_args()
    report=plan();OUT.mkdir(parents=True,exist_ok=True)
    if args.bake:
        source=p.read_skeleton(p.WORLD_MODEL,True);target=p.read_skeleton(p.GU_MODEL,False)
        p.check_mapping(source,target)
        actions=source_actions()
        entries=[];timelines={};raw={p.WORLD:p.WORLD.read_bytes(),COMMON:COMMON.read_bytes()}
        for row in report['clips']:
            a,path=actions[row['world_clip']]
            entries.append((row['gu_slot'],a,p.bake(a,source,target)))
            timelines[a.id]=p.timeline(raw[path],a)
            print(f"Baked source {a.id} -> isolated slot {row['gu_slot']}",flush=True)
        blob=p.write_bank(entries);report['readback']=p.verify_readback(blob,entries)
        bank=OUT/'world_ground_body.lmt';bank.write_bytes(blob)
        report['bank_sha256']=p.sha(bank)
        (OUT/'timelines.json').write_text(json.dumps(timelines,ensure_ascii=False,indent=2),encoding='utf8')
    (p.PROJECT/'research/world_ground_motion_plan.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'clips':len(report['clips']),'ids':[r['world_clip']for r in report['clips']],
                      'output':str(OUT),'baked':args.bake}))

if __name__=='__main__':main()
