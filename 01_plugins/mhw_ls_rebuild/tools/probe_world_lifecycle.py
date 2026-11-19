"""Pad-driven moves interrupted by the real area loader in a copied save.

Warp requests and stations are fixture setup, not evidence of natural traversal.
The assertions cover release of owned animation, attachment and physics state.
"""
import argparse,hashlib,json,time
from pc_fixture import Fixture


def main():
    ap=argparse.ArgumentParser();ap.add_argument('case',choices=['ground_zone','air_zone','down_zone']);args=ap.parse_args()
    f=Fixture();a=f.actor;rows=[];tests=[]
    def sample():
        s=f.state();w=f.read(a+0x23a0)
        s.update(time=time.monotonic(),rate=f.read(a+0x50c,'<f'),
                 weapon_motion=f.read(w+0x4b4,'<H') if w else None)
        rows.append(s);return s
    def wait(test,timeout=10,hold_enemy=False):
        end=time.monotonic()+timeout;poke=0
        while time.monotonic()<end:
            s=sample()
            if test(s):return s
            if hold_enemy and time.monotonic()>poke:f.command('emact 2 5 1');poke=time.monotonic()+.2
            time.sleep(.015)
        raise TimeoutError(s)
    def ready():
        wait(lambda s:s['state']==1 and s['action']<=5)
        if not f.read(a+0x2749,'<B')&1:f.command('X 8');time.sleep(2)
        wait(lambda s:s['state']==1 and s['motion']==0x501)
        time.sleep(.3)
    def thrust():
        f.command('A 8');wait(lambda s:s['action']==4 and s['motion']==0x569 and s['frame']>=27)
    def recovered(zone):
        f.warp(zone);time.sleep(.25)
        s=sample();assert s['state']==1 and s['action']<=5 and s['rate']==1,s
        assert s['motion']<0x5e0 and s['mode']!=2,s
        assert abs(s['position'][1]-s['floor'])<2,s
        ready();thrust()
        assert sample()['weapon_motion']==1,'Native drawn attachment did not recover'
        wait(lambda s:s['state']==1 and s['action']<=5)
        return s
    result={'status':'FAIL','case':args.case,'rows':rows,'tests':tests,
            'plugin_sha256':hashlib.sha256((f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro').read_bytes()).hexdigest(),
            'fixture':'Copied save, native area-loader request and pad-driven moves; no private action or motion is forced.'}
    try:
        if sample()['area']!=0:f.warp(0)
        origin=sample()['position']
        if args.case=='ground_zone':
            for name,key,action,motion in [('sheathe',None,246,0x5e6),('small','X',247,0x5ee),('big','R',248,0x5f5)]:
                if sample()['area']!=0:f.warp(0)
                for off,v in zip((0x40,0x44,0x48),origin):f.fixture_bytes(a+off,v,'<f')
                ready();f.fixture_bytes(a+0x3330,3);f.fixture_bytes(a+0x332c,6000.,'<f')
                thrust();f.command('R 24\nB 24')
                wait(lambda s:s['action']==246 and s['motion']==0x5e6 and s['frame']>=85)
                if key:
                    f.command(key+' 10');wait(lambda s:s['action']==action and s['motion']==motion)
                before=sample();after=recovered(1)
                assert after['rank']==before['rank']-(1 if name=='big' else 0),(name,before,after)
                tests.append({'move':name,'before':before,'after':after})
        else:
            en=next(e for e in sample()['enemies'] if e['uid']==0)
            f.warp(en['area']);time.sleep(2);s=sample();en=next(e for e in s['enemies'] if e['uid']==0)
            assert en['area']==s['area'];target=en['actor'];f.command('emact 2 5 1')
            f.fixture_bytes(a+0x13d6,100,'<h');f.fixture_bytes(target+0x17b0,3000)
            for other in s['enemies']:
                if other['actor']!=target and other['area']==s['area']:f.fixture_bytes(other['actor']+0x17b0,0)
            x,y,z=en['position']
            for off,v in zip((0x40,0x44,0x48),(x,y,z-800)):f.fixture_bytes(a+off,v,'<f')
            ready();f.fixture_bytes(a+0x3330,3);f.fixture_bytes(a+0x332c,6000.,'<f');f.fixture_bytes(a+0x2780,100)
            thrust();f.command('R 30\nX 30')
            wait(lambda s:s['action']==241 and s['motion']==0x5e1 and s['frame']>=82,hold_enemy=True)
            en=next(e for e in sample()['enemies'] if e['actor']==target)
            for off,v in zip((0x40,0x44,0x48),(en['position'][0],en['position'][1],en['position'][2]-200)):f.fixture_bytes(a+off,v,'<f')
            f.fixture_bytes(a+0xfec,0);f.fixture_bytes(a+0x14a0,0)
            before=wait(lambda s:s['action']==243 and s['motion']==0x5e3 and s['frame']>=4,hold_enemy=True)
            assert before['position'][1]>before['floor']+10 and before['gravity']<-.4,before
            if args.case=='down_zone':
                f.command('X 70');before=wait(lambda s:s['action']==244 and s['motion']==0x5e4 and s['frame']>=4,hold_enemy=True)
            after=recovered(0)
            assert after['rank']==before['rank']-(1 if args.case=='down_zone' else 0),(before,after)
            tests.append({'move':'helm_'+('down' if args.case=='down_zone' else 'air'),'before':before,'after':after})
        result['status']='PASS_NATIVE_'+args.case.upper()
        result['limits']='Checks actual load/unload recovery. Natural boundary traversal, fainting, actor replacement and emitted-shell lifetime are separate cases.'
    finally:
        (f.run/('lifecycle_'+args.case+'.json')).write_text(json.dumps(result,indent=2),encoding='utf8')
        print(result['status'],[(t['move'],t['before']['rank'],t['after']['rank']) for t in tests]);f.close()


if __name__=='__main__':main()
