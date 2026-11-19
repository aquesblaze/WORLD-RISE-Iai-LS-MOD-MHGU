"""Record an actual-input GU big-Iai trajectory; no action/clock writes.

The existing guarded copied-save fixture sets only the surveyed camp station
and gauge/rank. This is diagnostic evidence, not an animation acceptance test.
"""
import json
import time
import argparse
from pc_fixture import Fixture
from animation_port import sha

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rank',type=int,choices=range(4),default=0);args=ap.parse_args()
    f=Fixture();rows=[];torn=0
    def wait(test,seconds=15):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            state=f.state()
            if test(state):return state
            time.sleep(.008)
        raise TimeoutError(state)
    try:
        f.command('STICK_CENTER 1200');f.camp_station()
        if not f.read(f.actor+0x2749,'<B')&1:
            f.command('X 8');time.sleep(3)
        wait(lambda s:s['state']==1)
        f.fixture_values([(f.actor+0x332c,6000.,'<f'),(f.actor+0x3330,args.rank,'<I'),
                          (f.actor+0x3334,0.,'<f'),(f.actor+0x2780,100,'<I')]);time.sleep(.2)
        f.command('A 8');wait(lambda s:s['action']==4 and s['frame']>=45)
        f.command('R 20\nB 20');wait(lambda s:s['action']==246 and s['frame']>=85)
        slot=(239,240,241,245)[args.rank]
        f.command('R 8');wait(lambda s:s['action']==248 and s['motion']==0x500+slot)
        end=time.monotonic()+7
        while time.monotonic()<end:
            before=f.read(f.actor+0x500,'<f')
            state=f.state();state['time']=time.monotonic()
            records=f.read(f.actor+0x494);mapping=f.read(f.actor+0x498)
            state['bones']={str(function):f.read(records+160*f.read(mapping+function,'<B')+16,'<16f')
                            for function in (0,1,8,12)}
            after=f.read(f.actor+0x500,'<f')
            if before!=state['frame'] or after!=state['frame']:
                torn+=1;continue
            rows.append(state)
            if state['action']!=248 and len(rows)>2:break
            time.sleep(.008)
        if not any(s['action']==248 and s['frame']>170 for s in rows):raise ValueError('Incomplete source-308 playback')
        report={'status':'DIAGNOSTIC_BASELINE_ONLY','run':str(f.run),
            'source_clip':308+args.rank,'source_rank':args.rank,
            'discarded_cross_frame_reads':torn,'sampling_guard':'Same native motion clock before and after state and bone reads',
            'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
            'rows':rows,'limits':'Copied-save station and gauge/rank setup; no pose, action or clock forcing.'}
        path=f.run/f'iai_trajectory_{time.time_ns()}.json';path.write_text(json.dumps(report,indent=2))
        active=[s for s in rows if s['action']==248]
        print(path);print(json.dumps([{k:s[k]for k in ('frame','position','heading')}for s in active[::max(1,len(active)//12)]]))
    finally:f.close()

if __name__=='__main__':main()
