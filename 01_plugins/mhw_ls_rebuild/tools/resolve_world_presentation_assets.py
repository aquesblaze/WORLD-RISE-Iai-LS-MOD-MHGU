"""Resolve World EFX, UVS and material dependencies against the local chunk index.

The pinned external reader is used as a separate format tool. No opaque reader
code or original game bytes are emitted into the project report.
"""
import argparse,json,re,subprocess,sys
from pathlib import Path
from animation_port import ROOT,PROJECT,sha

CACHE=ROOT/'.cache/mhw_ls_presentation'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--extract',action='store_true')
    ap.add_argument('--inventory',type=Path,default=PROJECT/'research/world_efx_inventory.json')
    ap.add_argument('--report-name',default='world_presentation_assets');args=ap.parse_args()
    assert args.report_name.replace('_','').isalnum()
    tool=ROOT/'.cache/mhw_efx_editor'
    if not tool.exists():tool=Path('D:/AAAGPT/MHGU-MOD/gumod/.cache/mhw_efx_editor')
    assert subprocess.check_output(['git','-C',str(tool),'rev-parse','HEAD'],text=True).strip()=='4c231acda787074330d506cae24911c5977087d0'
    sys.path.insert(0,str(tool));from efx_format.uvs import UVSFile
    index={}
    for line in (CACHE/'all_files.tsv').read_text(encoding='utf-8-sig').splitlines():
        chunk,path,size=line.split('|');path=path.replace('\\','/').strip('/')
        index[path.lower()]={'path':path,'chunk':chunk,'bytes':int(size)}
    inventory=json.loads(args.inventory.read_text(encoding='utf8'))
    pending=list(inventory.get('referenced_assets',inventory.get('asset_references',[])))
    assert pending,'No source asset references'
    selected={};edges={};roundtrips={}
    def extract():
        (CACHE/'presentation_asset_dependencies.json').write_text(json.dumps(sorted(selected),indent=2)+'\n',encoding='utf8')
        subprocess.run([sys.executable,str(Path(__file__).with_name('prepare_presentation_sources.py'))],check=True)
    for generation in range(6):
        for ref in pending:
            key=ref.replace('\\','/').strip('/').lower()
            matches=[v for k,v in index.items() if k==key or k.startswith(key+'.')]
            assert matches,('Unresolved source reference',ref)
            assert all(Path(v['path']).suffix.lower() in ('.tex','.uvs','.mod3','.mrl3','.tfa') for v in matches),matches
            edges[ref]=[v['path'] for v in matches]
            for v in matches:selected[v['path']]=v
        missing=[p for p in selected if not (CACHE/'source'/p).is_file()]
        if missing:
            if not args.extract:break
            extract()
            assert all((CACHE/'source'/p).is_file() for p in missing)
            missing=[]
        pending=[]
        for path in selected:
            p=CACHE/'source'/path;raw=p.read_bytes();refs=[]
            if p.suffix=='.uvs':
                u=UVSFile.parse(raw);assert u.serialize()==raw,('UVS roundtrip failed',path)
                roundtrips[path]={'groups':len(u.groups),'frames':sum(len(g.frames) for g in u.groups),'sha256':sha(p)}
                refs=[s.path for s in u.strings if s.path]
            elif p.suffix in ('.mrl3','.mod3'):
                refs=[m.group().decode('ascii') for m in re.finditer(rb'vfx[\\/][A-Za-z0-9_\\/]+',raw)]
            pending.extend(ref for ref in refs if ref not in edges)
        if not pending:break
    else:raise RuntimeError('Dependency traversal did not converge')
    (CACHE/'presentation_asset_dependencies.json').write_text(json.dumps(sorted(selected),indent=2)+'\n',encoding='utf8')
    report={'status':'SOURCE_ASSET_CLOSURE_EXTRACTED' if not missing else 'SOURCE_ASSET_CLOSURE_REQUESTED',
        'source_index_sha256':sha(CACHE/'all_files.tsv'),'assets':selected,'edges':edges,
        'uvs_roundtrips':roundtrips,'missing':missing,'converted_for_gu':False,'installed':False,
        'limits':'File closure and UVS byte preservation only; GU renderer conversion and visual acceptance remain separate work.'}
    report['source_inventory']=str(args.inventory);report['source_inventory_sha256']=sha(args.inventory)
    (PROJECT/'research'/(args.report_name+'.json')).write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(report['status'],len(selected),'assets;',len(roundtrips),'UVS files; missing',len(missing))

if __name__=='__main__':main()
