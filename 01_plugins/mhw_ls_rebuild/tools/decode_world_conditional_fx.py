"""Decode the owned thrust glow with the previously pinned independent reader."""
import json,sys,subprocess
from animation_port import ROOT,sha
tool=ROOT/'.cache/mhw_efx_editor'
if not tool.exists():tool=__import__('pathlib').Path('D:/AAAGPT/MHGU-MOD/gumod/.cache/mhw_efx_editor')
assert subprocess.check_output(['git','-C',str(tool),'rev-parse','HEAD'],text=True).strip()=='4c231acda787074330d506cae24911c5977087d0'
sys.path.insert(0,str(tool))
from efx_format import EFXFile,ATTR_SCHEMA_MAP,unpack
from efx_format.structs import ATTR_CUSTOM_CODEC
from efx_format.hashes import HASH_TO_NAME
cache=ROOT/'.cache/mhw_ls_presentation'
for clip in ("wp03_050","wp03_060"):
    path=cache/'source/vfx/efx/wp/wp03'/f'{clip}.efx';raw=path.read_bytes();effect=EFXFile.parse(raw)
    assert effect.serialize()==raw and not effect.main_opaque
    rows=[]
    for emitter in effect.main:
        attrs=[]
        for attr in emitter.attr_blocks:
            schema=ATTR_SCHEMA_MAP.get(attr.type_hash)
            if not schema:continue
            value=ATTR_CUSTOM_CODEC[attr.type_hash][0](attr.data_bytes) if schema[0]=='_custom' else unpack(schema[0],attr.data_bytes)
            fields=value[0] if isinstance(value,tuple) else value
            attrs.append({'type':HASH_TO_NAME.get(attr.type_hash,hex(attr.type_hash)),'fields':fields})
        rows.append({'attributes':attrs})
    (cache/'decoded'/f'{clip}.json').write_text(json.dumps(rows,indent=2,default=lambda b:b.decode('ascii').rstrip('\0')),encoding='utf8')
    print(clip,len(rows),sha(path))
