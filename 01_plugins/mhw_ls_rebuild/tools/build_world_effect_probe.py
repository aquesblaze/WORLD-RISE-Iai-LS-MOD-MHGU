"""Private one-billboard renderer experiment, not the final source effect."""
import json,struct,sys
from animation_port import ROOT,PROJECT,sha
sys.path.insert(0,str(ROOT/'05_reference/fx_test23/source_reference'))
from build_effect_assets import entries,pel_groups,pack

CACHE=ROOT/'.cache/mhw_ls_presentation'
EFX='effect/world/probe_wp03_002'
PEL='effect/pel/pl/world_probe'
UID=0x3f50

def main():
    textures=json.loads((PROJECT/'research/wp03_002_texture_conversion.json').read_text())
    native=entries((ROOT/'04_assets/MHGU_romfs/romfs/nativeNX/arc/shell/pl/com.arc').read_bytes())
    key=next(k for k in native if k[0]=='effect/cm/cm139_000')
    flags,template=native[key];b=bytearray(template)
    assert len(b)==1056 and b[:4]==b'EFL\0' and struct.unpack_from('<HH',b,16)==(1,1)
    offsets=[48+(v>>8) for v in struct.unpack_from('<4I',b,48)]
    assert offsets==[80,272,736,752],offsets
    emitter,unit,life,position=offsets
    source=json.loads((CACHE/'decoded/wp03_002.json').read_text())[2]
    billboard=next(a['fields']for a in source['attributes']if a['type']=='BILLBOARD3D')
    assert billboard['width']==billboard['height']==50 and billboard['scale']==1
    # Native A5D538 case0 copies the spawn transform without the template's
    # type8 acceleration/drift. Keep its unused storage to preserve offsets.
    struct.pack_into('<I',b,60,(position-48)<<8)
    # Isolate renderer/UV/size from the template's random emission and curves.
    struct.pack_into('<H',b,emitter+12,1)
    struct.pack_into('<2f4I2f',b,emitter+64,1,0,1,1,1,0,0,0)
    struct.pack_into('<6f',b,emitter+96,*([0]*6))
    struct.pack_into('<6f',b,emitter+136,1,0,1,0,1,0)
    struct.pack_into('<4I',b,life,0,0,43,0)
    ean_path=next(v['ean'] for v in textures['emitters'] if v['emitter']==2)
    ean=next(v for v in textures['resources'] if v['path']==ean_path)
    tex=next(v for v in textures['resources'] if v['path']==ean['texture'])
    for off,path in [(0x70,tex['path']),(0x130,ean_path)]:
        b[unit+off:unit+off+64]=path.encode().ljust(64,b'\0')
    # Preserve GU's working billboard shader flags for this first transport
    # check. Native A6A2A4 copies brightness to particle88 and fixed256 fields.
    # HDR/blend equivalence and anisotropic animation still need comparison.
    struct.pack_into('<6f',b,unit+32,billboard['brightness'],0,50/tex['width'],0,0,0)
    struct.pack_into('<I',b,unit+56,0)
    struct.pack_into('<I',b,unit+64,0)
    struct.pack_into('<2I',b,unit+72,0xfffeffff,0xfffeffff)
    struct.pack_into('<I',b,unit+80,0)
    struct.pack_into('<2I',b,unit+96,tex['width']//2,tex['height']//2)
    struct.pack_into('<10f',b,unit+0x170,0,0,0,0,1,0,0,0,1,0)
    struct.pack_into('<I',b,unit+0x198,0)
    weapon=entries((ROOT/'04_assets/MHGU_romfs/romfs/nativeNX/arc/shell/pl/w07.arc').read_bytes())
    pflags,original=weapon['effect/pel/pl/w07_800',0x5a525c16]
    row=next(r for r in pel_groups(original)[2] if r['uid']==800)
    payload=bytearray(row['raw'][row['payload']:]);assert len(payload)==160
    struct.pack_into('<3f',payload,0,0,0,0)
    struct.pack_into('<H',payload,48,UID)
    raw=original[:8]+struct.pack('<3I',0,0,1)+bytes([len(EFX)])+EFX.encode()+b'\x01\0'+payload
    assert pel_groups(raw)[2][0]['uid']==UID
    resources={}
    for r in (tex,ean):
        from pathlib import Path
        path=Path(r['output']);assert sha(path)==r['sha256']
        data=path.read_bytes();resources[r['path'],r['type']]=(0x40000000|len(data),data)
    resources[EFX,key[1]]=(flags&0xe0000000|len(b),bytes(b))
    resources[PEL,0x5a525c16]=(pflags&0xe0000000|len(raw),raw)
    out=ROOT/'.cache/mhw_ls_combat/mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_effects.arc'
    out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(pack(resources))
    report={'status':'EXPERIMENTAL_NATIVE_BILLBOARD_BUILT','arc':str(out),'arc_sha256':sha(out),
        'template':'effect/cm/cm139_000','source_clip':'wp03_002','source_emitter':2,
        'uid':UID,'resources':[{'path':p,'type':hex(t),'bytes':len(d)}for(p,t),(f,d)in resources.items()],
        'native_render_verified':False,'complete_source_effect':False,
        'brightness':billboard['brightness'],
        'limits':['Native template shader. Source brightness is passed to native particle brightness; HDR/blend equivalence, scale animation, continuous attachment and other emitters are not validated.']}
    (PROJECT/'research/world_effect_probe_bank.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],sha(out))

if __name__=='__main__':main()
