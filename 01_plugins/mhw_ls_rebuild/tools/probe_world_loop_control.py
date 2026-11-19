"""Real pad loop under stick tilt: no draw-upper prep, re-aim or idle gap."""
import json,time
from pc_fixture import Fixture
from animation_port import sha

def main():
    f=Fixture();trials=[];report={'status':'FAIL','cases':trials};rows=[]
    def state():
        s=f.state();s['magnitude']=f.read(f.actor+0x1410,'<h')
        s['coherent']=(s['motion'],s['frame'],s['action'])==(f.read(f.actor+0x4b4,'<H'),f.read(f.actor+0x500,'<f'),f.read(f.actor+0x250a,'<H'))
        return s
    def wait(test,rows=None):
        end=time.monotonic()+12
        while time.monotonic()<end:
            s=state()
            if rows is not None:rows.append(s)
            if s['coherent'] and test(s):return s
            time.sleep(.004)
        raise TimeoutError(s)
    try:
        for stick in ('STICK_UP','STICK_RIGHT'):
            f.camp_station()
            if not f.read(f.actor+0x2749,'<B')&1:f.command('X 8');time.sleep(2)
            f.command('A 8');wait(lambda s:s['action']==4 and s['motion']==0x569 and s['frame']>=20)
            f.command(stick+' 300')
            for source,key,target,motion in [(4,'X',25,0x56b),(25,'A',4,0x569)]*3:
                before=wait(lambda s:s['action']==source and s['motion']==(0x569 if source==4 else 0x56b) and s['frame']>=25)
                f.command(key+' 8');rows=[]
                after=wait(lambda s:s['action']==target and s['motion']==motion and s['frame']>=8,rows)
                coherent=[s for s in rows if s['coherent']]
                assert coherent and all(s['motion']!=0x574 for s in coherent),'Draw-upper prep was inserted'
                assert all(s['state']==16 for s in coherent),'Combo returned to idle'
                assert any(s['magnitude']>=50 for s in coherent),'Stick fixture was not active'
                assert all(abs(((s['heading']-before['heading']+32768)&65535)-32768)<=1 for s in coherent),'Combo re-aimed'
                entered=[s for s in coherent if s['motion']==motion]
                assert entered and entered[0]['frame']<8,'Missed the attack startup'
                trials.append({'stick':stick,'from':source,'to':target,'before':before,'after':after,'rows':rows})
            wait(lambda s:s['state']==1)
            # Script durations use presented frames. Let the stick release
            # before a following probe warps into an unrelated terrain edge.
            f.command('STICK_CENTER 300');wait(lambda s:s['magnitude']<50)
        report={'status':'PASS_ALTERNATING_NATIVE_COMBO_WITH_STICK','plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),'run':str(f.run),'cases':trials}
        (f.run/'loop_control.json').write_text(json.dumps(report,indent=2)+'\n')
        print(report['status'],len(trials),'transitions')
    finally:
        f.command('STICK_CENTER 300')
        report.update(plugin_sha256=sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),run=str(f.run))
        if report['status']=='FAIL':report['failed_transition_rows']=rows
        (f.run/'loop_control.json').write_text(json.dumps(report,indent=2)+'\n')
        f.close()

if __name__=='__main__':main()
