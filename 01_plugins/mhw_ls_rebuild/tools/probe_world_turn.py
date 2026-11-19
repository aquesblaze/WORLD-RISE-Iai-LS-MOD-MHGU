"""Actual pad turning: Iai must keep its entry heading until TIML10/12."""
import hashlib,json,time
from pc_fixture import Fixture

def delta(a,b):return ((a-b+32768)&65535)-32768
def main():
    f=Fixture();tests=[]
    def wait(test,seconds=12):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            s=f.state()
            if test(s):return s
            time.sleep(.008)
        raise TimeoutError(s)
    try:
        f.camp_station()
        origin=f.state()['position']
        for name,key,action,motion,trigger in [('small','X',247,0x5ee,10),('big','R',248,0x5ef,12)]:
            wait(lambda s:s['state']==1 and s['action']<=5)
            for off,v in zip((0x40,0x44,0x48),origin):f.fixture_bytes(f.actor+off,v,'<f')
            # Each independent turn starts from the same heading; otherwise
            # small Iai can already face the next case's stick direction.
            for off in (0xfec,0x14a0):f.fixture_bytes(f.actor+off,40051)
            f.fixture_bytes(f.actor+0x3330,0)
            if not f.read(f.actor+0x2749,'<B')&1:f.command('X 6');time.sleep(2)
            time.sleep(.4);f.command('A 8')
            wait(lambda s:s['motion']==0x569 and s['frame']>=22)
            f.command('R 18\nB 18')
            ready=wait(lambda s:s['motion']==0x5e6 and s['frame']>=82)
            baseline=ready['heading'];f.command(key+' 5\nSTICK_LEFT 30')
            rows=[];wait(lambda s:s['action']==action and s['motion']==motion)
            while True:
                s=f.state();rows.append({k:s[k] for k in ('frame','heading','motion','action')})
                if s['action']!=action or s['frame']>24:break
                time.sleep(.004)
            early=[r for r in rows if r['motion']==motion and r['frame']<trigger]
            late=[r for r in rows if r['motion']==motion and r['frame']>=trigger+3]
            assert early and late,(name,rows)
            assert all(abs(delta(r['heading'],baseline))<=1 for r in early),(name,'turned early',early)
            assert 2<=abs(delta(late[-1]['heading'],baseline))<=10924,(name,'invalid correction',late)
            tests.append({'move':name,'trigger':trigger,'baseline':baseline,'delta':delta(late[-1]['heading'],baseline),'rows':rows})
        report={'status':'PASS_IAI_TRIGGERED_TURN','run':str(f.run),'pad_driven':True,'tests':tests,
            'plugin_sha256':hashlib.sha256((f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro').read_bytes()).hexdigest()}
        (f.run/'turn_report.json').write_text(json.dumps(report,indent=2))
        print(json.dumps({**report,'tests':[{k:v for k,v in t.items() if k!='rows'} for t in tests]},indent=2))
    finally:f.close()

if __name__=='__main__':main()
