"""Real output PCM + native requests and effect creation, including negative branches."""
import json,re,threading,time,wave
import numpy as np
import pyaudiowpatch as pa
from scipy.io import wavfile
from scipy.signal import correlate,resample_poly
from pc_fixture import Fixture
from animation_port import ROOT,PROJECT,sha

def main():
    f=Fixture();a=f.actor;cases=[];bank=json.loads((PROJECT/'research/world_audio_bank.json').read_text(encoding='utf8'))
    report={'status':'FAIL','plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
        'audio_arc_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_audio.arc'),
        'fx_arc_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_simple_fx.arc'),'cases':cases}
    assert report['audio_arc_sha256']==bank['arc_sha256']
    log=f.run/'log.txt';audio=pa.PyAudio();device=audio.get_default_wasapi_loopback();rate=int(device['defaultSampleRate']);channels=device['maxInputChannels']
    stream=audio.open(format=pa.paInt16,channels=channels,rate=rate,input=True,input_device_index=device['index'],frames_per_buffer=480)
    chunks=[];done=threading.Event()
    def capture():
        while not done.is_set():chunks.append(stream.read(480,exception_on_overflow=False))
    thread=threading.Thread(target=capture);thread.start()
    def wait(test,timeout=12):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            s=f.state()
            if test(s):return s
            time.sleep(.005)
        raise TimeoutError(s)
    def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
    def setup(rank,gauge):
        idle();f.camp_station()
        if not f.read(a+0x2749,'<B')&1:f.command('X 8');time.sleep(2);idle()
        f.fixture_values([(a+0x3330,rank,'<I'),(a+0x2780,gauge,'<I'),(a+0x332c,6000.,'<f')]);time.sleep(.15)
    try:
        for move,rank,gauge in [('foresight',0,0),('foresight',0,100),('thrust',0,100),('thrust',1,100),('thrust',2,100),('thrust',3,100),('thrust',1,0)]:
            setup(rank,gauge);source=140 if move=='foresight' else 170;request=25606 if source==140 else 25515
            layered=b'presentation=world-layers-v102' in (f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro').read_bytes()
            uid=(0x3d03 if source==140 else 0x3d22) if layered else (0x3f69 if source==140 else 0x3f6a)
            expected=gauge>=10 if source==140 else rank>=1
            start=log.stat().st_size;audio_start=len(chunks)
            if source==140:
                f.command('A 2');wait(lambda s:(s['action'],s['motion']) in ((4,0x569),(250,0x590)) and s['frame']>=22)
                f.command('R 24\nA 24')
            else:f.command('R 16\nX 16')
            entered=wait(lambda s:s['motion']==0x500+(224 if source==140 else 225))
            wait(lambda s:s['motion']==entered['motion']and s['frame']>=100)
            idle();time.sleep(.4);audio_end=len(chunks)
            with log.open('rb')as streamlog:streamlog.seek(start);text=streamlog.read().decode(errors='replace')
            cues=re.findall(r'world_audio_cue [0-9A-F]+ ([0-9A-F]+) ([0-9A-F]+)',text)
            found=[int(frame,16)/1000 for req,frame in cues if int(req,16)==request]
            assert len(found)==int(expected),(move,rank,gauge,found)
            fx=re.findall(r'world_simple_fx_emit [0-9A-F]+ ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+)',text)
            created=[int(ok,16)for ident,src,ok in fx if int(ident,16)==uid and int(src,16)==source]
            assert created==([1]if expected else []),(move,rank,created)
            if found:assert found[0]<(8 if source==140 else 92)and found[0]>=(0 if source==140 else 84)
            native_ids=[r['request_id']for r in bank['requests']if r.get('source_request')==request]
            plays=[int(i,16)for i in re.findall(r'world_audio_play [0-9A-F]+ ([0-9A-F]+)',text) if int(i,16)in native_ids]
            assert sorted(plays)==(sorted(native_ids)if expected else []),(move,rank,plays)
            pcm=b''.join(chunks[audio_start:audio_end]);name=f'conditional_{move}_{rank}_{gauge}.wav'
            with wave.open(str(f.run/name),'wb')as w:w.setnchannels(channels);w.setsampwidth(2);w.setframerate(rate);w.writeframes(pcm)
            y=np.frombuffer(pcm,dtype='<i2').reshape(-1,channels).astype(float)/32768;matches=[]
            for r in bank['requests']:
                if r.get('source_request')!=request:continue
                sr,x=wavfile.read(ROOT/f'.cache/mhw_ls_presentation/audio/wav/{r["media"]}.wav');x=x.astype(float)/32768
                if sr!=rate:x=resample_poly(x,rate,sr)
                x=x-x.mean();best=None
                for ch in range(channels):
                    corr=correlate(y[:,ch],x,mode='valid',method='fft');i=int(np.argmax(np.abs(corr)));part=y[i:i+len(x),ch]
                    v={'media':r['media'],'channel':ch,'time':i/rate,'correlation':float(corr[i]/max(1e-15,np.sqrt(np.dot(x,x)*np.dot(part,part)))),
                        'gain':float(corr[i]/np.dot(x,x))}
                    if best is None or abs(v['correlation'])>abs(best['correlation']):best=v
                matches.append(best)
            if expected:assert all(abs(m['correlation'])>.10 for m in matches),(move,rank,matches)
            else:assert all(abs(m['correlation'])<.15 for m in matches),(move,rank,matches)
            cases.append({'move':move,'rank':rank,'gauge':gauge,'expected':expected,'source_request':request,'frames':found,
                'native_requests':plays,'effects_created':created,'pcm':name,'pcm_sha256':sha(f.run/name),'source_matches':matches,
                'peak':float(np.max(np.abs(y)))})
            print('PASS',move,rank,gauge,'special',expected,'correlations',[round(m['correlation'],3)for m in matches],flush=True)
        report['status']='PASS_CONDITIONAL_SOURCE_SFX_PCM_AND_FLASH'
    except Exception as e:report['error']=repr(e);raise
    finally:
        done.set();thread.join(3);stream.close();audio.terminate();f.close()
        (f.run/'conditional_presentation.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')

if __name__=='__main__':main()
