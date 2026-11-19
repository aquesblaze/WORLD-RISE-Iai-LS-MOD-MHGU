"""Capture the reported raw R taps, gauge variants, inserted attacks and Iai path."""
import argparse,json,time
from pc_fixture import Fixture
from animation_port import sha

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--big-only',action='store_true');args=parser.parse_args()
    f=Fixture();cases=[];a=f.actor
    result={'status':'OBSERVED_ONLY','run':str(f.run),'cases':cases,
        'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro')}
    def state():
        s=f.state();s.pop('enemies',None)
        pad=f.read(0x2326888);index=f.read(pad+0x6b60,'<i')
        s.update(pad=f.read(pad+index*0xb50+0x1d0)if 0<=index<=8 else None,root_delta=f.read(a+0x1100,'<4f'),
                 chain_words=f.read(a+0x3300,'<16I'))
        return s
    def wait(test,seconds=12):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            s=state()
            if test(s):return s
            time.sleep(.003)
        raise TimeoutError(s)
    def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
    def setup(gauge=100,rank=0):
        idle();f.camp_station()
        if not f.read(a+0x2749,'<B')&1:f.command('X 8');time.sleep(2);idle()
        f.fixture_values([(a+0x2780,gauge,'<I'),(a+0x332c,6000.,'<f'),
                          (a+0x3330,rank,'<I'),(a+0x3334,0.,'<f')])
        time.sleep(.15)
    def record_until_idle(rows,seconds=5):
        end=time.monotonic()+seconds;seen=False
        while time.monotonic()<end:
            s=state();rows.append(s)
            if s['state']==16:seen=True
            if seen and s['state']==1 and s['action']<=5:return
            time.sleep(.004)
    try:
        for key,at,gauge in ([]if args.big_only else [('A',5,100),('A',20,100),('X',20,100),('X',55,100),('A',20,0)]):
            setup(gauge);f.command(key+' 2')
            before=wait(lambda s:s['state']==16 and s['frame']>=at)
            rows=[];f.command('R 2');record_until_idle(rows)
            case={'name':'raw_R','source_key':key,'pressed':before,'gauge_fixture':gauge,'rows':rows}
            cases.append(case)
            print(key,at,gauge,'=>',list(dict.fromkeys((s['action'],s['motion'])for s in rows)),flush=True)
        for key in (()if args.big_only else ('A','X')):
            setup();f.command('R 2');first=wait(lambda s:s['state']==16 and s['action']==16 and s['frame']>=50)
            f.command(key+' 24')
            inserted=wait(lambda s:s['state']==16 and s['action']!=16)
            before=wait(lambda s:s['state']==16 and s['action']==inserted['action']and s['motion']in (0x569,0x56b)and s['frame']>=35)
            rows=[];f.command('R 2');record_until_idle(rows)
            cases.append({'name':'spirit_insert','key':key,'first':first,'inserted':inserted,'pressed':before,'rows':rows})
            print('R',key,'R =>',list(dict.fromkeys((s['action'],s['motion'])for s in rows)),flush=True)
        setup(100,3);f.command('A 2');wait(lambda s:s['action']==4 and s['frame']>=22)
        f.command('R 24\nB 24');wait(lambda s:s['motion']==0x5e6 and s['frame']>=90)
        f.command('R 2');wait(lambda s:s['motion']==0x5f5)
        rows=[];record_until_idle(rows,10)
        cases.append({'name':'big_whiff','rows':rows})
        print('big path',[(round(s['frame'],1),s['heading'],[round(x,1)for x in s['position']])for s in rows[::max(1,len(rows)//12)]],flush=True)
    finally:
        (f.run/('feedback3_big_observation.json'if args.big_only else 'feedback3_observation.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8');f.close()

if __name__=='__main__':main()
