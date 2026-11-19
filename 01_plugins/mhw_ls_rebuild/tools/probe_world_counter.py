"""Counter timing sweep against a real native monster attack, in a copied save."""
import argparse,hashlib,json,re,time
from pc_fixture import Fixture

def main():
    ap=argparse.ArgumentParser();ap.add_argument('move',choices=['small','big','foresight'])
    ap.add_argument('--delay',type=float,default=.3);ap.add_argument('--attack',type=int,default=0)
    ap.add_argument('--group',type=int,default=7)
    ap.add_argument('--contact-fixture',action='store_true')
    ap.add_argument('--at-frame',type=float)
    ap.add_argument('--round',action='store_true');ap.add_argument('--sheathe-after-round',action='store_true')
    ap.add_argument('--rank-matrix',action='store_true',help='Keep rank-specific evidence and test the post-counter follow-up')
    ap.add_argument('--encounter-whiff',action='store_true',help='Use the same monster attack, offset the hunter horizontally for a negative control')
    ap.add_argument('--clear-line-view',action='store_true',help='Visual fixture: move the monster aside after the real detector contact to clear the ribbon from view obstruction')
    ap.add_argument('--film-lines',action='store_true',help='Save consecutive presented frames for a big Iai rank-matrix trial')
    ap.add_argument('--rank',type=int,default=3,choices=range(4))
    ap.add_argument('--counter-drop',type=float,help='Once after real Foresight contact, place the hunter this far above the local floor')
    ap.add_argument('--gauge',type=int,default=100,choices=range(101))
    ap.add_argument('--stun-start',type=int,choices=range(50))
    ap.add_argument('--armor-follow-hit',action='store_true',help='Restart the real enemy attack after small Iai active frames, inside its2s counter armor')
    ap.add_argument('--armor-follow-attack',type=int,help='Use a different unmodified enemy attack for armor/negative-control contacts; do not seek its windup')
    ap.add_argument('--attack-row',type=int,help='Copied-save fixture: select an existing native difficulty attack row, preserving its native multiplier')
    args=ap.parse_args()
    if args.encounter_whiff and not (args.move=='big' and args.rank_matrix and args.contact_fixture):
        ap.error('--encounter-whiff requires a big Iai rank-matrix contact fixture')
    if args.clear_line_view and not (args.move=='big' and args.rank_matrix and args.contact_fixture and not args.encounter_whiff):
        ap.error('--clear-line-view requires a big Iai rank-matrix counter fixture')
    if args.film_lines and not (args.move=='big' and args.rank_matrix):
        ap.error('--film-lines requires a big Iai rank-matrix fixture')
    if args.counter_drop is not None and not (args.move=='foresight' and args.contact_fixture and 0<args.counter_drop<=100):
        ap.error('Drop control requires a Foresight contact fixture and a height in (0,100]')
    side=600. if args.encounter_whiff else 0.
    f=Fixture();a=f.actor;rows=[]
    attack_fixture=None
    def wait(test,timeout=9,idle=True):
        end=time.monotonic()+timeout;wake=0
        while time.monotonic()<end:
            s=f.state()
            if test(s):return s
            if idle:f.command('emact 2 5 1')
            if s['state']==64 and s['frame']>60 and time.monotonic()>wake:
                f.command('B 8');wake=time.monotonic()+.6
            time.sleep(.02)
        raise TimeoutError(s)
    try:
        s=f.state();enemy=next(e for e in s['enemies'] if e['uid']==0)
        if s['area']!=enemy['area']:f.warp(enemy['area']);time.sleep(3)
        # A previous counter can leave the hunter beside small monsters. Move
        # the setup away from the target before drawing, and remove only the
        # unrelated fixture enemies. Otherwise their hits can interrupt the
        # draw and make the next test time out before its measured action.
        s=f.state();enemy=next(e for e in s['enemies'] if e['uid']==0)
        if args.contact_fixture:
            # Settle the target inside this zone BEFORE drawing. A roaming
            # target near an exit can send the hunter across the boundary
            # during the initial draw, consuming that input in the loader.
            early_station={2:(-1500.,0.,-1000.),5:(-1000.,-30.,1600.),6:(-2000.,-22.5,-3400.),7:(0.,0.,0.)}.get(s['area'])
            if early_station and enemy['area']==s['area']:
                f.command('emact 2 5 1')
                for owner in (enemy['actor'],f.read(enemy['actor']+0x1428)):
                    for off,v in zip((0x40,0x44,0x48),early_station):f.fixture_bytes(owner+off,v,'<f')
                time.sleep(.2);s=f.state();enemy=next(e for e in s['enemies']if e['uid']==0)
            for other in s['enemies']:
                if other['actor']!=enemy['actor'] and other['area']==s['area']:
                    f.fixture_bytes(other['actor']+0x17b0,0)
        for off,v in zip((0x40,0x44,0x48),(enemy['position'][0],enemy['position'][1],enemy['position'][2]+700)):
            f.fixture_bytes(a+off,v,'<f')
        wait(lambda s:s['state']==1 and s['action']<=5)
        f.fixture_bytes(a+0x13d6,100,'<h')
        if not f.read(a+0x2749,'<B')&1:
            f.command('X 8');time.sleep(2);wait(lambda s:s['state']==1 and s['action']<=5 and f.read(a+0x2749,'<B')&1)
        f.fixture_bytes(a+0x3330,args.rank);f.fixture_bytes(a+0x332c,6000.,'<f');f.fixture_bytes(a+0x2780,args.gauge)
        if args.stun_start is not None:
            f.fixture_bytes(a+0x2898,args.stun_start)
            f.fixture_bytes(a+0x289c,6000.,'<f')
        # A normal monster may change zones during draw/ready. Reacquire the
        # actual zone before station setup rather than test against stale data.
        for _ in range(3):
            s=f.state();enemy=next(e for e in s['enemies'] if e['uid']==0)
            if s['area']==enemy['area']:break
            f.warp(enemy['area']);wait(lambda s:s['state']==1 and s['action']<=5)
        assert s['area']==enemy['area'],'Target did not remain in the fixture zone'
        en=enemy['actor'];station=None
        if args.attack_row is not None:
            data=f.read(en+0x1428);tbl=f.read(f.read(0x1a51fe0)+0x257c)
            count=f.read(tbl+0x68);base=f.read(tbl+0x64)
            assert 0<=args.attack_row<count<=256
            multiplier=f.read(base+32*args.attack_row+4,'<f')
            assert .1<=multiplier<=30
            attack_fixture={'data':data,'row_before':f.read(data+0x39d,'<B'),
                'scale_before':f.read(data+0x384,'<f'),'row':args.attack_row,
                'row_multiplier':multiplier,'native_modifier':f.read(data+0x390,'<f'),
                'source':'Native 2baaac selects info+39d; 2c0528 caches row[1] * info+390 into info+384. No collision or pending damage is edited.'}
            f.fixture_bytes(data+0x39d,args.attack_row,'<B')
            f.fixture_bytes(data+0x384,multiplier*attack_fixture['native_modifier'],'<f')
        if args.contact_fixture:
            # Interior stations on this fixture's map. Verify the native zone
            # and settled target before using one for a collision observation.
            # Following a freely roaming target near an exit can trigger a
            # real area transition before the Iai input is consumed.
            station={2:(-1500.,0.,-1000.),5:(-1000.,-30.,1600.),6:(-2000.,-22.5,-3400.),7:(0.,0.,0.)}.get(s['area'])
            # In other zones retain the target's native station, then require
            # both actors to remain in that zone throughout the contact test.
            if station is None:station=enemy['position']
            f.command('emact 2 5 1')
            data=f.read(en+0x1428)
            for owner in (en,data):
                for off,v in zip((0x40,0x44,0x48),station):f.fixture_bytes(owner+off,v,'<f')
            f.fixture_bytes(en+0xfec,0);f.fixture_bytes(en+0x14a0,0)
            time.sleep(.2)
            s=f.state();enemy=next(e for e in s['enemies'] if e['actor']==en)
            assert enemy['area']==s['area'] and sum((u-v)**2 for u,v in zip(enemy['position'],station))<10000,('Station did not settle',enemy)
        if args.contact_fixture:
            for other in s['enemies']:
                if other['actor']!=en and other['area']==s['area']:
                    f.fixture_bytes(other['actor']+0x17b0,0)
        f.fixture_bytes(en+0x17b0,30000);f.fixture_bytes(en+0x17b4,30000)
        x,y,z=enemy['position'];assert s['area']==enemy['area']
        for off,v in zip((0x40,0x44,0x48),(x,y,z+700)):f.fixture_bytes(a+off,v,'<f')
        f.fixture_bytes(a+0xfec,32768);f.fixture_bytes(a+0x14a0,32768)
        time.sleep(.4);start=(f.run/'log.txt').stat().st_size
        if args.move=='foresight':
            f.fixture_bytes(en+0xfec,0);f.fixture_bytes(en+0x14a0,0)
            f.command(f'emact {args.group} {args.attack} 0');time.sleep(args.delay)
        f.command('A 12');retry=time.monotonic()+.6
        def thrust_ready(s):
            nonlocal retry
            if s['state']==16 and (s['action'],s['motion']) in ((4,0x569),(250,0x590)):return True
            if s['state']==1 and s['action']==0 and time.monotonic()>retry:
                f.command('A 6');retry=time.monotonic()+.6
            return False
        wait(thrust_ready,idle=args.move!='foresight');time.sleep(.3)
        if args.move=='foresight' and args.contact_fixture:
            # Let the preceding thrust's hit window close before moving near
            # the enemy. The counter shell must spawn at the measured station,
            # not700 units away followed by a teleport after binding.
            wait(lambda s:s['state']==16 and (s['action'],s['motion']) in ((4,0x569),(250,0x590)) and s['frame']>=27,idle=False)
            # This artificial station change must not carry the prelude GU
            # thrust's lingering collider into the enemy and flinch its attack.
            # Disable only that prelude collider in the recorded setup. The
            # World move opens its own new collider and all enemy hits remain real.
            f.fixture_bytes(a+0x3025,0,'<B')
            # The native update can re-enable an in-range old collider.
            # Expire its remaining lifetime too; the World move later binds
            # its own fresh HDP/ID and duration in the normal native path.
            f.fixture_bytes(a+0x3080,0.,'<f')
        if args.move!='foresight':
            wait(lambda s:s['action'] in (4,250) and s['frame']>=24,idle=False)
            f.command('R 18\nB 18');wait(lambda s:s['action']==246 and s['motion']==0x5e6 and s['frame']>=82,idle=False)
        s=f.state();enemy=next(e for e in s['enemies'] if e['uid']==0);x,y,z=enemy['position']
        # Do not move the preceding native thrust into the enemy; its hit can
        # flinch away the attack we are trying to counter before foresight starts.
        gap=(0 if args.contact_fixture else 700) if args.move=='foresight' else 140
        if args.move=='foresight' and args.contact_fixture:
            # The attack is already running here: enemy Y may be airborne.
            # Keep the hunter on its native floor, as contact_position does
            # below, rather than teleporting it into a ledge/fall transition.
            y=s['floor']
        for off,v in zip((0x40,0x44,0x48),(x+side,y,z+gap)):f.fixture_bytes(a+off,v,'<f')
        f.fixture_bytes(en+0xfec,0);f.fixture_bytes(en+0x14a0,0)
        f.fixture_bytes(a+0xfec,32768);f.fixture_bytes(a+0x14a0,32768)
        path_contact=False
        dropped=False
        path_cursor=start
        cleared=False
        def contact_position(s):
            nonlocal path_contact,path_cursor,dropped,cleared
            if not args.contact_fixture:return
            if args.move=='foresight' and s['action'] not in (240,30):return
            e=next(e for e in s['enemies'] if e['actor']==en)
            if args.clear_line_view and s['action']==248:
                if cleared:return
                with (f.run/'log.txt').open('rb') as stream:
                    stream.seek(path_cursor)
                    accepted=b'world_counter ' in stream.read()
                    path_cursor=stream.tell()
                if accepted:
                    x=e['position'][0]+1200
                    f.fixture_values([(en+0x40,x,'<f'),(f.read(en+0x1428)+0x40,x,'<f')])
                    cleared=True
                    return
            if args.counter_drop and s['action']==240 and s['motion']==0x5e0:
                if not path_contact:
                    with (f.run/'log.txt').open('rb') as stream:
                        stream.seek(path_cursor)
                        path_contact=b'world_counter ' in stream.read()
                        path_cursor=stream.tell()
                if path_contact and not dropped and s['frame']>=23:
                    dropped=True
                    f.fixture_bytes(a+0x44,s['floor']+args.counter_drop,'<f')
            # Follow horizontally only. Copying a jumping monster's Y puts
            # the hunter above the floor and invokes GU's real ledge/fall
            # transition before any collision, invalidating the counter test.
            # Leave height, floor and airborne flags to the native controller.
            for off,v in ((0x40,e['position'][0]+side),(0x48,e['position'][2])):
                f.fixture_bytes(a+off,v,'<f')
        if args.move!='foresight':
            f.command(f'emact {args.group} {args.attack} 0')
            wait(lambda s:any(e['actor']==en and e['action']&65535==args.group+(args.attack<<8) for e in s['enemies']),timeout=2,idle=False)
        delay_end=time.monotonic()+(0 if args.move=='foresight' else 5 if args.at_frame is not None else args.delay)
        while time.monotonic()<delay_end:
            s=f.state();contact_position(s)
            enemy=next(e for e in s['enemies'] if e['actor']==en)
            if args.at_frame is not None and enemy['action']&65535==args.group+(args.attack<<8) and enemy['frame']>=args.at_frame:break
            time.sleep(.01)
        key='X 10' if args.move=='small' else 'R 10' if args.move=='big' else 'R 24\nA 24'
        f.command(key);started=time.monotonic();end=started+8;round_sent=sheathe_sent=follow_hit_sent=follow_clock_set=False
        bound_at=None;unprotected_sent=unprotected_clock_set=False
        counter_flash_shot=False;fx_cursor=start
        line_shots={};line_particle=None;line_burst=None
        thrust_sent=False
        while time.monotonic()<end:
            s=f.state();rows.append({'time':time.monotonic(),**s,
                'stun':f.read(a+0x2898),'stun_timer':f.read(a+0x289c,'<f')})
            if time.monotonic()-started<(4 if args.armor_follow_hit else 1.5):contact_position(s)
            if s['action']==247 and s['motion']==0x5ee and bound_at is None:bound_at=time.monotonic()
            if args.armor_follow_hit and s['action']==247 and s['motion']==0x5ee and s['frame']>=38 and not follow_hit_sent:
                follow_attack=args.attack if args.armor_follow_attack is None else args.armor_follow_attack
                f.command(f'emact {args.group} {follow_attack} 0');follow_hit_sent=True
                if args.armor_follow_attack is not None:follow_clock_set=True
            if follow_hit_sent and not follow_clock_set:
                enemy=next(e for e in s['enemies'] if e['actor']==en)
                if enemy['action']&65535==args.group+(args.attack<<8) and enemy['frame']<10:
                    # Incoming-damage fixture: shorten only this real attack's
                    # windup so its native contact lands inside2s armor.
                    f.fixture_bytes(en+0x4fc,40.,'<f')
                    f.fixture_bytes(en+0x4bc,f.read(en+0x4bc)|0x10);follow_clock_set=True
            if args.armor_follow_hit and bound_at is not None and time.monotonic()-bound_at>=2.4 and not unprotected_sent:
                # Independent negative control after the source2s armor.
                # Seeking the second attack correctly now places it inside
                # armor; a third real attack establishes that KO resumes.
                follow_attack=args.attack if args.armor_follow_attack is None else args.armor_follow_attack
                f.command(f'emact {args.group} {follow_attack} 0');unprotected_sent=True
                if args.armor_follow_attack is not None:unprotected_clock_set=True
            if unprotected_sent and not unprotected_clock_set:
                enemy=next(e for e in s['enemies'] if e['actor']==en)
                if enemy['action']&65535==args.group+(args.attack<<8) and enemy['frame']<10:
                    f.fixture_bytes(en+0x4fc,40.,'<f')
                    f.fixture_bytes(en+0x4bc,f.read(en+0x4bc)|0x10);unprotected_clock_set=True
            if args.round and s['action']==240 and s['gauge']==100 and s['frame']>=85 and not round_sent:
                f.command('R 2');round_sent=True
            if args.rank_matrix and args.move=='big' and s['action']==248 and s['motion']==(0x5ef,0x5f0,0x5f1,0x5f5)[args.rank] and s['frame']>=70 and not thrust_sent:
                f.command('R 8\nX 8');thrust_sent=True
            if args.rank_matrix and args.move=='big' and s['action']==248 and s['motion']==(0x5ef,0x5f0,0x5f1,0x5f5)[args.rank]:
                first=10 if args.rank in (0,2) else 12
                if (args.clear_line_view or args.film_lines) and line_burst is None:
                    kind='clear' if args.clear_line_view else 'whiff' if args.encounter_whiff else 'counter'
                    line_burst=f'iai_{kind}_{args.rank}_{start}'
                    f.command(f'burst 125 {line_burst}')
                if args.clear_line_view and not line_particle and 55<=s['frame']<59:
                    with (f.run/'log.txt').open('rb') as stream:
                        stream.seek(start);match=re.search(rb'world_iai_counter_line \w+ (\w+)',stream.read())
                    if match:
                        controller=int(match[1],16);child=f.read(controller+336) if controller else 0
                        gen=f.read(child+496) if child else 0
                        particle=f.read(gen+36) if gen else 0
                        if particle:
                            resource=f.read(child+244)
                            line_particle=dict(frame=s['frame'],resource=bytes(f.read(resource+8,'<64B')).split(b'\0')[0].decode())
                shots=(('first',first+3),('second',67))
                if line_burst:shots=()
                for name,target in shots:
                    if name not in line_shots and target<=s['frame']<target+7:
                        outcome='clear' if args.clear_line_view else 'whiff' if args.encounter_whiff else 'counter'
                        shot=f"iai_{args.rank}_{outcome}_{name}"
                        f.command('shot '+shot)
                        line_shots[name]={'frame':s['frame'],'file':str(f.run/'shots'/(shot+'.png'))}
            if args.round and s['action']==30:contact_position(s)
            if args.sheathe_after_round and s['action']==30 and s['motion']==0x57f and s['frame']>=31 and not sheathe_sent:
                f.command('R 2\nB 2');sheathe_sent=True
            if args.move=='big' and not (args.clear_line_view or args.film_lines) and not counter_flash_shot:
                with (f.run/'log.txt').open('rb')as stream:
                    stream.seek(fx_cursor);piece=stream.read().decode(errors='replace');fx_cursor=stream.tell()
                if ('00003F66' in piece or '00003FC2' in piece) and 'world_simple_fx_emit' in piece:
                    f.command('shot big_counter_source_flash');counter_flash_shot=True
            time.sleep(.015)
        with (f.run/'log.txt').open('rb') as log:log.seek(start);events=log.read().decode('utf8',errors='replace')
        relevant=[line for line in events.splitlines() if any(k in line for k in ('world_counter','world_incoming','world_interrupt','world_detector_','world_super_hit','world_stun','world_hp_hit'))]
        result={'status':'OBSERVATION_ONLY','contact_fixture':args.contact_fixture,'move':args.move,'group':args.group,'attack':args.attack,'delay':args.delay,'events':relevant,'rows':rows}
        result['prelude_collider_disabled_fixture']=args.move=='foresight' and args.contact_fixture
        result['at_frame']=args.at_frame
        result['stun_start_fixture']=args.stun_start
        result['armor_follow_hit_fixture']=args.armor_follow_hit
        result['armor_follow_attack_fixture']=args.armor_follow_attack
        result['native_attack_difficulty_fixture']=attack_fixture
        result['follow_attack_clock40_fixture']=follow_clock_set
        result['unprotected_attack_clock40_fixture']=unprotected_clock_set
        result['initial_attack_clock_modified_fixture']=False
        result['non_target_enemies_removed_fixture']=args.contact_fixture
        result['contact_position_axes_fixture']='XZ only; native height/floor/air state' if args.contact_fixture else None
        if args.counter_drop:result['counter_drop_fixture']={'height':args.counter_drop,'applied':dropped}
        result['interior_station_fixture']=station
        result['enemy_heading_zero_fixture']=bool(args.contact_fixture)
        result['log_start']=start;result['counter_flash_screenshot_requested']=counter_flash_shot
        result['line_screenshots']=line_shots
        result['counter_line_particle']=line_particle
        result['line_burst']=line_burst
        result['monster_moved_after_counter_fixture']=cleared
        result['line_events']=[line for line in events.splitlines()
                               if 'world_iai_line ' in line or 'world_iai_counter_line ' in line]
        result.update(rank_fixture=args.rank,gauge_fixture=args.gauge,round_requested=args.round,sheathe_after_round=args.sheathe_after_round,
            plugin_sha256=hashlib.sha256((f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro').read_bytes()).hexdigest())
        name=f'counter_{args.move}_{args.group}_{args.attack}_{args.delay}'+(f'_frame{args.at_frame}' if args.at_frame is not None else '')
        if args.gauge!=100:name+=f'_gauge{args.gauge}'
        if args.armor_follow_hit:name+='_armor'
        if args.armor_follow_attack is not None:name+='_follow'+str(args.armor_follow_attack)
        if args.attack_row is not None:name+='_row'+str(args.attack_row)
        result['horizontal_control_offset']=side
        if args.rank_matrix:name=f'matrix_{args.move}_{args.rank}_'+('whiff' if args.encounter_whiff else 'counter')
        if args.clear_line_view:name+='_clear'
        (f.run/(name+'.json')).write_text(json.dumps(result,indent=2))
        print(name,'hp',rows[0]['hp'],rows[-1]['hp'],'phases',sorted(set(r['action'] for r in rows)),relevant)
        f.warp(0)
    finally:
        if attack_fixture:
            f.fixture_bytes(attack_fixture['data']+0x39d,attack_fixture['row_before'],'<B')
            f.fixture_bytes(attack_fixture['data']+0x384,attack_fixture['scale_before'],'<f')
        f.close()

if __name__=='__main__':main()
