"""World MBD v21 transition contracts verified against its native loader.

1a029e0 reads target uint32 then row-count uint64. 1a02a80 reads previous
motion uint32 BEFORE the bank string. The public 010 template labels that
word at the end of the preceding row; using those labels shifts every link.
Native loader order and observed 116->104 frame44 settle the layout.
"""
import json
import struct
from animation_port import PROJECT,WORLD,sha

def read_mbd(path):
    data=path.read_bytes();magic,version,count,reserved=struct.unpack_from('<4I',data)
    if (magic,version)!=(0x18091001,21):raise ValueError('Unsupported MBD')
    p=16;entries={}
    for _ in range(count):
        target,n=struct.unpack_from('<IQ',data,p);p+=12;rows=[]
        if target in entries or n>10000:raise ValueError('Invalid MBD entries')
        for _ in range(n):
            offset=p;previous=struct.unpack_from('<I',data,p)[0];p+=4
            end=data.index(0,p);bank=data[p:end].decode('ascii');p=end+1
            values=struct.unpack_from('<fIIIfIi',data,p);p+=28
            rows.append(dict(zip(('previous','bank','previous_frame_limit','start','interpolation',
                                  'overlap','speed','modifier','unknown'),(previous,bank,*values)),file_offset=offset))
        tail=data[p:p+12];p+=12
        entries[target]={'rows':rows,'tail_hex':tail.hex()}
    if p!=len(data):raise ValueError(('MBD extent mismatch',p,len(data)))
    return entries

def select(entries,target,previous,bank,frame):
    rows=entries[target]['rows'];default=next(r for r in rows if r['bank']=='Default')
    for row in rows:
        if row['bank']!=bank or row['previous']!=previous:continue
        if row['previous_frame_limit']>0 and frame>row['previous_frame_limit']:continue
        return row
    return default

def main():
    plan=json.loads((PROJECT/'research/world_ground_motion_plan.json').read_text(encoding='utf8'))
    banks={row['source_bank']for row in plan['clips']}
    entries={};sources={}
    from pathlib import Path
    for bank in banks:
        path=Path(bank).with_suffix('.mbd');parsed=read_mbd(path);sources[str(path)]=sha(path)
        for clip in plan['clips']:
            if clip['source_bank']!=bank:continue
            ident=clip['world_clip']
            if ident not in parsed:raise ValueError(('Missing MBD target',ident,bank))
            entries[ident]=parsed[ident]
    # Source-playback evidence, independent of GU implementation.
    assert select(entries,104,116,'w03_00',42)['start']==44
    assert select(entries,107,119,'w03_00',22)['start']==22
    assert select(entries,112,118,'w03_00',14)['start']==14
    assert select(entries,306,108,'w03_00',100)['interpolation']==30
    report={'sources':sources,'entries':entries,'native_loaders':{
        'resource':'1a027e0','entry_target_and_count':'1a029e0','previous_before_bank':'1a02a80'},
        'status':'NATIVE_LAYOUT_VERIFIED_RUNTIME_START_FRAMES_PARTIALLY_OBSERVED',
        'correction':'Previous-motion ID prefixes its own row. Target row count is uint64, not two unrelated uint32 values.',
        'reference_template':'https://github.com/Synthlight/MHW-Editor/blob/master/010%20Templates/mbd.bt'}
    (PROJECT/'research/world_ground_motion_links.json').write_text(json.dumps(report,indent=2)+'\n')
    names=sorted({r['bank']for e in entries.values()for r in e['rows']});bank_ids={s:i for i,s in enumerate(names)}
    h='/* Native MBD v21 row order; compile_world_motion_links.py. */\n#pragma once\n'
    h+='typedef struct {unsigned target,previous,bank;float limit,start,blend,overlap,speed;unsigned modifier;int unknown;} WMotionLink;\n'
    h+='static const WMotionLink world_motion_links[]={\n'
    for target,entry in sorted(entries.items()):
        for row in entry['rows']:
            h+=' {'+','.join([str(target),str(row['previous']),str(bank_ids[row['bank']]),
                *(f'{row[key]:.9f}f'for key in ('previous_frame_limit','start','interpolation','overlap','speed')),
                str(row['modifier']),str(row['unknown'])])+'},\n'
    h+='};\n';h+='enum {'+','.join('W_BANK_'+(name.upper() or 'EMPTY')+'='+str(ident)for name,ident in bank_ids.items())+'};\n'
    (PROJECT/'c/world_motion_links.h').write_text(h,encoding='ascii')
    print(json.dumps({'targets':len(entries),'rows':sum(len(v['rows'])for v in entries.values()),'banks':bank_ids}))

if __name__=='__main__':main()
