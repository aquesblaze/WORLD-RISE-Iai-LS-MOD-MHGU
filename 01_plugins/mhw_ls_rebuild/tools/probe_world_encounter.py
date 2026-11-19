"""Combat fixture: copied save, native area transition, explicit positioning/rank.

Player actions are driven by pad input. Setup mutations are recorded separately;
they are never used as evidence of a legitimate combo, hit or damage outcome.
"""
import argparse,json,time,re
from pc_fixture import Fixture

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--landing-follow',choices=['sheathe','foresight'])
    ap.add_argument('--rank',type=int,choices=[1,2,3],default=3)
    ap.add_argument('--primary-limit',type=int,choices=range(1,7),help='Move the hunter away after this many real primary contacts to exercise the source tail fallback')
    ap.add_argument('--air-turn',action='store_true',help='Hold left during the real airborne phase and record angular speed')
    ap.add_argument('--auto-down',action='store_true',help='Release every attack key after thrust; require the native airborne chain to finish automatically')
    ap.add_argument('--film-land',action='store_true',help='Capture consecutive frames of the landing impact')
    ap.add_argument('--fall-reset-frame',type=float,help='Copied-save fault injection: clear fall speed/gravity once during the dive')
    ap.add_argument('--mobile-target',action='store_true',help='Release the native monster AI when the hunter starts rising')
    args=ap.parse_args()
    f=Fixture();a=f.actor;rows=[]
    try:
        for _ in range(4):
            s=f.state()
            target=next(e for e in s['enemies'] if e['uid']==0 and e['hp']>0)
            zone=target['area']
            if s['area']==zone:break
            f.warp(zone);time.sleep(1)
        else:raise RuntimeError('Target kept changing area while positioning the encounter')
        target_id=target['actor']
        f.fixture_bytes(a+0x13d6,100,'<h')
        for e in s['enemies']:
            if e['area']==zone:
                # Remove non-target actors in this copied-save collision fixture:
                # their attacks otherwise add unrelated 1-HP changes to the trace.
                f.fixture_bytes(e['actor']+0x17b0,2000 if e['actor']==target_id else 0)
                if e['actor']==target_id:f.fixture_bytes(e['actor']+0x17b4,2000)
        # Surveyed interior stations keep the prelude away from zone edges.
        # In zone2 the old z-800 prelude is below a cliff; z+700 is ground.
        station={2:(-1500.,0.,-1000.),5:(-1000.,-30.,1600.),6:(-2000.,-22.5,-3400.),7:(0.,0.,0.)}.get(zone,target['position'])
        f.command('emact 2 5 1')
        for owner in(target_id,f.read(target_id+0x1428)):
            for off,value in zip((0x40,0x44,0x48),station):f.fixture_bytes(owner+off,value,'<f')
        time.sleep(.2);x,y,z=station
        for off,v in [(0x40,x),(0x44,y),(0x48,z+700)]:f.fixture_bytes(a+off,v,'<f')
        for _ in range(90):
            f.command('emact 2 5 1');s=f.state()
            if s['state']==1 and (s['action']<=5 or s['action']==24):break
            if s['state']==64 and s['frame']>60:f.command('B 8')
            time.sleep(.25)
        assert s['state']==1 and (s['action']<=5 or s['action']==24),('not ready',s)
        if not f.read(a+0x2749,'<B')&1:
            f.command('X 8')
            for _ in range(7):time.sleep(.3);f.command('emact 2 5 1')
        # The neutral state can be visible while the preceding action is still
        # handing off its motion/input consumption. Wait for drawn idle itself.
        deadline=time.monotonic()+8
        while time.monotonic()<deadline:
            f.command('emact 2 5 1');s=f.state()
            if s['state']==1 and s['action']<=5 and s['motion']==0x501:
                time.sleep(.35);break
            time.sleep(.025)
        if s['motion']!=0x501 and s['state']==1 and s['action']<=5:
            # A preceding mobile-target run can finish in the native startled
            # idle while its draw flag is still handing off. Retry with pad input.
            f.command('X 8');deadline=time.monotonic()+8
            while time.monotonic()<deadline:
                f.command('emact 2 5 1');s=f.state()
                if s['state']==1 and s['action']<=5 and s['motion']==0x501:break
                time.sleep(.025)
        assert s['motion']==0x501,('drawn idle missing',s)
        f.fixture_bytes(a+0x3330,args.rank);f.fixture_bytes(a+0x332c,6000.0,'<f');f.fixture_bytes(a+0x2780,100)
        def thrust_motion(state):
            return state['state']==16 and (state['action'],state['motion']) in ((4,0x569),(250,0x590))
        f.command('A 8')
        deadline=time.monotonic()+4
        while time.monotonic()<deadline:
            s=f.state()
            if thrust_motion(s):break
            f.command('emact 2 5 1');time.sleep(.05)
        assert thrust_motion(s),('Opening thrust missing',s)
        while s['frame']<23 and thrust_motion(s):
            time.sleep(.006);s=f.state()
        f.command('R 24\nX 24')
        end=time.monotonic()+14;placed=False;seen=set();next_idle=0;shells=set();shell_rows=[];follow_sent=False;released=False
        log_start=(f.run/'log.txt').stat().st_size
        log_cursor=log_start;log_chunks=[];log_tail='';primary=[];fall_reset=None
        while time.monotonic()<end:
            s=f.state();s['hitstop']=f.read(a+0x27ac,'<2f');rows.append({'time':time.monotonic(),**s})
            if args.fall_reset_frame is not None and fall_reset is None and s['action']==244 and s['motion']==0x5e4 and s['frame']>=args.fall_reset_frame:
                assert s['position'][1]>s['floor']+50,('Fault injection needs real airborne dive',s)
                fall_reset=dict(time=time.monotonic(),before=s)
                f.fixture_values([(a+0x1014,0.,'<f'),(a+0x1024,0.,'<f')])
            if args.auto_down and s['action'] in (242,243,244):
                pad=f.read(0x2326888);index=f.read(pad+0x6b60,'<i')
                assert 0<=index<=8
                rows[-1]['raw_attack_buttons']=f.read(pad+index*0xb50+0x1d0)&0x3200
            with (f.run/'log.txt').open('rb') as log:
                log.seek(log_cursor);piece=log.read().decode('utf8',errors='replace');log_cursor=log.tell()
            # Dense native audio tracing can add megabytes per second. Do
            # not reread/reparse the entire attack trace on every sample:
            # that stalls observation across the short air-turn window.
            log_chunks.append(piece);scan,separator,log_tail=(log_tail+piece).rpartition('\n')
            if not separator:scan=''
            shells.update(int(v,16) for v in re.findall(r'world_burst \w+ \w+ \w+ (\w+)',scan))
            primary.extend(int(v,16) for v in re.findall(r'world_helm_primary \w+ (\w+)',scan))
            if args.primary_limit and primary and max(primary)>=args.primary_limit and s['action'] in (244,245):
                en=next(e for e in s['enemies'] if e['actor']==target_id)
                f.fixture_bytes(a+0x40,en['position'][0]+1600,'<f')
            for shell in shells:
                if f.read(shell)!=0x1960cb4:continue
                col=shell+0x13a8
                shell_rows.append({'time':time.monotonic(),'shell':shell,'position':f.read(shell+0x40,'<3f'),
                    'attack_id':f.read(col+0x34,'<H'),
                    'hit_effect':f.read(col+0x52,'<H'),
                    'age':f.read(shell+0x1378,'<f'),'area':f.read(shell+0x1054,'<B'),
                    'flags':f.read(col,'<8B'),'mv':f.read(col+0x38,'<H'),
                    'start':f.read(col+0x5c,'<f'),'duration':f.read(col+0x60,'<f'),
                    'shape':f.read(col+0x84,'<II'),'contact':f.read(col+0xac,'<III')})
                shell_rows[-1]['element_part_scale']=f.read(col+0x94,'<2f')
            if args.mobile_target and not released and s['action'] in (242,243,244):
                f.command('emact 2 14 1');released=True
            if time.monotonic()>next_idle and not released:
                f.command('emact 2 5 1');next_idle=time.monotonic()+.25
            if s['state']==16 and s['action']==241 and s['motion']==0x5e1 and 82<s['frame']<96:
                en=next(e for e in s['enemies'] if e['actor']==target_id);assert en['area']==s['area'],'target changed area'
                x,y,z=en['position']
                for off,v in [(0x40,x),(0x44,y),(0x48,z-200)]:f.fixture_bytes(a+off,v,'<f')
                f.fixture_bytes(a+0xfec,0);f.fixture_bytes(a+0x14a0,0);placed=True
            if s['state']==16 and s['action'] not in seen:
                seen.add(s['action']);print('phase',s['action'],s['motion'],s['frame'],s['position'],flush=True)
                if args.film_land and s['action']==245:
                    f.command(f'burst 70 helm_r{args.rank}_land')
                if s['action']==243:
                    if not args.auto_down:f.command('X 70')
                    if args.air_turn:f.command('STICK_LEFT 45')
            if args.landing_follow and not follow_sent and s['action']==245 and s['motion']==0x5e5:
                threshold=5 if args.landing_follow=='sheathe' else 60
                if s['frame']>=threshold:
                    f.command('R 2\n'+('B' if args.landing_follow=='sheathe' else 'A')+' 2')
                    follow_sent=True
            time.sleep(.015)
        text=''.join(log_chunks)
        result={'status':'OBSERVATION_ONLY','target':target_id,'phases':sorted(seen),'fixture_positioned':placed,'rows':rows,'shells':shell_rows,
                'landing_follow':args.landing_follow,'rank_fixture':args.rank,'follow_sent':follow_sent,'primary_limit_fixture':args.primary_limit,
                'primary_clock':[[int(v,16) for v in row] for row in re.findall(r'world_helm_clock \w+ (\w+) (\w+) (\w+)',text)],
                'fixture_non_target_enemies_removed':True,'auto_down_no_attack_input':args.auto_down,
                'mobile_target_fixture':args.mobile_target,'monster_released':released}
        result['helm_burst_events']=[[int(v,16)for v in row]for row in re.findall(r'world_burst \w+ (\w+) (\w+) (\w+)',text)
                                    if int(row[0],16) in (1000+args.rank,1020+args.rank)]
        result['duplicate_attempts_suppressed']=[[int(v,16)for v in row]for row in re.findall(r'world_helm_duplicate_suppressed \w+ (\w+) (\w+) (\w+)',text)]
        suffix=('_'+args.landing_follow if args.landing_follow else '')+('_rank'+str(args.rank) if args.rank!=3 else '')
        if args.primary_limit:suffix+='_primary'+str(args.primary_limit)
        if args.air_turn:suffix+='_airturn'
        if args.auto_down:suffix+='_auto'
        if args.mobile_target:suffix+='_mobile'
        result['log_start']=log_start
        result['fall_reset_fixture']=fall_reset
        result['log_end']=(f.run/'log.txt').stat().st_size
        # Preserve the actual observation even if an acceptance assertion fails.
        (f.run/('encounter_probe'+suffix+'.json')).write_text(json.dumps(result,indent=2))
        if args.auto_down:
            air=[r for r in rows if r['action']==243 and r['motion']==0x5e3]
            assert air and all(r['raw_attack_buttons']==0 for r in air),'Attack key remained held in air'
            assert 244 in seen and 245 in seen,'Automatic down/landing chain did not complete'
        if args.air_turn:
            air=[r for r in rows if r['action']==243 and r['motion']==0x5e3]
            changing=[];late=[]
            for x,y in zip(air,air[1:]):
                df=y['frame']-x['frame'];dh=((y['heading']-x['heading']+32768)&65535)-32768
                # The frame value is the update's entry clock. Heading has
                # already integrated THIS update's simulation delta, while
                # frame differences contain the PREVIOUS delta. These differ
                # during uneven rendering; do not assume a constant step.
                if df>0 and 6<=x['frame'] and y['frame']<20 and dh and y['dt']>0:
                    changing.append(abs(dh)*360/65536/y['dt']*60)
                if df>0 and x['frame']>=22:late.append(dh)
            assert len(changing)>=4 and all(78<v<82 for v in changing),changing
            assert late and all(v==0 for v in late),late
            import hashlib
            turn={'status':'PASS_AIR_CONTINUOUS_TURN','degrees_per_second':changing,'late_heading_changes':late,
                'rate_denominator':'Current native simulation delta; animation frame is the entry clock.',
                'plugin_sha256':hashlib.sha256((f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro').read_bytes()).hexdigest(),
                'rows':air,'limits':'One real jump with pad stick; source angle consumer and30/60/120Hz core tests are separate evidence.'}
            (f.run/'air_turn_report.json').write_text(json.dumps(turn,indent=2))
        print('observed',sorted(seen),'monster HP',rows[0]['enemies'][0]['hp'],rows[-1]['enemies'][0]['hp'])
    finally:f.close()

if __name__=='__main__':main()
