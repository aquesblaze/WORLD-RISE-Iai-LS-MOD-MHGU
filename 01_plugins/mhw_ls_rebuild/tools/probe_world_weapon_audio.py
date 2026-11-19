"""Pad-driven Foresight/Thrust audio and early cancellation in the camp."""
import json,re,time
from collections import Counter
from pc_fixture import Fixture
from animation_port import PROJECT,sha

def cues(text):
    return [[int(x,16) for x in row] for row in re.findall(
        r'world_weapon_audio_cue [0-9A-F]+ ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+)',text)]

def validate_random(text,bank):
    last={};count=0
    for request,selected,group in re.findall(r'world_weapon_audio_choice [0-9A-F]+ ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+)',text):
        request,selected,group=[int(x,16) for x in (request,selected,group)]
        definition=bank['weapon_groups'][group]
        assert request==definition['source_request'] and selected in definition['requests']
        if definition['count']>1:assert last.get(group)!=selected,('Source avoid-repeat violated',group,selected)
        last[group]=selected;count+=1
    return count

def main():
    f=Fixture();a=f.actor;log=f.run/'log.txt';cases=[]
    source=json.loads((PROJECT/'research/world_motion_audio.json').read_text(encoding='utf8'))
    bank=json.loads((PROJECT/'research/world_audio_bank.json').read_text(encoding='utf8'))
    report={'status':'FAIL','run':str(f.run),'cases':cases,'pad_driven':True,
        'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),'bank_sha256':bank['arc_sha256']}
    observed_frames={};observed_steps={}
    def wait(test,seconds=10):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            s=f.state()
            # Native action changes before its new animation binds. An old
            # Foresight motion can remain visible for one update after the
            # World audio owner has already changed to special sheathe.
            # Only count frames while that source action still owns them.
            owner={0x5e0:240,0x5e1:241}.get(s['motion'])
            if owner is None or s['state']==16 and s['action']==owner:
                observed_frames[s['motion']]=max(s['frame'],observed_frames.get(s['motion'],0))
                observed_steps[s['motion']]=max(s['dt'],observed_steps.get(s['motion'],0))
            if test(s):return s
            time.sleep(.01)
        raise TimeoutError(s)
    def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
    def read_log(start):
        with log.open('rb') as stream:stream.seek(start);return stream.read().decode('utf8',errors='replace')
    try:
        f.camp_station()
        origin=f.state()['position']
        for clip,cancel in ((140,False),(170,False),(140,True)):
            idle()
            for offset,value in zip((0x40,0x44,0x48),origin):f.fixture_bytes(a+offset,value,'<f')
            f.fixture_bytes(a+0xfec,0);f.fixture_bytes(a+0x14a0,0)
            f.fixture_bytes(a+0x3330,3);f.fixture_bytes(a+0x332c,6000.,'<f');f.fixture_bytes(a+0x2780,100)
            if not f.read(a+0x2749,'<B')&1:f.command('X 8');time.sleep(2);idle()
            time.sleep(.3);start=log.stat().st_size
            observed_frames.clear();observed_steps.clear()
            f.command('A 8');wait(lambda s:s['motion']==0x569 and s['frame']>=24)
            f.command('R 24\n'+('A' if clip==140 else 'X')+' 24')
            slot=224 if clip==140 else 225
            wait(lambda s:s['motion']==0x500+slot)
            exit_frame=None
            if cancel:
                exit_frame=wait(lambda s:s['motion']==0x5e0 and s['frame']>=26)['frame']
                f.command('R 2\nB 2');wait(lambda s:s['motion']==0x5e6)
            idle();time.sleep(.3)
            text=read_log(start);actual=[(t/1000,r) for r,t,c in cues(text) if c==clip]
            expected=sorted((e['frame'],e['request']) for e in source['weapon_one_shots'] if e['source']==clip)
            # A buffered input is not the transition. The native Foresight
            # window accepts this early input later, after its frame31 sound.
            last_source_frame=observed_frames[0x500+slot]
            if cancel:
                # The next source cue after the frame31 sound is frame50.
                # A long native step can cancel at46; that still must omit
                # frame50 and every later cue. Do not use an arbitrary45.
                omitted_boundary=min(frame for frame,_ in expected if frame>31)
                assert last_source_frame<omitted_boundary,(last_source_frame,omitted_boundary)
                expected=[e for e in expected if e[0]<=last_source_frame+.01]
            assert len(actual)==len(expected),(clip,cancel,actual,expected)
            max_dt=observed_steps[0x500+slot];assert 0<max_dt<30,max_dt
            for (at,req),(frame,expected_req) in zip(actual,expected):
                assert req==expected_req and frame<=at<frame+2*max_dt+.1,(clip,actual,expected,max_dt)
            cases.append({'source':clip,'cancelled':cancel,'cancel_input_frame':exit_frame,
                'last_observed_source_frame':last_source_frame,'observed_max_dt':max_dt,'observed':actual,'expected':expected})
            print('Weapon timeline verified',clip,'cancel',cancel,len(actual),'cues',flush=True)
        report['random_choices_verified']=validate_random(log.read_text(encoding='utf8',errors='replace'),bank)
        assert report['random_choices_verified']>=20
        report['status']='PASS_WEAPON_AUDIO_TIMELINE_AND_CANCEL'
    except Exception as exc:
        report['error']=repr(exc);raise
    finally:
        (f.run/'weapon_audio.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
        (PROJECT/'research/world_weapon_audio_playback.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
        f.close()
    print(report['status'])

if __name__=='__main__':main()
