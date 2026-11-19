"""Actual-input checks for World's source command VM in a copied GU fixture.

Read the actual raw/pending command log and transition clocks. Timing misses
remain failures; this tool never forces an action, pose, clock or collision.
"""
import argparse,json,re,time
from animation_port import PROJECT,sha
from pc_fixture import Fixture

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--case',choices=('r_buffer','too_early','chord','upper_R','loop'),required=True)
    args=ap.parse_args();f=Fixture();rows=[]
    plan=json.loads((PROJECT/'research/world_ground_motion_plan.json').read_text(encoding='utf8'))
    slots={r['world_clip']:r['gu_slot']for r in plan['clips']};inverse={0x500+v:k for k,v in slots.items()}
    offset=(f.run/'log.txt').stat().st_size
    def sample():
        s=f.state();s['time']=time.monotonic();s['source']=inverse.get(s['motion'],0);rows.append(s);return s
    def wait(test,seconds=12):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            s=sample()
            if test(s):return s
            time.sleep(.006)
        raise TimeoutError(s)
    def motion(source,frame=0):return wait(lambda s:s['motion']==0x500+slots[source]and s['frame']>=frame)
    report={'status':'FAIL','case':args.case,'run':str(f.run),'setup':'Copied-save station, rank/gauge only; no action/clock writes.'}
    try:
        f.command('STICK_CENTER 1200');f.camp_station()
        if not f.read(f.actor+0x2749,'<B')&1:f.command('X 8');time.sleep(3)
        wait(lambda s:s['state']==1)
        f.fixture_values([(f.actor+0x332c,6000.,'<f'),(f.actor+0x3330,3,'<I'),
            (f.actor+0x3334,0.,'<f'),(f.actor+0x2780,100,'<I')]);time.sleep(.2)
        f.command('A 8');motion(105,14 if args.case=='too_early' else 22)
        expected=38;origin=105;destination=104
        if args.case=='chord':
            # Keep R physically held through A's native70ms maturation.
            # R8 can release on that same frame after host polling latency;
            # that is a different native gesture, not a chord-priority check.
            f.command('R 12');motion(105,24);f.command('A 8');destination=140;motion(140)
        elif args.case in('upper_R','loop'):
            f.command('X 6');motion(119);motion(107,25);origin=107;expected=42
            if args.case=='loop':
                destination=105;f.command('A 6');motion(105)
            else:
                destination=126;f.command('R 4');motion(126);motion(104,28)
        else:
            f.command('R 4')
            if args.case=='too_early':wait(lambda s:s['state']==1)
            else:motion(104)
        time.sleep(.15)
        text=(f.run/'log.txt').read_bytes()[offset:].decode('utf8',errors='replace')
        commands=[];transitions=[]
        for line in text.splitlines():
            m=re.search(r'ML_REBUILD: world_input_command ([0-9A-F]{8}) ([0-9A-F]{8}) ([0-9A-F]{8}) ([0-9A-F]{8})',line)
            if m:
                actor,x,y,z=[int(v,16)for v in m.groups()]
                commands.append({'actor':actor,'id':x&255,'source':x>>8,'flags':y&31,
                    'held':(y>>8)&255,'permission':(y>>16)&3,'frame':z/1000})
            m=re.search(r'ML_REBUILD: world_source_transition ([0-9A-F]{8}) ([0-9A-F]{8}) ([0-9A-F]{8}) ([0-9A-F]{8})',line)
            if m:
                actor,old,new,frame=[int(v,16)for v in m.groups()]
                transitions.append({'actor':actor,'old':old,'new':new,'frame':frame/1000})
        if not commands:raise ValueError('No actual command VM telemetry; wrong candidate or log scope')
        if args.case=='too_early':
            raw=[v for v in commands if v['source']==105 and v['id']==39 and v['flags']&1]
            if len(raw)!=1 or not raw[0]['frame']<18 or raw[0]['permission']!=0:
                raise ValueError(('Early-input fixture did not precede source buffer18',raw))
            if any(v['new']==104 for v in transitions):raise ValueError('Too-early R was incorrectly buffered')
        else:
            matches=[v for v in transitions if(v['old'],v['new'])==(origin,destination)]
            if len(matches)!=1:raise ValueError(('Missing unique source transition',origin,destination,transitions))
            observed=matches[0]['frame'];maximum_delta=max(s['dt']for s in rows if s['motion']==0x500+slots[origin])
            if not expected<=observed<=expected+maximum_delta+.025:
                raise ValueError(('Extra command delay or early transition',expected,observed,maximum_delta))
            if args.case=='chord'and any(v['new']==104 for v in transitions):raise ValueError('Solo Spirit-I preempted R+A')
            if args.case in('r_buffer','upper_R'):
                raw=[v for v in commands if v['source']==origin and v['id']==39 and v['flags']&1]
                if not raw or not any(v['permission']&1 and v['flags']&4 for v in raw):
                    raise ValueError(('No actual source-window R buffer',raw))
        report.update(status='PASS_SCOPED_RUNTIME_INPUT',commands=commands,transitions=transitions)
    except Exception as exc:report['error']=repr(exc)
    finally:
        # Preserve the actual command stream even when a motion wait fails.
        report['log_excerpt']=(f.run/'log.txt').read_bytes()[offset:].decode('utf8',errors='replace')
        report.update(rows=rows,plugin_sha256=sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
            limits='Source command and routing checks only; full weapon FSM, turn binding, FX/audio and user-entry acceptance remain pending.')
        path=f.run/f'command_vm_{args.case}_{time.time_ns()}.json';path.write_text(json.dumps(report,indent=2))
        print(path);print(json.dumps({k:v for k,v in report.items()if k not in('rows','commands','log_excerpt')}));f.close()
    return 0 if report['status'].startswith('PASS')else 1

if __name__=='__main__':raise SystemExit(main())
