"""Exercise the installed release palette using real action input."""
import json,re,time
from pc_fixture import Fixture
from animation_port import PROJECT,sha

def main():
    f=Fixture();log=f.run/'log.txt';cases=[]
    report={'status':'FAIL','run':str(f.run),'cases':cases,
        'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
        'audio_arc_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_audio.arc'),
        'fx_arc_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_simple_fx.arc'),
        'style':'Native effects emitted by the installed weapon mod.'}
    def wait(test,seconds=12):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            s=f.state()
            if test(s):return s
            time.sleep(.01)
        raise TimeoutError(s)
    def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
    def text(start):
        with log.open('rb')as stream:stream.seek(start);return stream.read().decode(errors='replace')
    try:
        t=log.read_text(errors='replace');layered='presentation=world-layers-v102' in t
        assert (layered or 'presentation=simple-native-v1' in t) and 'world_simple_fx_ready' in t
        assert 'fx-probe-only=1' not in t and 'audio-probe-only=1' not in t
        assert 'world_simple_fx_failed' not in t
        f.camp_station()
        origin=f.state()['position']
        for source,slot,frame in [(140,224,72),(170,225,86),(307,238,37),(311,245,20)]:
            idle()
            for off,v in zip((0x40,0x44,0x48),origin):f.fixture_bytes(f.actor+off,v,'<f')
            f.fixture_values([(f.actor+0x332c,6000.,'<f'),(f.actor+0x3330,3,'<I'),(f.actor+0x2780,100,'<I')])
            if not f.read(f.actor+0x2749,'<B')&1:f.command('X 8');time.sleep(2);idle()
            time.sleep(.3);start=log.stat().st_size
            f.command('A 8');wait(lambda s:s['motion']==0x569 and s['frame']>=24)
            if source in (140,170):f.command('R 24\n'+('A'if source==140 else'X')+' 24')
            else:
                f.command('R 24\nB 24');wait(lambda s:s['motion']==0x5e6 and s['frame']>=35)
                f.command('shot simple_sheathe');wait(lambda s:s['motion']==0x5e6 and s['frame']>=90)
                f.command(('X'if source==307 else'R')+' 10')
            wait(lambda s:s['motion']==0x500+slot and s['frame']>=frame)
            f.command('shot simple_'+str(source));idle();time.sleep(.2)
            t=text(start);emits=[[int(v,16)for v in row]for row in re.findall(r'world_simple_fx_emit [0-9A-F]+ ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+)',t)]
            assert emits and all(ok==1 for uid,clip,ok in emits),emits
            assert any(uid=={140:0x3d02 if layered else 0x3f85,170:0x3d17 if layered else 0x3f80,307:0x3f85,311:0x3f64}[source] and clip==source for uid,clip,ok in emits),(source,emits)
            if source in (307,311):
                assert sum(uid==0x3f60 and clip==306 for uid,clip,ok in emits)==2,emits
                if source==307:assert not any(uid in (0x3f65,0x3f87) and clip==307 for uid,clip,ok in emits),emits
                else:assert not any(uid==0x3fc1 and clip==311 for uid,clip,ok in emits),emits
            if source==170:assert any(uid==(0x3d16 if layered else 0x3f85) and clip==170 for uid,clip,ok in emits),emits
            cases.append({'source':source,'native_effects':emits});print('Simple effects verified',source,len(emits),flush=True)
        report['status']='PASS_WORLD_LAYER_PRESENTATION' if layered else 'PASS_SIMPLIFIED_PRESENTATION'
    except Exception as exc:report['error']=repr(exc);raise
    finally:
        (f.run/'simple_presentation.json').write_text(json.dumps(report,indent=2)+'\n')
        (PROJECT/'research/world_simple_presentation.json').write_text(json.dumps(report,indent=2)+'\n');f.close()
    print(report['status'])

if __name__=='__main__':main()
