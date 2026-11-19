"""Isolated PC acceptance for Guild landings, ledges, Spirit insert and uphill attacks."""
import json,time
from pc_fixture import Fixture
from probe_guild_ownership import draw,wait

def check(f):
    a=f.actor
    def inputs(keys):
        f.command('\n'.join(k+' 8' for k in keys))
    def motion(n,frame=0):
        return wait(f,lambda s:s['motion']==n and s['frame']>=frame,5)
    def setup():
        f.camp_station();draw(f);f.fixture_bytes(a+0x2780,100)
    def stationary():
        wait(f,lambda s:s['state']==1,7)
    results={}
    def save():
        (f.run/'guild_demo_acceptance.json').write_text(json.dumps(results,indent=2));print(results,flush=True)
    setup();inputs('R');motion(0x568,42);inputs('A');motion(0x569,30);inputs('X')
    chain=[motion(0x56b,30)['action']];inputs('A');chain.append(motion(0x569,24)['action']);inputs('X')
    chain.append(motion(0x56b)['action']);assert chain==[25,4,25];results['spirit_AX']=chain;save()
    stationary()
    for action,slot,frame in [(32,0x565,72),(33,0x565,72),(34,0x565,72),(42,0x568,48),(43,0x568,48)]:
        setup();f.command(f'plact 10 {action}');r=motion(slot,frame);inputs('RA')
        m=motion(0x5e0);results['landing_'+str(action)]=[r['action'],r['frame'],m['action']];save();stationary()
    # The measured camp incline rises to the east past x=400.
    for key,slot in [('X',0x565),('R',0x568)]:
        setup();f.fixture_values([(a+0x40,500.,'<f'),(a+0x44,-190.,'<f')]);time.sleep(.15)
        start=f.state();inputs(key);r=motion(slot,58);inputs('RA');m=motion(0x5e0)
        results['slope_'+key]=[r['action'],m['action'],r['floor']-start['floor']];save();stationary()
    for height in (40,113,160):
        setup();inputs('A');motion(0x569,28);inputs('RA');s=motion(0x5e0,20);off=(f.run/'log.txt').stat().st_size
        f.fixture_bytes(a+0x44,s['floor']+height,'<f')
        after=wait(f,lambda s:s['state']==4 or (s['motion']==0x5e0 and s['frame']>34));log=(f.run/'log.txt').read_bytes()[off:]
        assert (b'world_step_down' in log)==(height<=120),(height,after,log[-1200:])
        assert ((after['state'],after['action'])==(16,240) if height<=120 else (after['state'],after['action'])==(4,1)),(height,after)
        results['drop_'+str(height)]=[after['state'],after['action'],after['position'][1]-after['floor']];save();stationary()
    return results
if __name__=='__main__':
    f=Fixture()
    try:check(f)
    finally:f.close()
