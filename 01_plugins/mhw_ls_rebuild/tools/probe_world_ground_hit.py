"""Explicit collision fixture for the ground moves; inputs drive all transitions."""
import argparse,hashlib,json,re,time
from pc_fixture import Fixture

def main():
    ap=argparse.ArgumentParser();ap.add_argument('move',choices=['foresight','small','big'])
    ap.add_argument('--regen-check',action='store_true')
    ap.add_argument('--rank',type=int,choices=range(4),default=3)
    ap.add_argument('--whiff',action='store_true')
    ap.add_argument('--station-offset',type=float,nargs=2,default=(0.,0.),metavar=('X','Z'),help='Explicit copied-save station offset, e.g. to avoid native camera obstruction')
    ap.add_argument('--contact-gap',type=float,default=150.,help='Explicit hunter/target Z separation in the native collision fixture')
    ap.add_argument('--contact-offset-x',type=float,default=0.,help='Explicit lateral hunter/target separation for camera turn fixtures')
    ap.add_argument('--static-contact-station',action='store_true',help='Position before Iai only; leave its native dash/contact path untouched')
    args=ap.parse_args()
    f=Fixture();a=f.actor;rows=[]
    def wait(test,seconds=8):
        until=time.monotonic()+seconds;wake=0
        while time.monotonic()<until:
            f.command('emact 2 5 1');s=f.state()
            if test(s):return s
            if s['state']==64 and s['frame']>60 and time.monotonic()>wake:
                f.command('B 8');wake=time.monotonic()+.6
            time.sleep(.025)
        raise TimeoutError(s)
    try:
        # A long regression can catch the monster changing areas during our
        # own load. Track its current area, keeping the fixture's idle action.
        for attempt in range(3):
            enemy=next(e for e in f.state()['enemies'] if e['uid']==0)
            f.command('emact 2 5 1')
            if f.state()['area']!=enemy['area']:f.warp(enemy['area']);time.sleep(3)
            s=f.state();enemy=next(e for e in s['enemies'] if e['uid']==0)
            if enemy['area']==s['area']:break
        assert enemy['area']==s['area'];target=enemy['actor']
        station={5:(-1000.,-30.,1600.),6:(-2000.,-22.5,-3400.),7:(0.,0.,0.)}.get(s['area'],enemy['position'])
        station=(station[0]+args.station_offset[0],station[1],station[2]+args.station_offset[1])
        f.command('emact 2 5 1')
        for owner in (target,f.read(target+0x1428)):
            for off,v in zip((0x40,0x44,0x48),station):f.fixture_bytes(owner+off,v,'<f')
        for other in s['enemies']:
            if other['actor']!=target and other['area']==s['area']:f.fixture_bytes(other['actor']+0x17b0,0)
        time.sleep(.3);s=f.state();enemy=next(e for e in s['enemies']if e['actor']==target)
        f.fixture_bytes(target+0x17b0,3000);f.fixture_bytes(target+0x17b4,3000)
        f.fixture_bytes(a+0x13d6,100,'<h')
        for off,v in zip((0x40,0x44,0x48),(enemy['position'][0],enemy['position'][1],enemy['position'][2]-800)):
            f.fixture_bytes(a+off,v,'<f')
        # A previous live encounter can leave native stun active. Recovery
        # keeps the normal mash input above; give its native timer time to end.
        wait(lambda s:s['state']==1 and s['action']<=5,seconds=20)
        if not f.read(a+0x2749,'<B')&1:
            f.command('X 8');time.sleep(3)
        wait(lambda s:s['state']==1 and s['action']<=5 and s['motion']==0x501)
        time.sleep(.3)
        f.fixture_bytes(a+0x3330,args.rank);f.fixture_bytes(a+0x332c,6000.,'<f');f.fixture_bytes(a+0x2780,100)
        # Reading the accumulated audio trace during the attack can take
        # longer than its first hit window. Resolve telemetry before input.
        matches=re.findall(r'world_camera_owner '+f'{a:08X}'+r' (\w+)',(f.run/'log.txt').read_text(errors='replace')) if args.move=='big' else []
        camera=int(matches[-1],16) if matches else 0
        log_start=(f.run/'log.txt').stat().st_size
        f.command('A 8');wait(lambda s:s['state']==16 and s['action']==4 and s['motion']==0x569 and s['frame']>=27)
        if args.move=='foresight':f.command('R 24\nA 24');action=240
        else:
            f.command('R 24\nB 24');wait(lambda s:s['action']==246 and s['motion']==0x5e6 and s['frame']>=80)
            if not args.whiff:
                # Establish contact station while safely sheathed. Waiting
                # until Iai frame4 can miss both brief blade windows when a
                # rendering step and the control-file drain arrive together.
                enemy=next(e for e in f.state()['enemies']if e['actor']==target)
                for off,v in zip((0x40,0x44,0x48),(enemy['position'][0]+args.contact_offset_x,enemy['position'][1],enemy['position'][2]-args.contact_gap)):
                    f.fixture_bytes(a+off,v,'<f')
                f.fixture_bytes(a+0xfec,0);f.fixture_bytes(a+0x14a0,0)
                time.sleep(.1)
            f.command(('X' if args.move=='small' else 'R')+' 10');action=247 if args.move=='small' else 248
        expected_motion=0x5e0 if action==240 else 0x5ee if action==247 else (0x5ef,0x5f0,0x5f1,0x5f5)[args.rank]
        wait(lambda s:s['action']==action and s['motion']==expected_motion)
        end=time.monotonic()+12;regen_reset=False;regen_start=None;regen_result=None;next_idle=0
        while time.monotonic()<end:
            if time.monotonic()>=next_idle:
                f.command('emact 2 5 1');next_idle=time.monotonic()+.25
            s=f.state();rows.append({'time':time.monotonic(),**s})
            if args.move=='big':
                if not camera:
                    text=(f.run/'log.txt').read_text(errors='replace')
                    matches=re.findall(r'world_camera_owner '+f'{a:08X}'+r' (\w+)',text)
                    if matches:camera=int(matches[-1],16)
                if camera and f.read(camera+0x85c)==a:
                    rows[-1]['camera']={'address':camera,'target_angles':f.read(camera+0x9e8,'<2I'),
                        'angles':f.read(camera+0x9e0,'<2I'),'final_angles':f.read(camera+0x9d8,'<2I'),
                        'eye':f.read(camera+0x40,'<3f'),'look_at':f.read(camera+0x60,'<3f')}
            frame=s['frame']
            if args.regen_check and args.move=='small' and not regen_reset and s['action']==247 and frame>=42:
                f.fixture_bytes(a+0x2780,0);f.fixture_bytes(a+0x3334,0.,'<f')
                f.fixture_bytes(a+0x3328,1.,'<f');regen_reset=True
            if regen_reset and regen_start is None and s['gauge']==0:regen_start=time.monotonic()
            if regen_start is not None and regen_result is None and time.monotonic()-regen_start>=5:
                regen_result={'seconds':time.monotonic()-regen_start,'gauge':s['gauge'],'expected_rate':100/15}
            window=(60<frame<80) if action==240 else (4<frame<37)
            if s['action']==action and window and not args.whiff and not args.static_contact_station:
                enemy=next(e for e in s['enemies'] if e['actor']==target)
                assert enemy['area']==s['area']
                for off,v in zip((0x40,0x44,0x48),(enemy['position'][0]+args.contact_offset_x,enemy['position'][1],enemy['position'][2]-args.contact_gap)):
                    f.fixture_bytes(a+off,v,'<f')
                f.fixture_bytes(a+0xfec,0);f.fixture_bytes(a+0x14a0,0)
            time.sleep(.02)
        out={'status':'OBSERVATION_ONLY','move':args.move,'target':target,'rows':rows,'regen_result':regen_result,
             'interior_station_fixture':station,'contact_gap_fixture':args.contact_gap,'non_target_enemies_removed_fixture':True,
             'plugin_sha256':hashlib.sha256((f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro').read_bytes()).hexdigest()}
        if args.regen_check:
            passed=bool(regen_result and 30<=regen_result['gauge']<=35)
            out['status']='PASS_REGEN_RATE_ONLY' if passed else 'FAIL_REGEN_RATE'
        with (f.run/'log.txt').open('rb') as log:log.seek(log_start);events=log.read().decode('utf8',errors='replace')
        out.update(rank_fixture=args.rank,whiff_fixture=args.whiff,camera_events=[x for x in events.splitlines() if 'world_camera_' in x])
        out['position_before_iai_input_fixture']=args.move!='foresight' and not args.whiff
        out['static_contact_station_fixture']=args.static_contact_station
        out['contact_offset_x_fixture']=args.contact_offset_x
        out['monster_idle_request_interval_seconds_fixture']=.25
        suffix=(f'_rank{args.rank}' if args.rank!=3 else '')+('_whiff' if args.whiff else '')
        (f.run/f'ground_{args.move}{suffix}.json').write_text(json.dumps(out,indent=2))
        if args.regen_check:assert passed,regen_result
        prev=None;changes=[]
        for s in rows:
            hp=next(e['hp'] for e in s['enemies'] if e['actor']==target)
            if prev is not None and hp!=prev:changes.append((s['action'],round(s['frame'],2),prev-hp,s['rank']))
            prev=hp
        print(args.move,'HP changes',changes,'rank',rows[0]['rank'],rows[-1]['rank'],'gauge',rows[0]['gauge'],rows[-1]['gauge'])
        if regen_result:print(regen_result)
        f.warp(0)
    finally:f.close()

if __name__=='__main__':main()
