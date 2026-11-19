"""Check original media payloads at actual native renderer voice addresses."""
import json,re,struct
from pc_fixture import Fixture
from animation_port import ROOT,PROJECT,sha

def main():
    f=Fixture();bank=json.loads((PROJECT/'research/world_audio_bank.json').read_text(encoding='utf8'))
    pcm=json.loads((f.run/'conditional_presentation.json').read_text(encoding='utf8'));rows=[]
    report={'status':'FAIL','plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
            'bank_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_audio.arc'),'native_media':rows}
    try:
        assert pcm['plugin_sha256']==report['plugin_sha256'] and pcm['audio_arc_sha256']==report['bank_sha256']==bank['arc_sha256']
        assert pcm['status'].startswith('PASS')
        wanted={m['media']:m for m in bank['media'] if m['media'] in {r['media']for r in bank['requests']if r.get('source_request')in(25515,25606)}}
        assert len(wanted)==4
        waves={ident:(ROOT/f'.cache/mhw_ls_presentation/audio/gu/{ident}.wave').read_bytes() for ident in wanted}
        pattern=re.compile(r'fmt 6 rate (\d+) ch 1 pitch 1\.000 .*? addr ([0-9a-f]+) .*?\[0,(\d+)\).*? ds ([0-9a-f]+)')
        found=set()
        with(f.run/'log.txt').open(encoding='utf8',errors='replace')as log:
            for line in log:
                match=pattern.search(line)
                if not match:continue
                rate,at,samples,coef=match.groups();rate=int(rate);samples=int(samples);at=int(at,16);coef=int(coef,16)
                for ident,m in wanted.items():
                    if ident in found or (m['rate'],m['samples'])!=(rate,samples):continue
                    wave=waves[ident];n=struct.unpack_from('<I',wave,8)[0]
                    if bytes(f.read(at,f'<{n}B'))!=wave[0x78:0x78+n]:continue
                    assert f.read(coef,'<16h')==struct.unpack_from('<16h',wave,24)
                    found.add(ident);rows.append({'media':ident,'native_pcm_renderer_log':line.strip(),'adpcm_payload_equal':True,'coefficients_equal':True})
                if len(found)==4:break
        assert found==set(wanted),found
        for move in('foresight','thrust'):
            negative=next(c for c in pcm['cases']if c['move']==move and not c['expected'])
            for positive in(c for c in pcm['cases']if c['move']==move and c['expected']):
                for p,n in zip(positive['source_matches'],negative['source_matches']):
                    assert p['media']==n['media'] and abs(p['correlation'])>2*abs(n['correlation']),(p,n)
        report['status']='PASS_CONDITIONAL_NATIVE_PAYLOADS_AND_PCM_CONTROLS'
        report['pcm_report_sha256']=sha(f.run/'conditional_presentation.json')
        print(report['status'],len(rows),'original media')
    finally:
        (f.run/'conditional_transport.json').write_text(json.dumps(report,indent=2)+'\n');f.close()

if __name__=='__main__':main()
