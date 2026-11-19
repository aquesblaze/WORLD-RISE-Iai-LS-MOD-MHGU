"""Copied-save drop fixture; native R attack and R+B landing follow-up."""
import json,time
from pc_fixture import Fixture
from probe_guild_ownership import draw,wait


def main():
    f=Fixture();rows=[]
    try:
        for timing,rank,gauge in (('air',3,100),('landing',0,100),('landing',1,100),
                                  ('landing',2,100),('landing',3,100),('landing',0,0),('landing',3,0)):
            f.camp_station();draw(f)
            f.fixture_values([(f.actor+0x2780,gauge,'<I'),(f.actor+0x3330,rank,'<I'),
                              (f.actor+0x332c,6000.,'<f'),
                              (f.actor+0x44,f.state()['floor']+1000,'<f'),
                              (f.actor+0x1014,-1.,'<f')])
            wait(f,lambda s:s['state']==4 and s['motion']==0x533,3)
            f.command('R 12');sent=False;air=False;sheath=False;end=time.monotonic()+8
            while time.monotonic()<end:
                s=f.state();rows.append(dict(case=timing,rank_fixture=rank,gauge_fixture=gauge,**s))
                if 72<=s['action']<=75 and s['motion'] in (0x599,0x59b):
                    air=True
                    if timing=='air' and not sent and s['position'][1]-s['floor']<100:
                        f.command('R 4\nB 4');sent=True
                if timing=='landing' and not sent and 72<=s['action']<=75 and s['motion'] in (0x59a,0x59c) and s['frame']>=10:
                    f.command('R 4\nB 4');sent=True
                if s['action']==246 and s['motion']==0x5e6:
                    assert s['position'][1]<=s['floor']+1,s
                    sheath=True;break
                time.sleep(.006)
            assert air and sent and sheath,(timing,air,sent,sheath,s)
            print('PASS aerial spirit -> special sheath:',timing,rank,gauge,flush=True)
            wait(f,lambda s:s['state']==1 and s['action']<=5,15)
        status='PASS_AIR_SPIRIT_SHEATHE'
    finally:
        (f.run/'air_spirit_sheathe.json').write_text(json.dumps(dict(status=locals().get('status','FAIL'),
            fixture='Copied-save elevated drop; no action/motion/clock writes',rows=rows),indent=2))
        f.close()


if __name__=='__main__':main()
