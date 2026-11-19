"""Retarget source blade deployment to each GU weapon group's own endpoints.

World's blade translates; GU weapons retract, scale, rotate or unfold. Preserve
each GU group's native closed/open shapes, using the measured World deployment
curve as the interpolation parameter. Never overwrite stock motion slots.
"""
import json,math,struct,zlib
from pathlib import Path
import numpy as np
import animation_port as p
from prepare_world_combat import DEST,read_entries,unpack_one

SOURCE=Path(r'D:\MHW_extract\wp\swo\mot\wg03_00\wg03_00.lmt')
SLOTS={2:220,3:221}

def rotation(a,b,t):
    a=np.asarray(a,dtype=float);a/=np.linalg.norm(a)
    b=np.asarray(b,dtype=float);b/=np.linalg.norm(b)
    dot=float(np.dot(a,b))
    if dot<0:b=-b;dot=-dot
    angle=math.acos(min(1,dot))
    if angle<1e-7:return tuple(a)
    return tuple((math.sin((1-t)*angle)*a+math.sin(t*angle)*b)/math.sin(angle))

def main():
    source={a.id:a for a in p.read_lmt_file(SOURCE).actions};progress={}
    for motion in SLOTS:
        a=source[motion]
        curve=next(p.compile_pose_curve(t) for t in a.tracks if (t.header.bone_id,t.header.usage)==(2,1))
        progress[motion]=[(40-curve.sample(f)[2])/80 for f in range(a.header.frame_count)]
        assert len(progress[motion])==11
    outputs=[]
    root=p.ROOT/'04_assets/MHGU_romfs/romfs/nativeNX/arc/weapon/w07'
    for path in sorted(root.glob('g*.arc')):
        raw,version,entries=read_entries(path);out=bytearray(raw);changed=[];validation=[]
        for entry in entries:
            if not entry['name'].startswith('weapon\\w07\\mot\\wg07_') or 'sa_' in entry['name']:continue
            old,_=unpack_one(raw,entry);ends=[]
            for clip in (0,1):
                ends.append({(t.header.bone_id,t.header.usage):p.compile_pose_curve(t).sample(0) for t in p.read_gu(old,clip).tracks})
            assert ends[0].keys()==ends[1].keys(),('Endpoint channel mismatch',path)
            bank_entries=[]
            for motion,slot in SLOTS.items():
                components={}
                for key,a in ends[0].items():
                    b=ends[1][key]
                    components[key]=[rotation(a,b,t) if key[1] in (0,3) else tuple(x+(y-x)*t for x,y in zip(a,b)) for t in progress[motion]]
                    if key[1]==2:assert min(min(v) for v in components[key])>0,'Reflected weapon scale'
                bank_entries.append((slot,source[motion],components))
            bank=p.write_bank(bank_entries);validation.append(p.verify_readback(bank,bank_entries))
            body=p.append_preview_bank(old,bank)
            out.extend(bytes((-len(out))%8));offset=len(out);packed=zlib.compress(body,9);out.extend(packed)
            struct.pack_into('<III',out,12+80*entry['index']+68,len(packed),entry['flags']|len(body),offset)
            changed.append(entry['index'])
        assert len(changed)==1,(path,changed)
        target=DEST/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/weapon/w07'/path.name
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(out)
        check,_,new=read_entries(target)
        for before,after in zip(entries,new):
            if before['index'] not in changed:assert unpack_one(raw,before)[0]==unpack_one(check,after)[0]
        outputs.append({'relative':str(target.relative_to(DEST)).replace('\\','/'),'sha256':p.sha(target),
            'source':str(path),'source_sha256':p.sha(path),'changed_entries':changed,'readback':validation})
    assert len(outputs)==8
    evidence={'status':'PASS_WEAPON_BANK_READBACK_ONLY','source':str(SOURCE),'source_sha256':p.sha(SOURCE),
        'private_slots':SLOTS,'source_deployment_fraction':progress,'outputs':outputs,
        'mapping':'World blade-Z normalized between closed40 and open-40; GU native endpoint translations/scales and shortest-arc quaternion interpolation. Source overshoot retained.',
        'native_clock':'PlMotionCommon+e8 request, +f0 speed default1, +f4 start default0, +f8 blend default0; constructor191f5b0, consumer1f6cc00, request2110a90.',
        'limits':'Different weapon skeletons require retargeting. Runtime clock and visuals need independent verification; this report proves encoding and stock preservation only.'}
    (p.PROJECT/'research/weapon_transition_assets.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Verified',len(outputs),'weapon groups; private draw/close slots220/221')

if __name__=='__main__':main()
