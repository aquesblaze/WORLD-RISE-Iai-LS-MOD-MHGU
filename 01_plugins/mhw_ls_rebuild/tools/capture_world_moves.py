"""Visual samples from actual pad actions; not timing acceptance evidence."""
import json,time
from pc_fixture import Fixture

def main():
    f=Fixture();shots=[]
    def wait(pred,seconds=12):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            s=f.state()
            if pred(s):return s
            time.sleep(.01)
        raise TimeoutError(s)
    def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
    def cmd(keys,n=8):f.command('\n'.join(f'{k} {n}' for k in keys))
    def snap(name):
        before=f.state();f.command('shot '+name);time.sleep(.5)
        shots.append({'name':name,'before':before,'after':f.state()})
    try:
        if f.state()['area']!=0:f.warp(0)
        origin=f.state()['position']
        for name,keys,motion,at in [('foresight',['R','A'],0x5e0,60),
                                  ('spirit_thrust',['R','X'],0x5e1,86),
                                  ('sheathe',['R','B'],0x5e6,85),
                                  ('small',['X'],0x5ee,25),('big',['R'],0x5ef,25)]:
            idle();time.sleep(.35)
            for off,v in zip((0x40,0x44,0x48),origin):f.fixture_bytes(f.actor+off,v,'<f')
            if not f.read(f.actor+0x2749,'<B')&1:
                cmd(['X']);time.sleep(2);idle()
            f.fixture_bytes(f.actor+0x3330,0)
            cmd(['A']);wait(lambda s:s['state']==16 and s['action']==4 and s['motion']==0x569 and s['frame']>=18)
            if name in ('small','big'):
                cmd(['R','B'],24);wait(lambda s:s['action']==246 and s['motion']==0x5e6 and s['frame']>=82)
            cmd(keys,24 if name not in ('small','big') else 8)
            wait(lambda s:s['motion']==motion and s['frame']>=at)
            snap('visual_'+name)
        (f.run/'visual_samples.json').write_text(json.dumps(shots,indent=2))
        print(f.run/'shots')
    finally:f.close()

if __name__=='__main__':main()
