"""Build record-local controls for the World Iai streak; never writes into either game."""
import copy,json,sys,struct,hashlib
from pathlib import Path
from animation_port import ROOT,PROJECT
from inspect_world_presentation import Reader,epv
tool=Path('D:/AAAGPT/MHGU-MOD/gumod/.cache/mhw_efx_editor')
sys.path.insert(0,str(tool))
from efx_format import EFXFile
from efx_format.assembly.efx import efx_to_json,efx_from_json

def main():
    src=ROOT/'.cache/mhw_ls_presentation/source'
    out=ROOT/'.cache/world_iai_record_ab';out.mkdir(parents=True,exist_ok=True)
    rel=Path('wp/swo/epv/hm_wp03.epv3');ep=src/rel
    relfx=Path('vfx/efx/wp/wp03/wp03_004.efx')
    raw=(src/relfx).read_bytes();original=efx_to_json(EFXFile.parse(raw))
    assert efx_from_json(original).serialize()==raw
    offsets={};reader=Reader(ep);reader.pos=8
    for _ in range(reader.read('I')):
        count,group=reader.read('Ih')
        for __ in range(count):
            offset=reader.pos;paths=[reader.string() for _ in range(4)]
            rec=struct.unpack_from('<h',reader.data,reader.pos+8)[0];reader.pos+=338
            if group==1012 and rec in (5,6,7):
                assert paths[0]==str(relfx.with_suffix(''));offsets[rec]=offset
    contract=json.loads((ROOT/'.cache/mhw_ls_ground_rebuild/full_presentation/source_contract.json').read_text(encoding='utf8'))
    tex=json.loads((PROJECT/'research/wp03_004_texture_conversion.json').read_text())
    data={'status':'file_roundtrip_verified_game_AB_pending','efx_sha256':hashlib.sha256(raw).hexdigest(),'records':{},'variants':{}}
    for rid,action,candidate in ((5,1,11),(6,2,10),(7,3,10)):
        row=contract['work_records'][str(3010+rid)][0];assert (row['group_id'],row['record_id'])==(1012,rid)
        base=original['actions'][action]['entries'][0]['fields']['targets']
        assert candidate in base
        ean=next(v['ean'] for v in tex['emitters'] if v['emitter']==candidate)
        uv=next(v for v in tex['resources'] if v['path']==ean)
        diffuse=next(v for v in tex['resources'] if v['path']==uv['texture'])
        data['records'][rid]={'epv':row,'timl':[e for e in contract['events'] if e['clip']==304+rid],'selector':original['subselect'][rid-4],'parent':original['entries'][rid-3],'action':original['actions'][action],'candidate_index':candidate,'candidate':original['entries'][candidate],'uv':uv,'texture':diffuse}
        for mode,targets in [('routing_control',base),('minus',[i for i in base if i!=candidate]),('only',[candidate])]:
            name=f'r{rid}_{mode}';folder=out/name/'nativePC';alias=relfx.with_name(f'wp03_9{rid:02}.efx')
            patch=bytearray(ep.read_bytes());i=offsets[rid];namebytes=str(alias.with_suffix('')).encode();assert len(namebytes)==len(str(relfx.with_suffix('')))
            patch[i:i+len(namebytes)]=namebytes
            (folder/rel).parent.mkdir(parents=True,exist_ok=True);(folder/rel).write_bytes(patch)
            parsed=epv(folder/rel);unchanged=epv(ep)
            rr=next(r for g in parsed['groups'] if g['group_id']==1012 for r in g['records'] if r['record_id']==rid)
            assert rr['paths'][0]==str(alias.with_suffix(''));rr['paths'][0]=str(relfx.with_suffix(''));assert parsed==unchanged
            variant=copy.deepcopy(original);variant['actions'][action]['entries'][0]['fields']['targets']=targets
            blob=efx_from_json(variant).serialize();(folder/alias).parent.mkdir(parents=True,exist_ok=True);(folder/alias).write_bytes(blob)
            check=efx_to_json(EFXFile.parse((folder/alias).read_bytes()));assert check==variant
            if mode=='routing_control':assert blob==raw
            data['variants'][name]={'action':action,'targets':targets,'sha256':hashlib.sha256(blob).hexdigest()}
    (out/'evidence.json').write_text(json.dumps(data,indent=2),encoding='utf8')
    print(out, len(data['variants']))
if __name__=='__main__':main()
