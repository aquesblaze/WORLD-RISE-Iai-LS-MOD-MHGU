"""Prove private GU requests reach native audren voices with exact DSP bytes."""
import argparse,json,re,struct,time
from pc_fixture import Fixture
from animation_port import ROOT,PROJECT,sha
from prepare_world_audio import AUDIO

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--keep',action='store_true');ap.add_argument('--pitch-samples',type=int,default=8);args=ap.parse_args()
    assert args.pitch_samples>=3
    f=Fixture();log=f.run/'log.txt';report={'run':str(f.run),'tests':[],
        'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
        'limitations':'Explicit requests validate codec, native pitch variation and dry gain; source dynamic mixing and spatial acceptance are separate.'}
    try:
        text=log.read_text(encoding='utf8',errors='replace')
        match=re.search(r'world_audio_queued [0-9A-F]+ [0-9A-F]+ ([0-9A-F]+)',text)
        assert match and 'world_audio_ready' in text,'Audio resources not ready'
        mailbox=int(match[1],16);bank=json.loads((PROJECT/'research/world_audio_bank.json').read_text(encoding='utf8'))
        report['bank_sha256']=bank['arc_sha256'];report['mailbox']=hex(mailbox)
        assert sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_audio.arc')==bank['arc_sha256']
        request_resource=int(re.search(r'world_audio_ready [0-9A-F]+ ([0-9A-F]+)',text)[1],16)
        manager=f.read(0x2326d8c);voice_count=f.read(manager+202864)
        assert 0<voice_count<=1024
        def native_voice(request):
            data=bytes(f.read(manager+64,f'<{2784*voice_count}B'));rows=[]
            for i in range(voice_count):
                p=i*2784
                if struct.unpack_from('<2I',data,p+12)!=(request_resource,request['request_id']):continue
                at=manager+64+p
                rows.append({'address':hex(at),'serial':struct.unpack_from('<I',data,p+52)[0],
                    'dry_gain':struct.unpack_from('<f',data,p+120)[0],
                    'pitch_cents':struct.unpack_from('<i',data,p+128)[0],
                    'aux_gain':struct.unpack_from('<f',data,p+140)[0],
                    'final_pitch':struct.unpack_from('<f',data,p+176)[0],
                    'start_delay':struct.unpack_from('<I',data,p+220)[0],
                    'bank_gain':struct.unpack_from('<f',data,p+2608)[0],
                    'bank_pitch_cents':struct.unpack_from('<f',data,p+2616)[0],
                    'channel_mix':list(struct.unpack_from('<8f',data,p+436))})
            assert rows,('Native request voice missing',request['request_id'])
            voice=max(rows,key=lambda v:v['serial'])
            assert abs(voice['dry_gain']-10**(request['gain_db']/20))<1e-5,voice
            assert voice['pitch_cents']==request.get('pitch_cents',0) and voice['start_delay']==0,voice
            assert abs(voice['bank_gain']-1)<1e-5,voice
            assert request['pitch_cents_min']<=voice['bank_pitch_cents']<=request['pitch_cents_max'],voice
            return voice
        pattern=re.compile(r'\[audren\] f(\d+) v(\d+) wb(\d+) fmt (\d+) rate (\d+) ch (\d+) pitch ([\d.]+) vol ([\d.]+) mix (-?\d+) res (\d+) addr ([0-9a-f]+) size ([0-9a-f]+) \[(\d+),(\d+)\) loop (\d+)/(-?\d+) eos (\d+) ctx ([0-9a-f]+) ds ([0-9a-f]+)')
        media={m['media']:m for m in bank['media']}
        random_request=next((r for r in bank['requests'] if r['pitch_cents_min']!=r['pitch_cents_max']),None)
        work=bank['requests']+([random_request]*(args.pitch_samples-1) if random_request else [])
        for request in work:
            m=media[request['media']];ident=request['request_id']
            wave=(AUDIO/'gu'/f"{m['media']}.wave").read_bytes();n=struct.unpack_from('<I',wave,8)[0]
            start=log.stat().st_size;f.fixture_bytes(mailbox,ident+1)
            deadline=time.monotonic()+4;found=None
            while time.monotonic()<deadline:
                time.sleep(.04)
                with log.open('rb') as stream:stream.seek(start);recent=stream.read().decode('utf8',errors='replace')
                for event in pattern.finditer(recent):
                    v=event.groups()
                    if int(v[3])!=6 or int(v[4])!=m['rate'] or int(v[13])!=m['samples']:continue
                    at=int(v[10],16);coef=int(v[18],16)
                    payload=bytes(f.read(at,f'<{n}B'))
                    if payload!=wave[0x78:0x78+n]:continue
                    assert f.read(coef,'<16h')==struct.unpack_from('<16h',wave,24)
                    assert int(v[5])==1 and int(v[12])==0 and int(v[14])==0
                    static=request.get('pitch_cents',0)
                    pitch_low=2**((static+request['pitch_cents_min'])/1200);pitch_high=2**((static+request['pitch_cents_max'])/1200)
                    assert pitch_low-.001<=float(v[6])<=pitch_high+.001,('Source pitch/range mismatch',v[6],pitch_low,pitch_high)
                    found={'request':ident,'media':m['media'],'native_voice':int(v[1]),
                        'rate':int(v[4]),'samples':int(v[13]),'pitch':float(v[6]),'volume':float(v[7]),
                        'wave_sha256':sha(AUDIO/'gu'/f"{m['media']}.wave"),'adpcm_payload_equal':True,
                        'coefficients_equal':True,'native_log':event[0],
                        'voice_parameters':native_voice(request)}
                    assert abs(found['voice_parameters']['final_pitch']-found['pitch'])<.001,found
                    break
                if found:break
            assert found,('No native voice for request',ident,recent[-600:])
            report['tests'].append(found);print('Native voice verified',ident,m['media'],flush=True)
            time.sleep(m['samples']/m['rate']/2**(request['pitch_cents_min']/1200)+.2)
        if random_request:
            pitches=[t['voice_parameters']['final_pitch'] for t in report['tests'] if t['request']==random_request['request_id']]
            assert len(pitches)==args.pitch_samples
            assert len(set(pitches))>=3 and max(pitches)-min(pitches)>.005,('Pitch did not vary',pitches)
            report['random_pitch_check']={'request':random_request['request_id'],'samples':pitches,'varies':True}
        report['status']='PASS_PRIVATE_NATIVE_AUDIO_TRANSPORT'
    except Exception as exc:
        report['status']='FAIL';report['error']=repr(exc);raise
    finally:
        (f.run/'audio_probe.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
        (PROJECT/'research/world_audio_playback.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
        if not args.keep:(f.run/'stop').touch()
        f.close()
    print(report['status'])

if __name__=='__main__':main()
