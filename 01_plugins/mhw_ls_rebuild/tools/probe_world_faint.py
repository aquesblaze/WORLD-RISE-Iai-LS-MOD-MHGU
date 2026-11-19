"""Real native faint/recovery from a monster hit during special sheathe.

Station, enemy attack selection and HP1 are explicit copied-save fixtures;
neither the hunter's action nor a death/recovery state is forced.
"""
import json,re,time
from pc_fixture import Fixture
from animation_port import sha

def main():
    f=Fixture();log=f.run/'log.txt';rows=[]
    report={'status':'FAIL','run':str(f.run),'rows':rows,'hp_fixture':1,
        'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro')}
    log_offset=0
    def state():
        nonlocal log_offset
        with log.open('rb')as stream:
            stream.seek(log_offset);recent=stream.read().decode(errors='replace');log_offset=stream.tell()
        matches=re.findall(r'local_actor ([0-9A-F]+)',recent)
        if matches:
            actor=int(matches[-1],16)
            if actor!=f.actor:
                assert f.read(actor)==0x194cf64,'Unexpected replacement actor'
                f.actor=actor;f.meta['actor']=actor
                (f.run.parents[1]/'active_session.json').write_text(json.dumps(f.meta))
        s=f.state();s['rate']=f.read(f.actor+0x50c,'<f');s['actor']=f.actor;rows.append(s);return s
    def wait(test,seconds=15,hold=False):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            s=state()
            if test(s):return s
            if hold:f.command('emact 2 5 1')
            time.sleep(.025)
        raise TimeoutError(s)
    try:
        s=state();enemy=next(e for e in s['enemies']if e['uid']==0)
        if s['area']!=enemy['area']:f.warp(enemy['area']);time.sleep(2)
        s=state();enemy=next(e for e in s['enemies']if e['uid']==0);en=enemy['actor']
        for other in s['enemies']:
            if other['actor']!=en and other['area']==s['area']:f.fixture_bytes(other['actor']+0x17b0,0)
        f.fixture_bytes(en+0x17b0,30000);f.command('emact 2 5 1')
        station={5:(-1000.,-30.,1600.),6:(-2000.,-22.5,-3400.),7:(0.,0.,0.)}.get(s['area'],enemy['position'])
        for actor in (en,f.read(en+0x1428)):
            for off,v in zip((0x40,0x44,0x48),station):f.fixture_bytes(actor+off,v,'<f')
        for off,v in zip((0x40,0x44,0x48),(station[0],station[1],station[2]+700)):f.fixture_bytes(f.actor+off,v,'<f')
        wait(lambda s:s['state']==1 and s['action']<=5,hold=True)
        f.fixture_bytes(f.actor+0x13d6,100,'<h')
        if not f.read(f.actor+0x2749,'<B')&1:f.command('X 8');time.sleep(2)
        f.command('A 8');wait(lambda s:s['motion']==0x569 and s['frame']>=24,hold=True)
        # Leave enough native sheathe time for the unmodified monster windup.
        # Starting at85 can land after the stance expires on a long frame,
        # proving ordinary fainting instead of private-action teardown.
        f.command('R 24\nB 24');before=wait(lambda s:s['motion']==0x5e6 and s['frame']>=35,hold=True)
        f.fixture_bytes(f.actor+0x13d6,1,'<h');f.fixture_bytes(f.actor+0x13da,1,'<h')
        report['recoverable_hp_fixture']=1
        f.fixture_bytes(en+0xfec,0);f.fixture_bytes(en+0x14a0,0)
        start=log.stat().st_size;f.command('emact 7 14 0');end=time.monotonic()+6;dead=None
        while time.monotonic()<end:
            s=state()
            if s['hp']<=0:dead=s;break
            # Keep the hunter on its settled native floor. Dragging it after
            # a jumping monster can cross a ledge and cancel the stance before
            # damage. Align only the enemy'sXZ; its attack/height stay native.
            for owner in (en,f.read(en+0x1428)):
                f.fixture_bytes(owner+0x40,s['position'][0],'<f')
                f.fixture_bytes(owner+0x48,s['position'][2],'<f')
            time.sleep(.02)
        assert dead,'Native attack did not faint hunter'
        after=wait(lambda s:s['motion']<0x5e0 and s['rate']==1,seconds=5)
        recovered=wait(lambda s:s['hp']>0 and s['area']==0 and s['state']==1 and s['action']<=5,seconds=45)
        f.command('X 8');wait(lambda s:s['state']==1 and s['action']<=5,seconds=8);time.sleep(1.5)
        f.command('A 8');wait(lambda s:s['motion']==0x569 and s['frame']>=24)
        f.command('R 24\nB 24');wait(lambda s:s['motion']==0x5e6 and s['frame']>=90)
        f.command('X 8');wait(lambda s:s['motion']==0x5ee);wait(lambda s:s['state']==1 and s['action']<=5)
        with log.open('rb')as stream:stream.seek(start);events=stream.read().decode(errors='replace')
        assert 'world_incoming' in events,'Missing native damage evidence'
        assert 'world_simple_fx_failed' not in events
        assert re.search(r'world_simple_fx_emit [0-9A-F]+ 00003F60 .* 00000001',events)
        report.update(status='PASS_NATIVE_FAINT_RECOVERY',before=before,faint=dead,cleared=after,recovered=recovered,
            actor_replaced=before['actor']!=recovered['actor'],fixture='HP1, station, enemyXZ alignment and monster attack; native damage, faint and recovery; pad-driven moves before/after.')
        print(report['status'],'actor replaced',report['actor_replaced'])
    except Exception as exc:report['error']=repr(exc);raise
    finally:
        (f.run/'faint_recovery.json').write_text(json.dumps(report,indent=2)+'\n');f.close()

if __name__=='__main__':main()
