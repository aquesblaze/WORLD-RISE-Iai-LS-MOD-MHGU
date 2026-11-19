"""Observe actual gauge, enhancement audio and flash around an A-to-R input."""
import json,re,time
from pc_fixture import Fixture
from animation_port import sha
def main():
    f=Fixture();cases=[];result={'status':'FAIL','cases':cases}
    try:
        f.camp_station()
        if not f.read(f.actor+0x2749,'<B')&1:
            f.command('X 8');time.sleep(3)
        for initial in (0,14,15,100):
            history=[]
            def wait(pred):
                end=time.monotonic()+8
                while time.monotonic()<end:
                    s=f.state()
                    if not history or (s['motion'],s['gauge'])!=(history[-1]['motion'],history[-1]['gauge']):
                        history.append({k:s[k]for k in ('action','motion','frame','gauge')})
                    if pred(s):return s
                    time.sleep(.004)
                raise TimeoutError(s)
            wait(lambda s:s['state']==1 and s['motion']==0x501)
            log=f.run/'log.txt';offset=log.stat().st_size
            f.command('A 8');wait(lambda s:s['motion']==0x590 and s['frame']>=22)
            f.fixture_values([(f.actor+0x2780,initial,'<I')]);f.command('R 4')
            wait(lambda s:s['motion']==0x58f and s['frame']>=48)
            wait(lambda s:s['state']==1);time.sleep(.1)
            with log.open('rb')as stream:stream.seek(offset);text=stream.read().decode(errors='replace')
            charge=re.findall(r'world_spirit_charge \w+ (\w+) (\w+) (\w+)',text)
            assert len(charge)==1
            before,after,paid=(int(v,16) for v in charge[0])
            assert bool(paid)==(before>=15)
            audio=len(re.findall(r'world_audio_cue \w+ 000063A1 ',text))
            fx=len(re.findall(r'world_simple_fx_emit \w+ 00003F61 00000068 00000001',text))
            row=dict(setup=initial,before=before,after=after,audio=audio,fx=fx,history=history)
            cases.append(row);print({k:v for k,v in row.items() if k!='history'},flush=True)
            assert (audio,fx)==(int(paid),int(paid))
            assert after==before-(15 if paid else 0)
        result['status']='PASS_SPIRIT_CHARGE_BOUNDARY'
    finally:
        result['plugin_sha256']=sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro')
        (f.run/f'ground_spirit_entry_{time.time_ns()}.json').write_text(json.dumps(result,indent=2))
        f.close()
if __name__=='__main__':main()
