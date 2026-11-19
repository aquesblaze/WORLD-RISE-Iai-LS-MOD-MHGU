"""Verify native private EFL spawn/lifetime; visual source parity is separate."""
import json,re,struct,time
from pc_fixture import Fixture
from animation_port import PROJECT,sha

def main():
    f=Fixture();log=f.run/'log.txt';report={'run':str(f.run),'status':'FAIL',
        'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
        'source_visual_parity':False,'installed':False}
    try:
        text=log.read_text(errors='replace')
        m=re.search(r'world_fx_queued [0-9A-F]+ [0-9A-F]+ ([0-9A-F]+)',text)
        assert m and 'world_fx_ready' in text,'Native FX archive not ready'
        report['arc_sha256']=sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_effects.arc')
        start=log.stat().st_size;f.command('shot fx_baseline');time.sleep(.15)
        f.fixture_bytes(int(m[1],16),1);time.sleep(.12);f.command('shot fx_early')
        recent=log.read_text(errors='replace').split('world_fx_origin')[-1]
        e=re.search(r'world_fx_step ([0-9A-F]+)',recent);assert e,recent
        effect=int(e[1],16);native_origin=f.read(effect+64,'<3f')
        particle=f.read(f.read(effect+496)+176);brightness=f.read(particle+88,'<f')
        bank=json.loads((PROJECT/'research/world_effect_probe_bank.json').read_text())
        assert brightness==bank['brightness']==20,brightness
        time.sleep(.2);f.command('shot fx_mid');time.sleep(1);f.command('shot fx_late');time.sleep(.2)
        with log.open('rb') as stream:stream.seek(start);text=stream.read().decode(errors='replace')
        events={}
        for line in text.splitlines():
            m=re.search(r'ML_REBUILD: (world_fx_\w+) ((?:[0-9A-F]+ ?){4})',line)
            if m:events.setdefault(m[1],[]).append([int(v,16) for v in m[2].split()])
        assert len(events.get('world_fx_emit',[]))==1,events
        origin=events.get('world_fx_origin',[]);assert len(origin)==1,events
        point=[struct.unpack('<f',struct.pack('<I',v))[0]for v in origin[0][1:]]
        expected=list(f.state()['position']);expected[1]+=100
        assert max(abs(a-b)for a,b in zip(point,expected))<.01,point
        assert max(abs(a-b)for a,b in zip(point,native_origin))<.01,native_origin
        particles=events.get('world_fx_particle',[]);assert len(particles)==1,events
        p=particles[0];size,aspect=[struct.unpack('<f',struct.pack('<I',v))[0]for v in p[1:3]]
        assert p[3]==1 and abs(size-50/128)<1e-5 and aspect==1,particles
        life=events.get('world_fx_life',[]);assert len(life)==1,events
        assert life[0][1]==0 and life[0][2]&65535==43,life
        steps=events.get('world_fx_step',[]);assert len(steps)>5,events
        # The callback precedes simulation, whose delta can skip integer ages.
        # Configured lifetime is checked above; these samples only check that
        # the native instance ran and stopped within the observation window.
        ages=[s[1] for s in steps];assert 35<=max(ages)<=44,ages
        report.update(status='PASS_NATIVE_SINGLE_BILLBOARD_TRANSPORT',events=events,
            size=size,aspect=aspect,brightness=brightness,life_fade_frames=life[0][2]&65535,native_origin=native_origin,
            screenshots=[str(f.run/'shots'/f'fx_{n}.png')for n in ['baseline','early','mid','late']],
            limits=['One native template billboard only. This report does not validate the World shader, source attachment, six-emitter composition or original lifetime parity.'])
        print(report['status'],'size',size,'fade',report['life_fade_frames'])
    except Exception as exc:
        report['error']=repr(exc);raise
    finally:
        (f.run/'effect_probe.json').write_text(json.dumps(report,indent=2)+'\n')
        (PROJECT/'research/world_effect_playback.json').write_text(json.dumps(report,indent=2)+'\n')
        f.close()

if __name__=='__main__':main()
