"""Compile local World timelines and collision IDs for the clean controller.

Sparse collision IDs are resolved through the final field in COL's name table,
never used as array offsets. Output assets stay in .cache; only derived event
constants and an evidence manifest are stored with the source project.
"""
from pathlib import Path
import json
import re
import struct
import zlib
import sys
import argparse
from animation_port import ROOT, PROJECT, WORLD, OUT, CLIPS, timeline, sha, read_lmt_file, append_preview_bank
sys.path.insert(0,str(ROOT/'06_tools'))
from arc_tool import read_entries, unpack_one

SOURCE=Path(r'D:\MHW_extract\MHW_LS_LOGIC\hm\wp\wp03')
CACHE=ROOT/'.cache/ls_world_retarget/mhw_editor'
DEST=ROOT/'.cache/mhw_ls_combat'


def collision_table(path):
    b=path.read_bytes()
    if b[4:8]!=b'COL\0':raise ValueError('Not COL')
    nodes={};p=24
    for _ in range(struct.unpack_from('<I',b,20)[0]):
        end=b.index(0,p);name=b[p:end].decode('utf8');p=end+1
        geometry,move,unknown,u2,u3,key=struct.unpack_from('<iiiHBI',b,p);p+=19
        if key in nodes:raise ValueError('Duplicate collision ID')
        nodes[key]={'name':name,'geometry':geometry,'move':move}
    text=(CACHE/'col.bt').read_text(encoding='utf8').split('// Atk1')[1].split('} Atk1;')[0]
    fields=re.findall(r'^\s*(uint|float|ubyte|byte|ushort)\s+(\w+)<',text,re.M)
    types={'uint':'I','float':'f','ubyte':'B','byte':'b','ushort':'H'}
    fmt='<'+''.join(types[t] for t,_ in fields);stride=struct.calcsize(fmt)
    at=b.index(b'ATK\0')-4;count,kind=struct.unpack_from('<II',b,at+12)
    if kind!=1 or stride!=218:raise ValueError('Unsupported COL attack layout')
    attacks={}
    for i in range(count):
        row=dict(zip([n for _,n in fields],struct.unpack_from(fmt,b,at+20+i*stride)))
        if row['Index'] in attacks:raise ValueError('Duplicate attack ID')
        attacks[row['Index']]=row
    for node in nodes.values():
        if node['move']>=0:node['attack']=attacks[node['move']]
    return nodes


def collision_geometry(path):
    b=path.read_bytes();p=24
    for _ in range(struct.unpack_from('<I',b,20)[0]):p=b.index(0,p)+20
    _,tag,_,count,kind,_=struct.unpack_from('<I4sIIIB',b,p);p+=21
    if tag!=b'CLND' or kind!=1:raise ValueError('Unsupported geometry version')
    result=[]
    for _ in range(count):
        _,tag,_,n=struct.unpack_from('<I4sII',b,p);p+=16
        rows=[]
        for _ in range(n):
            rows.append(struct.unpack_from('<BB4fhh6fHIh4fH',b,p));p+=72
        p+=27;result.append(rows)
    if b[p+7:p+11]!=b'ATK\0':raise ValueError('Geometry extent does not meet ATK section')
    return result


def sample(keys,t,default=0):
    value=default
    for frame,v in keys:
        if frame>t:break
        value=v
    return value


def track(events,kind,name):
    keys=[]
    for e in events:
        if e['type']!=kind:continue
        for row in e['tracks']:
            if row['name']==name:keys+=row['keys']
    # The channels used here occur once; reject conflicting duplicate tracks.
    if len({t for t,_ in keys})!=len(keys):raise ValueError((kind,name,'duplicate keys'))
    return keys


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--ground',action='store_true')
    args=parser.parse_args()
    DEST.mkdir(parents=True,exist_ok=True)
    data=WORLD.read_bytes();actions={a.id:a for a in read_lmt_file(WORLD).actions}
    mapped={world:gu for world,gu,_ in CLIPS}
    nodes=collision_table(SOURCE/'collision/wp03.col')
    clips={};event_rows=[];input_rows=[];profiles=[];float_rows=[];float_profiles=[]
    # Native ground clips use their actual motion clock; their two-bit input
    # channels remain explicitly separate from GU's own cancellation rules.
    wanted=sorted(set(mapped)|set(range(101,111))|{127,128})
    if args.ground:
        from prepare_ground_motion_bank import source_actions
        sources=source_actions()
        plan=json.loads((PROJECT/'research/world_ground_motion_plan.json').read_text(encoding='utf8'))
        mapped={r['world_clip']:r['gu_slot']for r in plan['clips']};wanted=sorted(mapped)
    pairs={}
    for world in wanted:
        if args.ground:
            a,path=sources[world];data=path.read_bytes();actions[world]=a
        a=actions[world];events=timeline(data,a)
        # Native runtime observations establish TIML1=hold,2=linear. Do not
        # inherit the external reader's display labels (off by one here).
        from animation_port import read_timl_data_bytes,DATATYPE_HASH_LABELS
        typed=read_timl_data_bytes(data,data_offset=a.header.timl_offset,entry_id=world)
        for channel,name in enumerate(('mMotionSpeed','mTurnSpeed','mCameraResetTime')):
            chosen=[t for group in typed.types for t in group.transforms if DATATYPE_HASH_LABELS.get(t.datatype_hash)==name]
            if not chosen:continue
            assert len(chosen)==1,(world,name)
            keys=chosen[0].keyframes;offset=len(float_rows)
            for k in keys:
                assert k.interpolation in (1,2) and k.easing==2 and k.control_left==0 and k.control_right==0,(world,name,vars(k))
                float_rows.append((k.frame_timing,k.value,k.interpolation))
            float_profiles.append((world,channel,offset,len(keys)))
        fields=[('PlMotionInput','mFlag'),('PlMotionInput','mFlag1'),
                ('PlMotionInput','mFlag2'),('PlMotionCommon','mFlag'),
                ('PlMotionCommon','mFlag2'),('PlMotionCommon','mTrigger'),
                ('PlMotionCommon','mMotionSpeed'),('PlMotionCommon','mActionPhase'),
                ('PlMotionCommon','mTurnSpeed')]
        tracks=[track(events,*f) for f in fields]
        extra_input=[track(events,'PlMotionInput','mFlag'+str(i))for i in range(3,7)]
        col=[e for e in events if e['type']=='CollisionTimelineObject']
        hit=[]
        for e in col:
            ids=next((r['keys'] for r in e['tracks'] if r['name']=='ノードID[0]'),None)
            bank=next((r['keys'] for r in e['tracks'] if r['name']=='バンク[0]'),[[0,0]])
            if ids is None:raise ValueError('Missing primary collision node')
            if any(v!=0 for _,v in bank):raise ValueError('Unsupported collision bank')
            # Secondary native ground colliders remain owned by GU. Raw source
            # events are preserved in the report; private moves use slot zero.
            flags=next(r['keys'] for r in e['tracks'] if r['name']=='mFlag')
            ids2=next((r['keys']for r in e['tracks']if r['name']=='ノードID[1]'),[[0,-1]])
            bank2=next((r['keys']for r in e['tracks']if r['name']=='バンク[1]'),[[0,0]])
            if any(v!=0 for _,v in bank2):raise ValueError('Unsupported secondary collision bank')
            hit.append((bank,ids,flags,ids2))
        times={0.0}
        for keys in tracks:
            times.update(t for t,_ in keys)
        for keys in extra_input:times.update(t for t,_ in keys)
        for group in hit:
            for keys in group:times.update(t for t,_ in keys)
        rows=[];full_inputs=[]
        for t in sorted(times):
            values=[sample(keys,t,1 if i==6 else 0) for i,keys in enumerate(tracks)]
            live=[]
            for slot,ids,flags,ids2 in hit:
                if int(sample(flags,t))&1:
                    key=int(sample(ids,t));live.append(key)
                    if key not in nodes or 'attack' not in nodes[key]:raise ValueError(('Unresolved ID',key))
                if args.ground and int(sample(flags,t))&2:
                    key=int(sample(ids2,t));live.append(key)
                    if key not in nodes or 'attack' not in nodes[key]:raise ValueError(('Unresolved secondary ID',key))
            if len(live)==2:
                first,second=live
                if nodes[first]['attack']!=nodes[second]['attack']:
                    raise ValueError('Distinct concurrent attacks need separate native colliders')
                key=20000+first*128+second;pairs[key]=live;live=[key]
            if len(live)>1:raise ValueError('Controller needs multiple concurrent colliders')
            row=[t,*map(int,values[:6]),float(values[6]),int(values[7]),float(values[8]),live[0] if live else -1]
            inputs=list(map(int,values[:3]))+[int(sample(keys,t))for keys in extra_input]
            if not rows or row[1:]!=rows[-1][1:]or inputs!=full_inputs[-1]:
                rows.append(row);full_inputs.append(inputs)
        offset=len(event_rows);event_rows+=rows;input_rows+=full_inputs
        clips[world]={'frames':a.header.frame_count,'gu_slot':mapped.get(world),
                      'rows':rows,'full_input_words':full_inputs,'raw_events':events}
        profiles.append((world,mapped.get(world,0),a.header.frame_count,offset,len(rows)))
    header='/* Generated from local source TIML/COL; see world_combat_source.json. */\n#pragma once\n'
    header+='typedef struct {float frame; unsigned input[7],common,common2,trigger; float speed; unsigned phase; float turn_speed; int hit;} WEvent;\n'
    header+='typedef struct {unsigned source,slot,length,offset,count;} WClip;\n'
    header+='static const WEvent world_events[]={\n'
    for row,inputs in zip(event_rows,input_rows):
        t,i0,i1,i2,c,c2,tr,sp,ph,turn,hit=row
        header+=f' {{{t:.1f}f,{{'+','.join(str(v)+'u'for v in inputs)+f'}},{c}u,{c2}u,{tr}u,{sp:.6f}f,{ph}u,{turn:.6f}f,{hit}}},\n'
    header+='};\nstatic const WClip world_clips[]={\n'
    header+=''.join(' {'+','.join(str(v)+'u' for v in p)+'},\n' for p in profiles)+'};\n'
    (PROJECT/'c/world_events.h').write_text(header,encoding='utf8')
    floats='/* Generated from original typed TIML keys;1=hold,2=linear. */\n#pragma once\n'
    floats+='typedef struct {float frame,value;unsigned interpolation;} WFloatKey;\n'
    floats+='typedef struct {unsigned source,channel,offset,count;} WFloatTrack;\n'
    floats+='static const WFloatKey world_float_keys[]={\n'+''.join(f' {{{t:.9f}f,{v:.9f}f,{m}u}},\n' for t,v,m in float_rows)+'};\n'
    floats+='static const WFloatTrack world_float_tracks[]={\n'+''.join(' {'+','.join(str(v)+'u' for v in row)+'},\n' for row in float_profiles)+'};\n'
    (PROJECT/'c/world_floats.h').write_text(floats,encoding='utf8')
    used=sorted({row[-1] for row in event_rows if row[-1]>=0})
    report={'source_hashes':{str(p):sha(p) for p in [WORLD,SOURCE/'collision/wp03.col']},
            'row_fields':['frame','input0','input1','input2','common0','common2','trigger','speed','phase','turn_speed','collision_id'],
            'clips':clips,'collision_nodes':{key:nodes[key] for key in used if key not in pairs},
            'gu_combat_verified':False,'input_pair_semantics_verified':False,
            'ground_bank':args.ground,'collision_pairs':pairs}
    for key,(first,second)in pairs.items():
        report['collision_nodes'][key]={'paired_nodes':[first,second],'attack':nodes[first]['attack'],
            'geometry_groups':[nodes[first]['geometry'],nodes[second]['geometry']]}
    (PROJECT/'research/world_combat_source.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    print('Compiled',len(profiles),'timelines,',len(event_rows),'events;',len(used),'resolved collision IDs')


if __name__=='__main__':main()
