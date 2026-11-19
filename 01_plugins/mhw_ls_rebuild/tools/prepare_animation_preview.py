"""Create a disposable ARC overlay for body-preview experiments, not release."""
from pathlib import Path
import json
import struct
import sys
import zlib
from animation_port import ROOT, OUT, append_preview_bank, sha
sys.path.insert(0,str(ROOT/'06_tools'))
from arc_tool import read_entries,unpack_one


def main():
    source=ROOT/'Windows-MHGURecomp/data/romfs/nativeNX/arc/player/quest/w07.arc'
    raw,version,entries=read_entries(source)
    bank=bytearray((OUT/'world_body_preview.lmt').read_bytes())
    # The preview host is grounded native thrust. Remove scene translation in
    # this disposable copy so air clips don't drag the test actor off terrain.
    # The faithful source-converted bank and its root curves remain unchanged.
    for slot in range(struct.unpack_from('<H',bank,6)[0]):
        head=struct.unpack_from('<I',bank,8+slot*4)[0]
        if not head:continue
        struct.pack_into('<4f',bank,head+16,0,0,0,0)
        tracks,n=struct.unpack_from('<II',bank,head)
        for i in range(n):
            t=tracks+36*i
            if bank[t+1]==4:
                bank[t]=1
                struct.pack_into('<II4fI',bank,t+8,0,0,0,0,0,0,0)
    # Preserve the entire original ARC; only append new compressed LMT data and
    # redirect its one table row. Same-name MRL/MOD records cannot collide here.
    result=bytearray(raw);matched=0
    for e in entries:
        if e['name'].replace('\\','/')!='player/mot/w07/w07':continue
        body,_=unpack_one(raw,e)
        if body[:4]!=b'LMT\0':continue
        expanded=append_preview_bank(body,bank)
        packed=zlib.compress(expanded,9);offset=len(result);result.extend(packed)
        struct.pack_into('<III',result,12+e['index']*80+68,len(packed),e['flags']|len(expanded),offset)
        matched+=1
    if matched!=1:raise ValueError(f'Expected one LMT record, found {matched}')
    target=OUT/'mods/MHW_BODY_PREVIEW/romfs/nativeNX/arc/player/quest/w07.arc'
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(result)
    rd,_,re=read_entries(target)
    for before,after in zip(entries,re):
        old,_=unpack_one(raw,before);new,_=unpack_one(rd,after)
        if before['index']!=next(e['index'] for e in entries if e['name'].replace('\\','/')=='player/mot/w07/w07'):
            if old!=new:raise ValueError('Unrelated ARC resource changed')
    print(json.dumps({'preview_only':str(target),'in_place_body_only':True,'source_sha256':sha(source),'output_sha256':sha(target)},indent=2))


if __name__=='__main__':main()
