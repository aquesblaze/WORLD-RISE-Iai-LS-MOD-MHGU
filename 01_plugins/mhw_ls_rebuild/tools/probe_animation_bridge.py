"""Read-only v67/x86 -> common LMT model format probe, NOT a retargeter.

Layout references (independently checked against the user's GU file):
https://github.com/PredatorCZ/RevilLib/blob/master/src/mtf_lmt/animation.inl
https://github.com/PredatorCZ/RevilLib/blob/master/src/mtf_lmt/bone_track.inl
No RevilLib implementation is embedded. Codec decoding uses the locally
installed mhw-anim-tools core. No files in either game's data are written.
"""
from pathlib import Path
from collections import Counter
import hashlib
import json
import math
import struct
import sys

PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,r'C:\gumod\.cache\mhw_anim_tools_core')
from core.formats.lmt.reader import read_lmt_file
from core.formats.lmt.model import LmtAction, LmtActionHeader, LmtTrack, LmtTrackHeader, LmtInterpolationBasis
from core.formats.lmt.decoder import decode_action_tracks

GU=Path(r'C:\gumod\04_assets\hit_w07\player\mot\w07\w07')
WORLD=Path(r'D:\MHW_extract\MHW_LS_WORLD\hm\wp\wp03\mot\w03_00\w03_00.lmt')

def read_gu(data,clip):
    magic,version,count=struct.unpack_from('<4sHH',data)
    assert magic==b'LMT\0' and version==67 and clip<count
    def values(fmt,offset):
        assert offset>0 and offset+struct.calcsize(fmt)<=len(data),(fmt,offset)
        return struct.unpack_from(fmt,data,offset)
    offset=values('<I',8+clip*4)[0]
    track_offset,n,frames,loop=values('<IIIi',offset)
    assert n<2048 and frames<100000
    translation=values('<4f',offset+16)
    rotation=values('<4f',offset+32)
    tracks=[]
    for i in range(n):
        p=track_offset+36*i
        codec,usage,joint,bone,weight,size,buffer,*tail=values('<BBBBfII4fI',p)
        basis=tuple(tail[:4]);lerp=tail[4]
        assert usage<=4 and codec<=15
        assert not size or (buffer>0 and buffer+size<=len(data))
        assert all(math.isfinite(x) for x in basis+(weight,))
        ranges=values('<8f',lerp) if lerp else None
        tracks.append(LmtTrack(LmtTrackHeader(codec,usage,joint,0,-1 if bone==255 else bone,
            weight,size,buffer,basis,lerp),data[buffer:buffer+size],
            LmtInterpolationBasis(tuple(ranges[:4]),tuple(ranges[4:])) if ranges else None))
    header=LmtActionHeader(clip,track_offset,n,frames,loop,(0,0,0),translation,
        rotation,data[offset+48],b'\0\0',0,(0,0,0,0,0),0)
    return LmtAction(header,tuple(tracks))

def describe(action):
    decoded=decode_action_tracks(action)
    roots=[]
    for track in decoded.tracks:
        if track.bone_id==-1:
            roots.append({'usage':track.usage,'basis':track.basis_value,
                          'tail':track.tail_value,'key_count':len(track.keyframes)})
    return {'clip':action.id,'frames':action.header.frame_count,'track_count':len(action.tracks),
        'bone_ids':sorted({t.header.bone_id for t in action.tracks}),
        'codecs':dict(Counter(t.header.buffer_type for t in action.tracks)),
        'roots':roots,'decode_diagnostics':[{'track':t.track_index,'error':t.decode_error}
            for t in decoded.tracks if t.decode_error]}

def main():
    data=GU.read_bytes();world={a.id:a for a in read_lmt_file(WORLD).actions}
    # Validate structural parsing for EVERY present GU action, not just the
    # attractive examples; never infer bone correspondence from a shared ID.
    count=struct.unpack_from('<H',data,6)[0]
    present=[i for i in range(count) if struct.unpack_from('<I',data,8+i*4)[0]]
    actions=[read_gu(data,i) for i in present]
    report={'status':'format probe only; no animation port or writer yet',
        'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in (GU,WORLD)},
        'gu_version':67,'world_version':95,'gu_pointer_width':4,'world_pointer_width':8,
        'gu_action_size':64,'gu_track_stride':36,'world_track_stride':48,
        'gu_present_actions_structurally_validated':len(actions),
        'comparisons':[{'semantic':name,'world':describe(world[w]),'gu':describe(read_gu(data,g))}
            for name,w,g in [('FADE_LEFT',127,128),('FADE_RIGHT',128,129),('SPIRIT_STEP',110,130)]],
        'remaining':['Semantic skeleton/bind-pose mapping; equal numeric IDs do not prove equivalence.',
            'Native-verified sample timing, quaternion order and root axes/scale calibration.',
            'GU v67 writer, events and resource binding, then key-pose/blade/sheath validation.',
            'No converted animations are included in rebuild-b1.']}
    (PROJECT/'research/animation_bridge_probe.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()
