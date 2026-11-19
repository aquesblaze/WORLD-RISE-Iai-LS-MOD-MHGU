"""Observe the actual native weapon layer while pad input drives each transition."""
import argparse,hashlib,json,math,time
from pathlib import Path
from pc_fixture import Fixture

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--shots',action='store_true');args=ap.parse_args()
    f=Fixture();a=f.actor;rows=[];tests=[]
    curves=json.loads((Path(__file__).resolve().parents[1]/'research/weapon_transition_assets.json').read_text(encoding='utf8'))['source_deployment_fraction']
    def sample():
        s=f.state();w=f.read(a+0x23a0)
        assert w and f.read(w+0x30)==a and f.read(w+0x13d0)==9
        s.update(time=time.monotonic(),weapon=w,weapon_motion=f.read(w+0x4b4,'<H'),
            weapon_frame=f.read(w+0x500,'<f'),weapon_rate=f.read(w+0x50c,'<f'))
        n=f.read(w+0x490);bones=f.read(w+0x494);assert 0<n<32 and bones
        s['weapon_bone_axes']=[]
        for i in range(n):
            m=f.read(bones+160*i+0x10,'<16f')
            s['weapon_bone_axes'].append([math.sqrt(sum(m[k+j]*m[k+j] for j in range(3))) for k in (0,4,8)])
        s['blade_scale']=f.read(bones+160+0x70,'<3f')
        # ReadProcessMemory is not a simulation-frame snapshot. A native layer
        # change can occur between the motion, clock and matrix reads above.
        # Reject torn samples, while retaining them in the raw evidence.
        s['coherent']=((f.read(a+0x4b4,'<H'),f.read(a+0x500,'<f'),
                       f.read(w+0x4b4,'<H'),f.read(w+0x500,'<f'))==
                      (s['motion'],s['frame'],s['weapon_motion'],s['weapon_frame']))
        rows.append(s);return s
    def wait(test,timeout=10):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            s=sample()
            if test(s):return s
            time.sleep(.004)
        raise TimeoutError(s)
    def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
    result={'status':'FAIL','rows':rows,'tests':tests,'plugin_sha256':hashlib.sha256((f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro').read_bytes()).hexdigest()}
    try:
        f.camp_station()
        origin=sample()['position']
        for name,key,action,motion in [('small','X',247,0x5ee),('big','R',248,0x5ef)]:
            idle()
            for off,v in zip((0x40,0x44,0x48),origin):f.fixture_bytes(a+off,v,'<f')
            if not f.read(a+0x2749,'<B')&1:f.command('X 8');time.sleep(2);idle()
            time.sleep(.3);f.command('A 8')
            wait(lambda s:s['action']==4 and s['motion']==0x569 and s['frame']>=18)
            start=len(rows);f.command('R 24\nB 24')
            wait(lambda s:s['action']==246 and s['motion']==0x5e6 and s['frame']>=71)
            if args.shots:f.command('shot weapon_close_'+name)
            wait(lambda s:s['action']==246 and s['frame']>=90)
            close=[r for r in rows[start:] if r['coherent'] and r['motion']==0x5e6 and r['weapon_motion']==221]
            assert len({round(r['weapon_frame'],2) for r in close})>=2,'Need two actual closing poses'
            assert sample()['weapon_motion']==0
            assert abs(sample()['blade_scale'][2]-.75)<.001,'Closed shape not evaluated'
            valid_motions=(motion,) if name=='small' else (0x5ef,0x5f0,0x5f1,0x5f5)
            f.command(key+' 10');wait(lambda s:s['action']==action and s['motion'] in valid_motions)
            if args.shots:f.command('shot weapon_draw_'+name)
            wait(lambda s:s['action']==action and s['frame']>=14)
            draw=[r for r in rows[start:] if r['coherent'] and r['action']==action and r['weapon_motion']==220]
            assert len({round(r['weapon_frame'],2) for r in draw})>=2,'Need two actual drawing poses'
            assert sample()['weapon_motion']==1
            assert abs(sample()['blade_scale'][2]-1)<.001,'Open shape not evaluated'
            for r in close+draw:
                expected=r['frame']-(73 if r in close else 0)
                assert abs(expected-r['weapon_frame'])<=1.6,(expected,r['weapon_frame'])
                curve=curves['3' if r in close else '2'];n=min(int(r['weapon_frame']),9);frac=min(r['weapon_frame']-n,1)
                scale=.75+.25*(curve[n]*(1-frac)+curve[n+1]*frac)
                assert abs(r['blade_scale'][2]-scale)<.003,(r['weapon_frame'],r['blade_scale'],scale)
            # This fixture's native blade scales on deployment. Check the
            # evaluated model matrices too, rather than certify only layer IDs.
            change=max(max(r['weapon_bone_axes'][i][k] for r in draw)-min(r['weapon_bone_axes'][i][k] for r in draw)
                       for i in range(len(draw[0]['weapon_bone_axes'])) for k in range(3))
            assert change>.02,('No evaluated blade deployment',change)
            idle();time.sleep(.2)
            assert sample()['weapon_motion']==1,'Native drawn pose not restored'
            tests.append({'move':name,'close_samples':len(close),'draw_samples':len(draw),'posed_axis_length_change':change,
                'close_frame_range':[min(r['weapon_frame'] for r in close),max(r['weapon_frame'] for r in close)],
                'draw_frame_range':[min(r['weapon_frame'] for r in draw),max(r['weapon_frame'] for r in draw)]})
        result['status']='PASS_NATIVE_WEAPON_TRANSITIONS'
        result['weapon_assets']={str(p.relative_to(f.run)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in (f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/weapon/w07').glob('g*.arc')}
        result['limits']='Native layer and clock verified on the equipped weapon. Other group banks passed encoding checks; their individual equipment visuals remain to be checked.'
    finally:
        (f.run/'weapon_transitions.json').write_text(json.dumps(result,indent=2),encoding='utf8')
        print(result['status'],tests);f.close()

if __name__=='__main__':main()
