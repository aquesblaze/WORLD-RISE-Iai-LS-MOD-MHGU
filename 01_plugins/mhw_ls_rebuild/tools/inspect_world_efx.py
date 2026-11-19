"""Inventory exact local effects using a pinned external format reader.

The GPL reader remains a separate tool in .cache; no reader code or original
game bytes are copied into this project's report.
"""
import collections,hashlib,json,re,subprocess,sys
from pathlib import Path
from animation_port import ROOT,PROJECT

def main():
    tool=ROOT/'.cache/mhw_efx_editor';commit='4c231acda787074330d506cae24911c5977087d0'
    actual=subprocess.check_output(['git','-C',str(tool),'rev-parse','HEAD'],text=True).strip()
    assert actual==commit,('Reader version changed',actual)
    sys.path.insert(0,str(tool))
    from efx_format import EFXFile
    from efx_format.hashes import HASH_TO_NAME
    source=ROOT/'.cache/mhw_ls_presentation/source';files=[];refs=set()
    paths=json.loads((source.parent/'effect_dependencies.json').read_text(encoding='utf8'))
    for relative in paths:
        path=source/(relative.replace('\\','/')+'.efx');raw=path.read_bytes();efx=EFXFile.parse(raw)
        assert efx.serialize()==raw,('Reader failed byte-identical roundtrip',relative)
        assert not efx.main_opaque,('Main effect data not decoded',relative)
        types=collections.Counter(HASH_TO_NAME.get(a.type_hash,hex(a.type_hash))
                                  for m in efx.main if hasattr(m,'attr_blocks') for a in m.attr_blocks)
        deps=sorted({m.group().decode('ascii') for m in re.finditer(rb'vfx[\\/][A-Za-z0-9_\\/]+',raw)})
        refs.update(deps)
        files.append({'path':relative,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),
                      'roundtrip_equal':True,'main_opaque':False,'emitters':len(efx.main),'actions':len(efx.play),
                      'labels':efx.labels,'attribute_counts':dict(types),'dependencies':deps,
                      'subselect':[vars(t) for t in efx.subselect]})
    report={'status':'SOURCE_EFX_PARSED_ONLY','tool':'https://github.com/Dimcirui/MHW-EFX-Editor',
            'tool_commit':commit,'files':files,'referenced_assets':sorted(refs),
            'limits':'Parsing and byte-identical roundtrip do not establish GU renderer support or visual equivalence.',
            'converted_for_gu':False,'installed':False}
    (PROJECT/'research/world_efx_inventory.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(report['status'],len(files),'files;',sum(r['emitters'] for r in files),'emitters;',len(refs),'references')

if __name__=='__main__':main()
