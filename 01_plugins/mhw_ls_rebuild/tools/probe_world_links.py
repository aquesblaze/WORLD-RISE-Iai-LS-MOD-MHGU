"""Camp regression with a recorded position reset between independent cases.

Actions and animation clocks are always driven by pad input. Recenter prevents
successive Iai root motions carrying the fixture over the camp ledge.
"""
import hashlib,json,time
from pc_fixture import Fixture

def main():
    f=Fixture();rows=[];tests=[];origin=None
    def sample():
        s=f.state();s['drawn']=f.read(f.actor+0x2749,'<B')&1
        s['at']=time.monotonic();rows.append(s);return s
    def wait(test,seconds=12):
        until=time.monotonic()+seconds
        while time.monotonic()<until:
            s=sample()
            if test(s):return s
            time.sleep(.01)
        raise TimeoutError(s)
    def neutral():return wait(lambda s:s['state']==1 and s['action']<=5)
    def command(keys,n=5):f.command('\n'.join(f'{k} {n}' for k in keys))
    def normal_thrust():
        neutral();time.sleep(.3)
        if origin:
            for off,value in zip((0x40,0x44,0x48),origin):f.fixture_bytes(f.actor+off,value,'<f')
            time.sleep(.15)
        if not f.read(f.actor+0x2749,'<B')&1:command(['X']);time.sleep(2);neutral()
        command(['A']);wait(lambda s:s['state']==16 and s['action']==4 and s['motion']==0x569 and s['frame']>=18)
    def sheathe():
        normal_thrust();command(['R','B'],24)
        return wait(lambda s:s['action']==246 and s['motion']==0x5e6 and s['frame']>=80)
    def small():
        sheathe();command(['X']);return wait(lambda s:s['action']==247 and s['motion']==0x5ee)
    result={'status':'FAIL','run':str(f.run),'pad_driven_actions':True,'position_reset_between_cases':True,'tests':tests,'observations':rows,
        'plugin_sha256':hashlib.sha256((f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro').read_bytes()).hexdigest()}
    try:
        f.camp_station()
        origin=sample()['position']
        start=sheathe()
        exit_motion=wait(lambda s:s['action']==249 and s['motion']==0x5f6)
        end=neutral()
        elapsed=end['at']-start['at']
        assert elapsed<7 and end['drawn']==0
        tests.append({'name':'sheathe_timeout_returns_control','seconds_after_ready':elapsed,'exit_motion':exit_motion['motion'],'drawn_after':end['drawn']})
        for name,keys,buffer,expected,motion in [('small_buffered_X',['X'],31,(16,5),0x566),
                                       ('small_buffered_A',['A'],31,(16,4),0x569),
                                       ('small_buffered_fade',['X','A'],31,(16,8),0x567),
                                       ('small_buffered_roll',['B'],41,(1,6),0x1c)]:
            small();before=wait(lambda s:s['action']==247 and s['frame']>=buffer)
            command(keys,2)
            after=wait(lambda s:(s['state'],s['action'])==expected and s['motion']==motion)
            assert before['frame']<50 if buffer==31 else before['frame']<60
            tests.append({'name':name,'pressed_at':before['frame'],'result':expected,'next_motion':after['motion']})
            neutral()
        for key in ('R','X','A'):
            f.fixture_bytes(f.actor+0x2780,100)
            small()
            wait(lambda s:s['motion']==0x5ee and s['frame']>=32)
            command(['R'],4)
            wait(lambda s:s['action']==250 and s['motion']==0x5cd)
            main=wait(lambda s:s['action']==250 and s['motion']==0x58f)
            assert 42<=main['frame']<=45,main
            wait(lambda s:s['motion']==0x58f and s['frame']>=45)
            command([key],6)
            if key!='R':
                # GU action 22 starts with its short prep, then switches to
                # the native thrust clock. That second motion owns the R window.
                insert=wait(lambda s:s['action']==22 and s['motion']==0x569 and s['frame']>=49)
                command(['R'],8)
            target=23 if key=='R' else 24
            follow=wait(lambda s:s['state']==16 and s['action']==target and s['motion']==0x56a)
            tests.append(dict(name='small_spirit_'+key,main_entry=main['frame'],
                              insert_frame=None if key=='R' else insert['frame'],
                              native_action=target,gauge_before=main['gauge'],gauge_after=follow['gauge']))
            neutral()
        normal_thrust();command(['R','A'],24)
        wait(lambda s:s['action']==240 and s['motion']==0x5e0)
        before=wait(lambda s:s['action']==240 and s['frame']>=26)
        command(['R','B'],2)
        after=wait(lambda s:s['action']==246 and s['motion']==0x5e6)
        tests.append({'name':'foresight_early_sheathe','pressed_at':before['frame'],'next_motion':after['motion']})
        neutral()
        result['status']='PASS_CAMP_LINKS_ONLY'
    except Exception as e:
        result['error']=repr(e);raise
    finally:
        (f.run/'camp_links.json').write_text(json.dumps(result,indent=2))
        print(json.dumps({k:v for k,v in result.items() if k!='observations'},indent=2))
        f.close()

if __name__=='__main__':main()
