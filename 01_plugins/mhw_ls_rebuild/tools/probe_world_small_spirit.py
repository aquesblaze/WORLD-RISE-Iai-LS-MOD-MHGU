"""Actual-input dedicated post-Iai chain in the guarded copied-save fixture.

Only station, rank and gauge are fixture setup. No action, motion, animation
clock, pose or collision is forced. Raw records remain under the private run.
This validates motion routing, not full World input/presentation parity.
"""
import argparse,json,time
from animation_port import PROJECT,sha
from pc_fixture import Fixture

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--insert',action='store_true')
    ap.add_argument('--input-vm',action='store_true');args=ap.parse_args()
    f=Fixture();rows=[];torn=0
    plan=json.loads((PROJECT/'research/world_ground_motion_plan.json').read_text(encoding='utf8'))
    slots={r['world_clip']:r['gu_slot']for r in plan['clips']}
    inverse={0x500+v:k for k,v in slots.items()}
    def sample():
        nonlocal torn
        before=f.read(f.actor+0x500,'<f');s=f.state()
        after=f.read(f.actor+0x500,'<f')
        if before==s['frame']==after:
            s['source']=inverse.get(s['motion'],0);s['time']=time.monotonic();rows.append(s)
        else:torn+=1
        return s
    def wait(test,seconds=12):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            s=sample()
            if test(s):return s
            time.sleep(.006)
        raise TimeoutError(s)
    def motion(source,frame=0):
        return wait(lambda s:s['motion']==0x500+slots[source] and s['frame']>=frame)
    result={'status':'FAIL','case':'insertions'if args.insert else 'direct_R_chain','run':str(f.run)}
    try:
        f.command('STICK_CENTER 1200');f.camp_station()
        if not f.read(f.actor+0x2749,'<B')&1:
            f.command('X 8');time.sleep(3)
            wait(lambda s:s['state']==1 and f.read(f.actor+0x2749,'<B')&1)
        f.fixture_values([(f.actor+0x332c,6000.,'<f'),(f.actor+0x3330,3,'<I'),
                          (f.actor+0x3334,0.,'<f'),(f.actor+0x2780,100,'<I')])
        time.sleep(.2);f.command('A 8')
        wait(lambda s:(s['action']==4 or s['action']==250 and s['motion']==0x500+slots[105])and s['frame']>=45)
        f.command('R 20\nB 20');motion(306,85)
        f.command('X 8');motion(307,30);f.command('R 8');motion(363);motion(104,44)
        if args.insert:
            f.command('A 8');motion(118);motion(112,28)
        f.command('R 8')
        if args.insert:motion(121)
        motion(106,26)
        if args.insert:
            f.command('A 8');motion(107,24)
        f.command('R 8')
        if args.insert:motion(124)
        motion(108,90);f.command('R 8');motion(109,30)
        wait(lambda s:s['state']==1)
        groups=[]
        start=next(i for i,s in enumerate(rows)if s['action']==247 and s['source']==307)
        for s in rows[start:]:
            if s['action']not in(247,250):continue
            # An action request precedes its first motion bind. Do not label
            # the outgoing special-sheathe clock as a small-Iai phase.
            if s['action']==247 and s['source']!=307:continue
            if s['action']==250 and s['source']in(0,306,307):continue
            if not groups or groups[-1]['source']!=s['source']:
                groups.append({'source':s['source'],'first_frame':s['frame'],'last_frame':s['frame'],'samples':1})
            else:groups[-1]['last_frame']=s['frame'];groups[-1]['samples']+=1
        expected=[307,363,104]+([118,112,121]if args.insert else[])+[106]+([107,124]if args.insert else[])+[108,109]
        if [g['source']for g in groups]!=expected:raise ValueError(('Unexpected actual chain',groups,expected))
        first104=next(g for g in groups if g['source']==104)['first_frame']
        if not 42<=first104<=44.1:raise ValueError(('MBD42 entry missing',first104))
        result.update(status='PASS_MOTION_ROUTING_ONLY',phases=groups)
    except Exception as exc:
        result['error']=repr(exc)
    finally:
        result.update(rows=rows,discarded_cross_frame_reads=torn,
            plugin_sha256=sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
            input_vm=args.input_vm,
            limits=('Source input VM connected; full timing validation, FX/audio pending.'if args.input_vm else
                'Legacy input pipeline; full input VM integration, FX/audio pending.')+' This report is not user acceptance.')
        path=f.run/f'small_spirit_{result["case"]}_{time.time_ns()}.json'
        path.write_text(json.dumps(result,indent=2));print(path)
        print(json.dumps({k:v for k,v in result.items()if k!='rows'}));f.close()
    return 0 if result['status'].startswith('PASS')else 1

if __name__=='__main__':raise SystemExit(main())
