"""Read-only native motion-clock/trajectory trace for World ground playtests.

Uses the owner-validated camera locator. 2236170 -> 2246d70 resolves layer0
to player[468]+b0. 1c015db/1c015e7 reads motion ID at+a and clock at+5c.
No synthetic actions, pose changes, process writes or injected code.
"""
import argparse
import json
import time
from observe_world_camera import WorldCamera,ROOT,BASE

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pid',type=int,required=True)
    ap.add_argument('--seconds',type=float,default=12);ap.add_argument('--tag',default='ground')
    args=ap.parse_args();assert 0<args.seconds<=45
    assert args.tag.replace('_','').isalnum()
    camera=WorldCamera(args.pid);rows=[]
    try:
        end=time.monotonic()+args.seconds
        while time.monotonic()<end:
            a=camera.owner
            component=camera.read(a+0x468,'<Q')
            if camera.read(a+0x460,'<Q'):raise ValueError('Unexpected alternate motion component')
            motion=component+0xb0;weapon=camera.read(a+0x76b0,'<Q')
            rows.append({'time':time.monotonic(),'position':camera.read(a+0x160,'<3f'),
                'forward':camera.read(a+0x230,'<3f'),'motion':camera.read(motion+0xa,'<H')&511,
                'native_motion':camera.read(motion+0xa,'<H'),
                'frame':camera.read(motion+0x5c,'<f'),'last_frame':camera.read(motion+0x64,'<f'),
                'requested_motion':camera.read(a+0x55b8,'<I'),
                'rank':camera.read(weapon+0x2370,'<I'),
                'drawn':camera.read(a+0x76aa,'<B')})
            time.sleep(.008)
        path=ROOT/'.cache/mhw_game_input'/f'{args.tag}_{time.time_ns()}.json'
        path.write_text(json.dumps({'pid':args.pid,'owner':camera.owner,'read_only':True,
            'source_build':421810,'clock_evidence':['2236170','2246d70','1c015db','1c015e7'],
            'rows':rows},indent=2))
        runs=[]
        for r in rows:
            if not runs or runs[-1]['motion']!=r['motion']:
                runs.append({'motion':r['motion'],'start_frame':r['frame'],'end_frame':r['frame'],
                    'start':r['position'],'end':r['position'],'samples':1})
            else:runs[-1].update(end_frame=r['frame'],end=r['position'],samples=runs[-1]['samples']+1)
        print(path);print(json.dumps(runs))
    finally:camera.close()

if __name__=='__main__':main()
