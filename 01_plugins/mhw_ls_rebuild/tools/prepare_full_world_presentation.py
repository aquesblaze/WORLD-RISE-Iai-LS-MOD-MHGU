"""Preserve full ground TIML/EPV/EFX records for the non-simplified rebuild.

Every emitter and attribute stays in source order, with original payload hashes
and lossless bytes in the private cache. Unsupported decoding is recorded as a
coverage failure, never replaced by a glow or silently dropped. This source
stage does not assert GU renderer support.
"""
import base64
import collections
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from animation_port import ROOT,PROJECT,sha
from inspect_world_presentation import epv,epvsp

CACHE=ROOT/'.cache/mhw_ls_presentation'
OUT=ROOT/'.cache/mhw_ls_ground_rebuild/full_presentation'

def json_value(value):
    if isinstance(value,bytes):return {'bytes_base64':base64.b64encode(value).decode('ascii')}
    if hasattr(value,'__dict__'):return vars(value)
    raise TypeError(type(value))

def main():
    timelines=json.loads((ROOT/'.cache/mhw_ls_ground_rebuild/timelines.json').read_text(encoding='utf8'))
    providers={name:epv(CACHE/'source'/path)for name,path in {
        'weapon':'wp/swo/epv/hm_wp03.epv3','common':'hm/common/epv/hm_cm00.epv3'}.items()}
    sound=epvsp(CACHE/'source/wp/swo/sound/hm_wp03.epvsp')
    events=[];work=set()
    for clip,groups in timelines.items():
        for index,event in enumerate(groups):
            if not event['type'].startswith('EffectParameter'):continue
            events.append({'clip':int(clip),'source_track_index':index,**event})
            work|={int(v)for t in event['tracks']if t['name'].startswith('WorkNo')for _,v in t['keys']}
    resolved={};paths=set()
    for ident in sorted(work):
        found=[]
        for name,provider in providers.items():
            for link in provider['work_index']:
                if link['work']!=ident:continue
                group=provider['groups'][link['group_index']]
                record=group['records'][link['record_index']]
                row={'provider':name,**link,'group_id':group['group_id'],**record}
                if name=='weapon':row['sound']={k:[s for s in sound[k]if (s['group_id'],s['record_id'])==(group['group_id'],record['record_id'])]for k in ('requests','triggers')}
                found.append(row);paths.update(s.replace('\\','/')for s in record['paths']if s)
        resolved[ident]=found
    # Code-triggered coloured sword trails/counters are not all TIML WorkNo
    # entries. Keep the complete LS-specific effect bank for their bindings.
    for group in providers['weapon']['groups']:
        for record in group['records']:
            paths.update(s.replace('\\','/')for s in record['paths']if s.replace('\\','/').startswith('vfx/efx/wp/wp03/'))
    source_contract={'events':events,'work_records':resolved,'weapon_epv':providers['weapon'],
                     'sound_requests_and_triggers':sound}
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'source_contract.json').write_text(json.dumps(source_contract,ensure_ascii=False,indent=2),encoding='utf8')
    dependencies=CACHE/'effect_dependencies.json'
    existing=json.loads(dependencies.read_text())if dependencies.exists()else []
    dependencies.write_text(json.dumps(sorted(set(s.replace('\\','/')for s in existing)|paths),indent=2)+'\n')
    missing=[s for s in sorted(paths)if not (CACHE/'source'/(s+'.efx')).is_file()]
    if missing:
        report={'status':'FULL_PRESENTATION_SOURCE_FILES_MISSING','missing':missing,'full_emitters_required':True}
        (PROJECT/'research/world_full_presentation_source.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report));return
    tool=ROOT/'.cache/mhw_efx_editor'
    if not tool.exists():tool=Path('D:/AAAGPT/MHGU-MOD/gumod/.cache/mhw_efx_editor')
    commit='4c231acda787074330d506cae24911c5977087d0'
    assert subprocess.check_output(['git','-C',str(tool),'rev-parse','HEAD'],text=True).strip()==commit
    sys.path.insert(0,str(tool))
    from efx_format import EFXFile,ATTR_SCHEMA_MAP,unpack
    from efx_format.structs import ATTR_CUSTOM_CODEC
    from efx_format.hashes import HASH_TO_NAME
    from efx_format.assembly.efx import efx_to_json,efx_from_json
    from efx_format.assembly.entry import entry_to_json
    files=[];failures=[];refs=set();total=collections.Counter()
    for relative in sorted(paths):
        path=CACHE/'source'/(relative+'.efx');raw=path.read_bytes();efx=EFXFile.parse(raw)
        assert efx.serialize()==raw,('Non-lossless EFX parse',relative)
        assembled=efx_to_json(efx)
        assert efx_from_json(assembled).serialize()==raw,('Full structured JSON roundtrip differs',relative)
        if efx.main_opaque:failures.append({'path':relative,'error':'opaque main emitter records'})
        emitters=[];types=collections.Counter()
        for index,emitter in enumerate(efx.main):
            if not hasattr(emitter,'attr_blocks'):
                emitters.append({'index':index,'kind':'root_controls','full_record':entry_to_json(emitter)})
                continue
            attrs=[]
            for attr_index,attr in enumerate(emitter.attr_blocks):
                name=HASH_TO_NAME.get(attr.type_hash,hex(attr.type_hash));types[name]+=1
                row={'index':attr_index,'type':name,'hash':attr.type_hash,
                     'payload_sha256':hashlib.sha256(attr.data_bytes).hexdigest(),
                     'payload_bytes':attr.data_bytes}
                try:
                    schema=ATTR_SCHEMA_MAP.get(attr.type_hash)
                    if not schema:raise ValueError('No schema')
                    value=ATTR_CUSTOM_CODEC[attr.type_hash][0](attr.data_bytes)if schema[0]=='_custom'else unpack(schema[0],attr.data_bytes)
                    row['fields']=value[0]if isinstance(value,tuple)else value
                except Exception as error:
                    row['decode_error']=str(error)
                    failures.append({'path':relative,'emitter':index,'attribute':attr_index,'type':name,'error':str(error)})
                attrs.append(row)
            emitters.append({'index':index,'attributes':attrs})
        decoded=OUT/(Path(relative).name+'.json')
        decoded.write_text(json.dumps({'source':relative,'emitters':emitters,'play':efx.play,
            'subselect':efx.subselect,'labels':efx.labels,'full_efx':assembled},default=json_value,indent=2),encoding='utf8')
        asset_refs=sorted({m.group().decode('ascii').replace('\\','/')for m in re.finditer(rb'vfx[\\/][A-Za-z0-9_\\/]+',raw)})
        refs.update(asset_refs);total.update(types)
        files.append({'path':relative,'sha256':sha(path),'emitters':sum(hasattr(e,'attr_blocks')for e in efx.main),
            'attributes':dict(types),'roundtrip_equal':True,'decoded_sha256':sha(decoded),'dependencies':asset_refs})
    report={'status':'FULL_SOURCE_DECODED_RENDERER_PENDING'if not failures else 'FULL_SOURCE_ATTRIBUTE_DECODE_INCOMPLETE',
        'source_motion_count':len(timelines),'effect_tracks':len(events),'work_ids':len(work),
        'files':files,'emitters':sum(f['emitters']for f in files),'attribute_counts':dict(total),
        'failures':failures,'unresolved_work_ids':[k for k,v in resolved.items()if not v and k>=0],
        'asset_references':sorted(refs),'external_reader_commit':commit,
        'raw_payloads_preserved':True,'renderer_implemented':False,'installed':False,
        'limits':'Full source preservation/decoding only. GU emitters, particles, curves, materials and rendering must all be implemented and visually verified; the old simplified archive is not a completed port.'}
    (PROJECT/'research/world_full_presentation_source.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items()if k not in ('files','asset_references','attribute_counts','failures')},ensure_ascii=True))
    print('Decode coverage failures:',len(failures),'types:',dict(total))

if __name__=='__main__':main()
