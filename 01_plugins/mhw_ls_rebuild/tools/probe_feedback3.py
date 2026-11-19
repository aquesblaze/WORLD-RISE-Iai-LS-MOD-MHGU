"""Pad-driven acceptance of early/released R, native resource branches and Iai travel."""
import json,time
from pc_fixture import Fixture
from animation_port import sha

def main():
    f=Fixture();a=f.actor;cases=[];samples=[]
    report={'status':'FAIL','plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),'cases':cases}
    def state():
        s=f.state();s.pop('enemies');samples.append(s);return s
    def wait(test,timeout=12):
        end=time.monotonic()+timeout
        while time.monotonic()<end:
            s=state()
            if test(s):return s
            time.sleep(.004)
        raise TimeoutError(s)
    def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
    def setup(gauge=100,rank=0):
        idle();f.camp_station()
        if not f.read(a+0x2749,'<B')&1:f.command('X 8');time.sleep(2);idle()
        f.fixture_values([(a+0x2780,gauge,'<I'),(a+0x332c,6000.,'<f'),(a+0x3330,rank,'<I'),(a+0x3334,0.,'<f')]);time.sleep(.1)
        samples.clear()
    def save(name,**extra):
        cases.append({'name':name,**extra,'samples':samples.copy()});print('PASS',name,flush=True)
    def second():
        # Reach II through the source-compatible I -> stab -> II route.
        # Stock GU R->R permission times are outside this insertion test.
        wait(lambda s:s['state']==16 and s['motion']==0x568 and s['frame']>=38);f.command('A 24')
        wait(lambda s:s['action']==22 and s['motion']==0x569 and s['frame']>=32);f.command('R 2')
        wait(lambda s:s['action']==24 and s['motion']==0x56a and s['frame']>=30)
    try:
        for key,at,gauge in [('A',5,100),('A',20,100),('X',5,100),('X',55,100),('A',5,0),('X',5,0),('A',20,10)]:
            setup(gauge);f.command(key+' 2');pressed=wait(lambda s:s['state']==16 and s['frame']>=at)
            f.command('R 2');target=16 if gauge>=15 else 17
            entered=wait(lambda s:s['state']==16 and s['action']==target and s['motion']==0x568)
            assert entered['gauge']<=max(0,gauge-(15 if target==16 else 0))
            idle();assert not any(s['action']==(17 if target==16 else 16)and s['state']==16 for s in samples)
            save(f'{key}{at}_Rtap_gauge{gauge}',pressed=pressed,entered=entered)
        for stage in (1,2):
            for key in ('A','X'):
                setup();f.command('R 2')
                if stage==2:
                    second()
                else:wait(lambda s:s['state']==16 and s['motion']==0x568 and s['frame']>=38)
                f.command(key+' 24');insert=22 if stage==1 else 25
                wait(lambda s:s['state']==16 and s['action']==insert and s['motion']==(0x569 if stage==1 else 0x56b)and s['frame']>=32)
                f.command('R 2');target=24 if stage==1 else 27
                entered=wait(lambda s:s['state']==16 and s['action']==target and s['motion']==(0x56a if stage==1 else 0x56c))
                idle();save(f'Spirit{stage}_{key}_resume',entered=entered)
        # Native empty-gauge behavior after an inserted attack is no II/III.
        for stage in (1,2):
            setup();f.command('R 2')
            if stage==2:
                second()
            else:wait(lambda s:s['motion']==0x568 and s['frame']>=38)
            f.command('X 24');insert=22 if stage==1 else 25
            wait(lambda s:s['action']==insert and s['motion']==(0x569 if stage==1 else 0x56b)and s['frame']>=32)
            f.fixture_bytes(a+0x2780,0);f.command('R 2');samples.clear();idle()
            assert not any(s['state']==16 and s['action']in(16,17,24,27)for s in samples)
            save(f'Spirit{stage}_insert_empty_no_follow')
        for rank in (0,1,2,3):
            setup(100,rank);f.command('A 2');wait(lambda s:s['action']==4 and s['frame']>=22)
            f.command('R 24\nB 24');wait(lambda s:s['motion']==0x5e6 and s['frame']>=90)
            samples.clear();f.command('R 2');first=wait(lambda s:s['motion']in(0x5ef,0x5f0,0x5f1,0x5f5))
            idle();rows=[s for s in samples if s['state']==16 and s['motion']==first['motion']]
            start=rows[0]['position'];late=min(rows,key=lambda s:abs(s['frame']-80));end=rows[-1]['position']
            assert all(s['heading']==first['heading'] for s in rows)
            assert late['position'][0]-start[0]>680,(rank,start,late)
            assert abs(end[2]-start[2])<100,(rank,start,end)
            assert end[0]-start[0]>700,(rank,start,end)
            # Sampling duplicates are expected; action clock must keep advancing.
            unique=list(dict.fromkeys(s['frame']for s in rows));assert all(y>x for x,y in zip(unique,unique[1:]))
            save(f'big_whiff_rank{rank}',forward=end[0]-start[0],lateral=end[2]-start[2])
        report['status']='PASS_FEEDBACK3_INPUT_AND_ROOT_TRAVEL'
    except Exception as e:report['error']=repr(e);raise
    finally:
        (f.run/'feedback3.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');f.close()

if __name__=='__main__':main()
