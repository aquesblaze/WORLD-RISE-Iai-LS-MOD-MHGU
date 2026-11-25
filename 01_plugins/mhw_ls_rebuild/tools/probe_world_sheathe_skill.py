"""Exercise native GU Quick Sheathe flags in a copied-save fixture, then restore."""
import hashlib,json,time
from pc_fixture import Fixture

def main():
    f=Fixture();a=f.actor;tests=[];saved={};origin=None
    def wait(test,seconds=12):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            s=f.state()
            if test(s):return s
            time.sleep(.01)
        raise TimeoutError(s)
    result={'status':'FAIL','run':str(f.run),'tests':tests,'skill_bit_fixture':True,
        'plugin_sha256':hashlib.sha256((f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro').read_bytes()).hexdigest()}
    try:
        f.camp_station()
        wait(lambda s:s['state']==1 and s['action']<=5);origin=f.state()['position']
        equipment=f.read(a+0x13c4);skills=f.read(equipment+0x18c)
        assert equipment and skills
        for key in (0x5d,0x13a,0x117,0x129):
            address=skills+0x3dc+4*(key//32)
            saved.setdefault(address,f.read(address))
        for enabled in (False,True):
            values=dict(saved)
            for key in (0x5d,0x13a,0x117,0x129):
                address=skills+0x3dc+4*(key//32);values[address]&=~(1<<(key%32))
            if enabled:values[skills+0x3dc+4*(0x5d//32)]|=1<<(0x5d%32)
            for address,value in values.items():f.fixture_bytes(address,value)
            wait(lambda s:s['state']==1 and s['action']<=5)
            for off,value in zip((0x40,0x44,0x48),origin):f.fixture_bytes(a+off,value,'<f')
            if not f.read(a+0x2749,'<B')&1:
                f.command('X 8');time.sleep(3);wait(lambda s:s['state']==1 and s['motion']==0x501)
            time.sleep(.3);f.command('A 8')
            wait(lambda s:s['action']==4 and s['motion']==0x569 and s['frame']>=18)
            f.command('R 24\nB 24')
            early=wait(lambda s:s['action']==246 and s['motion']==0x5e6 and 20<=s['frame']<60)
            rate=f.read(a+0x50c,'<f')
            assert abs(rate-(1.50 if enabled else 1.))<.0001,(enabled,early,rate)
            late=wait(lambda s:s['action']==246 and s['motion']==0x5e6 and s['frame']>=90)
            late_rate=f.read(a+0x50c,'<f')
            assert abs(late_rate-1)<.0001,late_rate
            tests.append({'enabled':enabled,'early_frame':early['frame'],'early_rate':rate,
                'late_frame':late['frame'],'late_rate':late_rate})
            f.command('X 4');wait(lambda s:s['state']==1 and s['action']<=5)
        result['status']='PASS_SPECIAL_SHEATHE_SKILL'
    finally:
        for address,value in saved.items():f.fixture_bytes(address,value)
        (f.run/'sheathe_skill.json').write_text(json.dumps(result,indent=2));f.close()
        print(json.dumps(result,indent=2))

if __name__=='__main__':main()
