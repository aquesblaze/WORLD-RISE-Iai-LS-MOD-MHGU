"""Original-verified small Iai -> Spirit-I, with empty and full gauge fixtures."""
import hashlib,json,time
from pc_fixture import Fixture

def main():
    f=Fixture();rows=[];tests=[]
    def wait(test,seconds=12):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            s=f.state();rows.append(s)
            if test(s):return s
            time.sleep(.01)
        raise TimeoutError(s)
    result={'status':'FAIL','run':str(f.run),'tests':tests,'observations':rows,
        'resource_fixture':True,'plugin_sha256':hashlib.sha256((f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro').read_bytes()).hexdigest()}
    try:
        f.camp_station()
        for gauge in (0,100):
            wait(lambda s:s['state']==1 and s['action']<=5);time.sleep(.3)
            if not f.read(f.actor+0x2749,'<B')&1:
                f.command('X 8');time.sleep(3)
                wait(lambda s:s['state']==1 and s['action']==0 and s['motion']==0x501)
            f.command('A 8');wait(lambda s:s['action']==4 and s['motion']==0x569 and s['frame']>=18)
            f.command('R 24\nB 24');wait(lambda s:s['action']==246 and s['motion']==0x5e6 and s['frame']>=80)
            f.command('X 4');wait(lambda s:s['action']==247 and s['motion']==0x5ee)
            f.fixture_bytes(f.actor+0x2780,gauge)
            before=wait(lambda s:s['action']==247 and s['frame']>=31)
            f.command('R 2')
            after=wait(lambda s:s['state']==16 and s['action']==16 and s['motion']==0x568)
            assert before['frame']<50
            tests.append({'gauge_fixture':gauge,'pressed_at':before['frame'],'next_action':after['action'],'next_motion':after['motion']})
            wait(lambda s:s['state']==1 and s['action']<=5)
        result['status']='PASS_SMALL_TO_SPIRIT_I'
    finally:
        (f.run/'small_spirit_follow.json').write_text(json.dumps(result,indent=2))
        print(json.dumps({k:v for k,v in result.items() if k!='observations'},indent=2));f.close()

if __name__=='__main__':main()
