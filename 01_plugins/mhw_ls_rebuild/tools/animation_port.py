"""Local World v95 -> GU v67 body animation experiment.

This is deliberately NOT a combat mod. It writes an event-free, sparse motion
bank for preview, plus source TIML evidence separately. Weapon/sheath channels,
collisions, invulnerability and resource consumption require their own adapter.
The bone mapping is checked against model hierarchy/rest matrices, not inferred
from equal function IDs. No original game files are modified.

Format references: RevilLib animation.inl/bone_track.inl; AsteriskAmpersand
Mod3Skeleton.py/Mod3Components.py; DemonDrugd MHGU-blenderImporter. The binary
reader/writer below is independent. Sampling uses local mhw-anim-tools 1.1 core.
"""
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import math
import struct
import sys
import os
import numpy as np

PROJECT = Path(__file__).resolve().parents[1]
# Explicit runtime root supports verification/deployment from a worktree.
ROOT = Path(os.environ.get('MHGU_WORLD_RUNTIME_ROOT',PROJECT.parents[1])).resolve()
sys.path.insert(0, str(ROOT / '.cache/mhw_anim_tools_core'))
from core.formats.lmt.reader import read_lmt_file
from core.formats.lmt.pose_evaluation import compile_pose_evaluation, compile_pose_curve
from core.formats.timl.reader import read_timl_data_bytes
from core.formats.timl.semantics import TIMELINE_PARAMETER_LABELS, DATATYPE_HASH_LABELS
from probe_animation_bridge import read_gu

WORLD = Path(r'D:\MHW_extract\MHW_LS_WORLD\hm\wp\wp03\mot\w03_00\w03_00.lmt')
CACHE = ROOT / '.cache/mhw_skeleton'
WORLD_MODEL = CACHE / 'source/pl/m_equip/pl001_0000/body/mod/m_body001_0000.mod3'
GU_MODEL = CACHE / 'gu_m_body001.mod'
OUT = ROOT / '.cache/mhw_ls_animation_port'
# Target function -> source function. World pelvis13 collapses under GU0;
# World's extra toe17 shifts the opposite leg's functions by one.
BODY_MAP = {0:13, **{i:i for i in range(1,13)}, 14:14, 15:15, 16:16, 17:18, 18:19, 19:20}
# Clip identity is a research candidate until visually/native validated.
CLIPS = [(140,224,'foresight'), (170,225,'spirit_thrust'),
         (171,226,'helm_rise'), (172,227,'helm_air'),
         (173,228,'helm_down'), (174,229,'helm_land'),
         (306,230,'special_sheathe'), (307,238,'iai_slash'),
         (308,239,'iai_spirit'), (309,240,'iai_spirit_variant_309'),
         (310,241,'iai_spirit_variant_310'), (127,242,'fade_left_control'),
         (128,243,'fade_right_control'), (110,244,'spirit_step_control'),
         (311,245,'iai_spirit_red'), (312,246,'special_sheathe_exit')]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def quat_matrix(q):
    q = np.asarray(q, dtype=float)
    if not np.isfinite(q).all() or np.linalg.norm(q) < 1e-10:
        raise ValueError('Invalid quaternion')
    w,x,y,z = q / np.linalg.norm(q)
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
                     [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
                     [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])


def matrix_quat(m):
    # Symmetric eigenproblem avoids a fragile branch near 180 degrees.
    r = np.asarray(m, dtype=float)
    if not np.allclose(r.T@r, np.eye(3), atol=2e-5) or np.linalg.det(r)<0:
        raise ValueError('Scale/shear/reflection needs a separate retarget rule')
    k = np.array([[r[0,0]-r[1,1]-r[2,2],r[0,1]+r[1,0],r[0,2]+r[2,0],r[2,1]-r[1,2]],
                  [r[0,1]+r[1,0],r[1,1]-r[0,0]-r[2,2],r[1,2]+r[2,1],r[0,2]-r[2,0]],
                  [r[0,2]+r[2,0],r[1,2]+r[2,1],r[2,2]-r[0,0]-r[1,1],r[1,0]-r[0,1]],
                  [r[2,1]-r[1,2],r[0,2]-r[2,0],r[1,0]-r[0,1],np.trace(r)]])
    _, vectors = np.linalg.eigh(k)
    q = vectors[:, -1][[3,0,1,2]]
    return q if q[0]>=0 else -q


@dataclass
class Skeleton:
    path: Path
    parents: list
    functions: list
    local: list
    world: list
    mapping: dict


def read_skeleton(path, world):
    b=path.read_bytes()
    expected=237 if world else 212
    if b[:4]!=b'MOD\0' or b[4]!=expected:
        raise ValueError(f'Unsupported model {path}')
    n=struct.unpack_from('<H',b,6)[0]
    offset=struct.unpack_from('<Q' if world else '<I',b,48 if world else 36)[0]
    map_size=512 if world else 256
    if not 0<n<255 or offset+n*152+map_size>len(b):
        raise ValueError('Invalid skeleton extent')
    parents=[];functions=[];local=[];global_matrices=[]
    for i in range(n):
        values=struct.unpack_from('<hBB' if world else '<BBBB',b,offset+24*i)
        function,parent=values[:2]
        if parent!=255 and not 0<=parent<i:
            raise ValueError('Skeleton is not an ordered acyclic hierarchy')
        m=np.array(struct.unpack_from('<16f',b,offset+24*n+64*i)).reshape(4,4).T
        if not np.isfinite(m).all() or not np.allclose(m[3],(0,0,0,1),atol=1e-6):
            raise ValueError('Invalid bind matrix')
        parents.append(parent);functions.append(function);local.append(m)
        global_matrices.append(m if parent==255 else global_matrices[parent]@m)
    table=b[offset+n*152:offset+n*152+map_size]
    mapping={i:v for i,v in enumerate(table) if v!=255}
    if any(v>=n for v in mapping.values()):
        raise ValueError('Function table points outside skeleton')
    for function in BODY_MAP.values() if world else BODY_MAP:
        if function not in mapping or functions[mapping[function]]!=function:
            raise ValueError(f'Missing or aliased core function {function}')
    return Skeleton(path,parents,functions,local,global_matrices,mapping)


def check_mapping(source,target):
    rows=[]
    for gu,world in BODY_MAP.items():
        gi,wi=target.mapping[gu],source.mapping[world]
        gp=target.parents[gi]
        sf_parent=BODY_MAP[target.functions[gp]] if gp!=255 else None
        wp=source.mapping[sf_parent] if sf_parent is not None else None
        p=wi;chain=[]
        while p!=wp and p!=255:
            chain.append(source.functions[p]);p=source.parents[p]
        if (wp is not None and p!=wp):
            raise ValueError(f'Inconsistent semantic chain {gu}')
        src_local=source.world[wi] if wp is None else np.linalg.inv(source.world[wp])@source.world[wi]
        error=float(np.max(np.abs(src_local-target.local[gi])))
        if error>0.001:
            raise ValueError(f'Rest transform correction required for function {gu}: {error}')
        rows.append({'gu_function':gu,'world_function':world,'source_chain':list(reversed(chain)),
                     'max_rest_matrix_error':error})
    return rows


def source_pose(action,skeleton):
    p=compile_pose_evaluation(action,{k:str(v) for k,v in skeleton.mapping.items()})
    if not p.supported:
        raise ValueError([(d.level,d.message) for d in p.diagnostics if d.level=='ERROR'])
    base={}
    for i,m in enumerate(skeleton.local):
        base[str(i),0]=tuple(matrix_quat(m[:3,:3]))
        base[str(i),1]=tuple(m[:3,3]);base[str(i),2]=(1,1,1)
    return p,base


def sample_body(pose,base,source,target,frame):
    values=pose.sample(frame,base=base);world=[]
    for i,parent in enumerate(source.parents):
        scale=values[str(i),2]
        # Finger/equipment-only branches can carry authored scale. Preserve it
        # in source FK; matrix_quat rejects any scale reaching a mapped body bone.
        m=np.eye(4);m[:3,:3]=quat_matrix(values[str(i),0])@np.diag(scale);m[:3,3]=values[str(i),1]
        world.append(m if parent==255 else world[parent]@m)
    output={}
    for gu,src in BODY_MAP.items():
        gi=target.mapping[gu];gp=target.parents[gi]
        m=world[source.mapping[src]]
        if gp!=255:
            parent_world=world[source.mapping[BODY_MAP[target.functions[gp]]]]
            m=np.linalg.inv(parent_world)@m
        output[gu,0]=tuple(matrix_quat(m[:3,:3]));output[gu,1]=tuple(m[:3,3])
    for usage in (3,4):
        if (None,usage) in values:output[-1,usage]=values[None,usage]
    return output


def bake(action,source,target):
    pose,base=source_pose(action,source)
    samples=[sample_body(pose,base,source,target,f) for f in range(action.header.frame_count)]
    keys=set(samples[0])
    if any(set(s)!=keys for s in samples):raise ValueError('Changing pose component set')
    components={key:[s[key] for s in samples] for key in sorted(keys)}
    # Native GU body LMT leaves ordinary bone lengths to the equipped model.
    # Emitting male bind translations would stretch female shoulders slightly.
    for key in list(components):
        bone,usage=key
        if bone>0 and usage==1:
            rest=target.local[target.mapping[bone]][:3,3]
            if np.max(np.abs(np.asarray(components[key])-rest))<0.0001:
                del components[key]
    return components


def encode_component(values,usage):
    quaternion=usage in (0,3)
    a=np.asarray(values,dtype=float)
    if not np.isfinite(a).all():raise ValueError('Non-finite output samples')
    if quaternion:
        a/=np.linalg.norm(a,axis=1)[:,None]
        for i in range(1,len(a)):
            if np.dot(a[i-1],a[i])<0:a[i]*=-1
    constant=np.max(np.abs(a-a[0]))<1e-7
    basis=tuple(a[0][[1,2,3,0]]) if quaternion else (*a[0],0)
    if constant:return (2 if quaternion else 1),basis,b''
    raw=bytearray()
    for i,v in enumerate(a):
        delta=0 if i==len(a)-1 else 1
        if quaternion:
            q=[int(round(x*4096)) for x in v]
            if any(not -8192<=x<=8191 for x in q):raise ValueError('Quaternion overflow')
            w,x,y,z=(x&0x3fff for x in q)
            raw+=struct.pack('<Q',w|(z<<14)|(y<<28)|(x<<42)|(delta<<56))
        else:raw+=struct.pack('<3fI',*v,delta)
    return (6 if quaternion else 3),basis,bytes(raw)


def write_bank(entries):
    count=max(slot for slot,_,_ in entries)+1
    b=bytearray(struct.pack('<4sHH',b'LMT\0',67,count)+b'\0'*(4*count))
    def alloc(size,align=16):
        b.extend(b'\0'*((-len(b))%align));at=len(b);b.extend(b'\0'*size);return at
    for slot,action,components in entries:
        header=alloc(64);struct.pack_into('<I',b,8+4*slot,header)
        tracks=alloc(36*len(components))
        struct.pack_into('<IIIi',b,header,tracks,len(components),action.header.frame_count,action.header.loop_frame)
        struct.pack_into('<4f',b,header+16,*action.header.translation)
        struct.pack_into('<4f',b,header+32,*action.header.rotation_lerp)
        # Match stock GU's base flags. Events/floats remain null by design.
        struct.pack_into('<I',b,header+48,0x800000)
        for i,((bone,usage),values) in enumerate(components.items()):
            codec,basis,raw=encode_component(values,usage)
            offset=alloc(len(raw)) if raw else 0
            if raw:b[offset:offset+len(raw)]=raw
            struct.pack_into('<BBBBfII4fI',b,tracks+i*36,codec,usage,0,bone&255,1,len(raw),offset,*basis,0)
    return bytes(b)


def verify_readback(blob,entries):
    max_angle=max_translation=0.0;sample_count=0
    for slot,original,components in entries:
        read=read_gu(blob,slot)
        if read.header.frame_count!=original.header.frame_count:raise ValueError('Frame count changed')
        actual={(t.header.bone_id,t.header.usage):compile_pose_curve(t) for t in read.tracks}
        if set(actual)!=set(components):raise ValueError('Component loss')
        for key,values in components.items():
            for f,v in enumerate(values):
                got=np.array(actual[key].sample(f));v=np.array(v);sample_count+=1
                if key[1] in (0,3):
                    dot=abs(float(np.dot(got/np.linalg.norm(got),v/np.linalg.norm(v))))
                    angle=math.degrees(2*math.acos(min(1,dot)));max_angle=max(max_angle,angle)
                else:max_translation=max(max_translation,float(np.max(np.abs(got-v))))
    if max_angle>0.06 or max_translation>0.001:
        raise ValueError(f'Encoding error {max_angle}deg, {max_translation} units')
    return {'component_samples':sample_count,'max_rotation_error_degrees':max_angle,
            'max_translation_error_units':max_translation,'native_gu_playback_verified':False}


def timeline(raw,action):
    if not action.header.timl_offset:return []
    data=read_timl_data_bytes(raw,data_offset=action.header.timl_offset,entry_id=action.id)
    return [{'type':TIMELINE_PARAMETER_LABELS.get(t.timeline_parameter_hash,hex(t.timeline_parameter_hash)),
             'tracks':[{'name':DATATYPE_HASH_LABELS.get(k.datatype_hash,hex(k.datatype_hash)),
                        'keys':[[v.frame_timing,v.value] for v in k.keyframes]} for k in t.transforms]} for t in data.types]


def append_preview_bank(stock, bank):
    """Append only to unused slots; keep every original payload byte in place."""
    count=struct.unpack_from('<H',stock,6)[0]
    other=struct.unpack_from('<H',bank,6)[0]
    if stock[:6]!=b'LMT\0\x43\0' or bank[:6]!=stock[:6] or other>count:
        raise ValueError('Stock table cannot accommodate preview slots')
    out=bytearray(stock);out.extend(b'\0'*((-len(out))%16));base=len(out);out.extend(bank)
    used=[]
    for slot in range(other):
        head=struct.unpack_from('<I',bank,8+4*slot)[0]
        if not head:continue
        if struct.unpack_from('<I',stock,8+4*slot)[0]:
            raise ValueError(f'Refusing to overwrite stock motion {slot}')
        used.append(slot);struct.pack_into('<I',out,8+4*slot,base+head)
        tracks,n=struct.unpack_from('<II',bank,head)
        if any(struct.unpack_from('<II',bank,head+52)):
            raise ValueError('Preview bank must contain no events or float tracks')
        struct.pack_into('<I',out,base+head,base+tracks)
        for i in range(n):
            track=tracks+36*i
            for field in (12,32):
                offset=struct.unpack_from('<I',bank,track+field)[0]
                if offset:struct.pack_into('<I',out,base+track+field,base+offset)
    for i,(old,new) in enumerate(zip(stock,out)):
        if old!=new and not any(8+slot*4<=i<12+slot*4 for slot in used):
            raise ValueError('Stock payload was changed')
    return bytes(out)


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    source=read_skeleton(WORLD_MODEL,True);target=read_skeleton(GU_MODEL,False)
    mapping=check_mapping(source,target)
    actions={a.id:a for a in read_lmt_file(WORLD).actions};entries=[];clips=[]
    raw=WORLD.read_bytes()
    for world,gu,name in CLIPS:
        a=actions[world];body=bake(a,source,target);entries.append((gu,a,body))
        clips.append({'name_candidate':name,'world_clip':world,'gu_preview_slot':gu,
                      'frames':a.header.frame_count,'source_root_tail':a.header.translation,
                      'body_components':len(body),'source_events':timeline(raw,a)})
        print(f'Baked World {world} -> GU {gu}: {a.header.frame_count} frames',flush=True)
    blob=write_bank(entries);validation=verify_readback(blob,entries)
    bank=OUT/'world_body_preview.lmt';bank.write_bytes(blob)
    report={'status':'body conversion experiment; not a playable combat mod',
            'sources':{str(p):sha(p) for p in (WORLD,WORLD_MODEL,GU_MODEL)},
            'mapping':mapping,'clips':clips,'output':str(bank),'output_sha256':sha(bank),
            'readback':validation,'omitted':['weapon/sheath attachment and IK','World TIML execution',
            'hitboxes, damage and counter mechanics','runtime moveset integration'],
            'references':['https://github.com/wowo-dot/mhw-anim-tools',
            'https://github.com/PredatorCZ/RevilLib/blob/master/src/mtf_lmt/animation.inl',
            'https://github.com/PredatorCZ/RevilLib/blob/master/src/mtf_lmt/bone_track.inl']}
    (PROJECT/'research/animation_port.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({'output':str(bank),'bytes':len(blob),'clips':len(clips),'readback':validation},indent=2))


if __name__=='__main__':main()
