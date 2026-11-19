"""Isolated controller asset overlay; original ARC and saves stay unchanged."""
from prepare_world_combat import *
def align_drawn_recovery(bank):
    """Ease the pelvis into the equipped GU idle during the final recovery."""
    from animation_port import read_gu, compile_pose_curve
    idle=next(t for t in read_gu(bank,1).tracks if t.header.bone_id==0 and t.header.usage==1)
    target=compile_pose_curve(idle).sample(0)
    result=bytearray(bank)
    for slot in (224,225,229,238,239,240,241,245):
        header=struct.unpack_from('<I',bank,8+4*slot)[0]
        tracks,count,frames=struct.unpack_from('<III',bank,header)
        at=next(tracks+i*36 for i in range(count) if bank[tracks+i*36:tracks+i*36+4]==bytes((3,1,0,0)))
        size,data=struct.unpack_from('<II',bank,at+8)
        assert size==frames*16
        last=data+(frames-1)*16
        for axis in (0,2):
            delta=target[axis]-struct.unpack_from('<f',bank,last+axis*4)[0]
            for f in range(frames-36,frames):
                u=(f-(frames-36))/35
                off=data+16*f+4*axis
                value=struct.unpack_from('<f',bank,off)[0]+delta*u*u*(3-2*u)
                struct.pack_into('<f',result,off,value)
    return bytes(result)

def apply_combat_root_rates(bank):
    result=bytearray(bank)
    source=json.loads((PROJECT/'research/world_combat_source.json').read_text(encoding='utf8'))
    for clip in source['clips'].values():
        slot=clip['gu_slot']
        if slot is None:continue
        for axis,name in enumerate(('mMotionTransRateX','mMotionTransRateY','mMotionTransRateZ')):
            keys=track(clip['raw_events'],'PlMotionCommon',name)
            if not keys:continue
            if len(keys)!=1 or keys[0][0]!=0:raise ValueError('Time-varying root rate needs integration')
            factor=keys[0][1];header=struct.unpack_from('<I',result,8+slot*4)[0]
            tracks,count=struct.unpack_from('<II',result,header)
            positions=[header+16+axis*4]
            for n in range(count):
                at=tracks+n*36;codec,usage,_,bone=struct.unpack_from('<4B',result,at)
                if usage!=4 or bone!=255:continue
                size,data=struct.unpack_from('<II',result,at+8)
                positions.append(at+16+axis*4)
                if codec==3:positions.extend(data+k+axis*4 for k in range(0,size,16))
                elif codec!=1:raise ValueError('Unexpected root codec')
            for pos in positions:struct.pack_into('<f',result,pos,struct.unpack_from('<f',result,pos)[0]*factor)
    return bytes(result)


def main():
    import argparse
    ap=argparse.ArgumentParser();ap.add_argument('--ground',action='store_true');args=ap.parse_args()
    source=ROOT/'Windows-MHGURecomp/data/romfs/nativeNX/arc/player/quest/w07.arc'
    raw,version,entries=read_entries(source);result=bytearray(raw)
    # Usage3 rotates the World actor. The runtime now applies that heading;
    # GU's inverse-root transform then consumes the original translation.
    bank_path=ROOT/'.cache/mhw_ls_ground_rebuild/world_ground_body.lmt' if args.ground else OUT/'world_body_preview.lmt'
    bank=apply_combat_root_rates(bank_path.read_bytes());changed=[]
    nodes=collision_table(SOURCE/'collision/wp03.col')
    geometry=dict(enumerate(collision_geometry(SOURCE/'collision/wp03.col')))
    ids=[63,65,82,84,101,86,87,88,89]
    if args.ground:
        contract=json.loads((PROJECT/'research/world_combat_source.json').read_text(encoding='utf8'))
        if not contract.get('ground_bank'):raise ValueError('Regenerate ground TIML headers first')
        ids=sorted(map(int,contract['collision_nodes']))
        for key,pair in contract['collision_pairs'].items():
            key=int(key);first,second=pair
            nodes[key]={'geometry':key,'attack':nodes[first]['attack']}
            geometry[key]=geometry[nodes[first]['geometry']]+geometry[nodes[second]['geometry']]
    shell_nodes=collision_table(SOURCE/'shell/collision/object.col')
    # Local IDs >=1000 identify shell rows and cannot collide with TIML IDs.
    for key,source_key in [(1001,6),(1002,5),(1003,4),(1011,15),(1012,14),(1013,13),
                           (1021,9),(1022,8),(1023,7)]:
        nodes[key]=shell_nodes[source_key];ids.append(key)
    appended=[];shape_map={};hit_base=None
    # Each private group retains the source capsule/sphere endpoints and radius.
    # These are collision geometry, separate from the visual blade attachment.
    for source_group in sorted({nodes[i]['geometry'] for i in ids if not 1000<=i<2000}):
        records=[]
        for r in geometry[source_group]:
            if r[0]!=1 or r[15] not in (8,9,10):raise ValueError('Unsupported source collision joint/type')
            bone=r[15]
            records.append(struct.pack('<4H10f',bone,bone,r[0],r[1],0,r[2],*r[8:11],0,*r[11:14],0))
        appended.append((source_group,b''.join(records)))
    shell_geometry=collision_geometry(SOURCE/'shell/collision/object.col')
    for key,group in [(1001,1),(1011,2)]:
        rows=shell_geometry[group]
        if len(rows)!=1 or rows[0][8:14]!=(0.,0.,0.,0.,0.,0.):
            raise ValueError('Expected centered World delayed sphere')
        # GU stock HTS group1 is a root sphere: function255, type0.
        appended.append((key,struct.pack('<4H10f',255,0,0,0,0,rows[0][2],0,0,0,0,0,0,0,0)))
    for entry in entries:
        old,_=unpack_one(raw,entry)
        body=None
        if entry['name'].replace('\\','/')=='player/mot/w07/w07' and old[:4]==b'LMT\0':
            body=append_preview_bank(old,bank)
            if args.ground:body=align_drawn_recovery(body)
        elif old[:4]==b'HTS\0':
            count=struct.unpack_from('<I',old,8)[0];extra=8*len(appended)
            body=bytearray(old[:16+8*count]+bytes(extra)+old[16+8*count:])
            struct.pack_into('<I',body,8,count+len(appended))
            for i in range(count):struct.pack_into('<I',body,20+8*i,struct.unpack_from('<I',old,20+8*i)[0]+extra)
            for i,(source_group,records) in enumerate(appended):
                shape_map[source_group]=count+i
                struct.pack_into('<II',body,16+8*(count+i),len(records)//48,len(body));body.extend(records)
        elif old[:4]==b'HDP\0':
            hit_base=struct.unpack_from('<I',old,8)[0]
            if len(old)!=16+hit_base*56:raise ValueError('HDP extent')
            body=bytearray(old);template=old[16+30*56:16+31*56]
            for key in ids:
                record=bytearray(template);attack=nodes[key]['attack'];mv=attack['Motion_Value']
                if int(mv)!=mv:raise ValueError('Fractional source MV needs native scaling')
                struct.pack_into('<HHI',record,0,0,1,int(mv));struct.pack_into('<I',record,48,int(mv))
                # Native368960 transfers these to collider94/98; element/status
                # scaling uses94 (374b48/3781c4), monster reaction uses98->142c.
                if abs(attack['Elemental_Modifier']-attack['Status_Modifier'])>1e-5:
                    raise ValueError('Separate element/status scaling required')
                struct.pack_into('<ff',record,40,attack['Elemental_Modifier'],attack['Part_Modifier'])
                body.extend(record)
            struct.pack_into('<I',body,8,hit_base+len(ids))
        if body is not None:
            packed=zlib.compress(body,9)
            offset=len(result);result.extend(packed)
            struct.pack_into('<III',result,12+entry['index']*80+68,len(packed),entry['flags']|len(body),offset)
            changed.append(entry['index'])
    if len(changed)!=3 or hit_base is None:raise ValueError('Expected LMT/HDP/HTS')
    target=DEST/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/player/quest/w07.arc'
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(result)
    check,_,new=read_entries(target)
    for old,e in zip(entries,new):
        if e['index'] not in changed and unpack_one(raw,old)[0]!=unpack_one(check,e)[0]:
            raise ValueError('Unrelated resource changed')
    (DEST/'arc_manifest.json').write_text(json.dumps({'source':str(source),'source_sha256':sha(source),
        'output':str(target),'output_sha256':sha(target),'changed_entries':changed,
        'status':'controller integration; combat acceptance pending'},indent=2),encoding='utf8')
    print(target)
    text='/* Locally generated appended records; stock rows stay byte-identical. */\n#pragma once\n'
    text+='typedef struct {unsigned source,hit,shape;} WHit;\nstatic const WHit world_hits[]={\n'
    text+=''.join(f' {{{key}u,{hit_base+i}u,{shape_map[nodes[key]["geometry"] if not 1000<=key<2000 else 1011 if 1010<=key<1020 else 1001]}u}},\n' for i,key in enumerate(ids))+'};\n'
    text+=f'#define WORLD_HIT_COUNT {hit_base+len(ids)}u\n'
    text+=f'#define WORLD_SHAPE_COUNT {max(shape_map.values())+1}u\n'
    (PROJECT/'c/world_hits.h').write_text(text,encoding='utf8')


if __name__=='__main__':main()
