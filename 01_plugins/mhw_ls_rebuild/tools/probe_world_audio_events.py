"""Drive small Iai/all four big Iai clips via pad; verify paired delayed cues."""
import argparse,json,re,time
from pc_fixture import Fixture
from animation_port import PROJECT,sha

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--keep',action='store_true')
    ap.add_argument('--cycles',type=int,choices=(1,2,3),default=1);args=ap.parse_args()
    f=Fixture();a=f.actor;log=f.run/'log.txt';cases=[]
    evidence=json.loads((PROJECT/'research/world_audio_native.json').read_text(encoding='utf8'))
    bank=json.loads((PROJECT/'research/world_audio_bank.json').read_text(encoding='utf8'))
    motion_audio=json.loads((PROJECT/'research/world_motion_audio.json').read_text(encoding='utf8'))
    report={'status':'FAIL','run':str(f.run),'cases':cases,
        'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
        'bank_sha256':bank['arc_sha256'],'native_pcm_verified_separately':'world_audio_playback.json'}
    observed=[]
    def wait(test,seconds=10):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            s=f.state()
            observed.append((s['motion'],s['dt']))
            if test(s):return s
            time.sleep(.012)
        raise TimeoutError(s)
    def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
    try:
        initial_log=log.read_text(errors='replace')
        assert '[audren]' in initial_log,'Native voice trace disabled; start fixture with MHGU_AUDIO_LOG=1 and MHGU_AUDIO_TRACE=2'
        assert sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_audio.arc')==bank['arc_sha256']
        resource=int(re.search(r'world_audio_ready [0-9A-F]+ ([0-9A-F]+)',initial_log)[1],16)
        native_rows=f.read(resource+0x6c)
        attenuation=[];groups=[]
        count=len(bank['requests'])
        for request_id in range(count):
            row=native_rows+132*request_id
            assert f.read(row,'<H')==request_id
            attenuation.append(f.read(row+56,'<i'))
            groups.append(f.read(row+14,'<h'))
            assert f.read(row+24,'<B')==bank['requests'][request_id].get('voice_limit',2)
        assert attenuation==[16]*count,attenuation
        assert groups==list(range(0x300,0x300+count)),groups
        report['native_distance_curves']=attenuation
        report['native_request_overlap_groups']=groups
        f.camp_station()
        origin=f.state()['position']
        for source,rank,key,slot in [(307,3,'X',238),(308,0,'R',239),(309,1,'R',240),(310,2,'R',241),(311,3,'R',245)]*args.cycles:
            idle()
            for at,value in zip((0x40,0x44,0x48),origin):f.fixture_bytes(a+at,value,'<f')
            if not f.read(a+0x2749,'<B')&1:f.command('X 8');time.sleep(2);idle()
            f.fixture_values([(a+0x332c,6000.,'<f'),(a+0x3330,rank,'<I'),(a+0x2780,100,'<I')])
            time.sleep(.25);start=log.stat().st_size;observed.clear()
            f.command('A 8');wait(lambda s:(s['action'],s['motion']) in ((4,0x569),(250,0x590)) and s['frame']>=22)
            f.command('R 24\nB 24');wait(lambda s:s['action']==246 and s['motion']==0x5e6 and s['frame']>=90)
            f.command(key+' 10');wait(lambda s:s['motion']==0x500+slot)
            idle();time.sleep(.5)
            with log.open('rb') as stream:stream.seek(start);text=stream.read().decode('utf8',errors='replace')
            cues=re.findall(r'world_audio_cue [0-9A-F]+ ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+)',text)
            plays=re.findall(r'world_audio_play [0-9A-F]+ ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+)',text)
            plays=[p for p in plays if int(p[0],16)<6]
            assert len(cues)==1 and len(plays)==2,(source,cues,plays)
            request,frame,clock=[int(x,16) for x in cues[0]]
            expected=next(c for c in evidence['iai_cues'] if c['source']==source)
            # Source clips reach up to 2x animation speed. A rendering stall
            # can advance more than one simulation frame; bound the cue by
            # the observed step instead of assuming every update is 60 Hz.
            max_dt=max(dt for motion,dt in observed if motion==0x500+slot)
            assert 0<max_dt<30,max_dt
            assert request==expected['request'] and expected['frame']<=frame/1000<expected['frame']+2*max_dt+.1
            expected_media=[m for m in bank['media'] if m.get('source_event',{}).get('source_request')==request]
            assert {int(p[0],16) for p in plays}=={m['request_id'] for m in expected_media}
            assert plays[0][2]==plays[1][2],'Paired stems must be queued together'
            delay=(int(plays[0][2],16)-clock)/1e6
            delay_source=expected_media[0]['source_event']['delay_seconds']
            # A delayed job runs on the first simulation update at/after its
            # deadline. Preserve the no-early-play assertion under long frames.
            # Logged absolute float clocks lose sub-ms precision in a long run.
            assert delay_source-.001<=delay<delay_source+max_dt/60+.001,(source,delay,delay_source,max_dt)
            for m in expected_media:
                rate_samples=rf'fmt 6 rate {m["rate"]} ch 1 pitch 1\.000 .*?\[0,{m["samples"]}\)'
                assert re.search(rate_samples,text),('Native voice missing',source,m['media'])
            # The stereo stems can have identical lengths/rates. One matching
            # log line must not stand in for both independent wave buffers.
            for rate,samples in {(m['rate'],m['samples'])for m in expected_media}:
                addresses=set(re.findall(rf'fmt 6 rate {rate} ch 1 pitch 1\.000 .*? addr ([0-9a-f]+) .*?\[0,{samples}\)',text))
                needed=sum(m['rate']==rate and m['samples']==samples for m in expected_media)
                assert len(addresses)>=needed,('Paired native stems missing',source,addresses,needed)
            weapon_cues=[[int(x,16) for x in row] for row in re.findall(r'world_weapon_audio_cue [0-9A-F]+ ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+)',text)]
            if bank['weapon_groups']:
                for clip in (306,source):
                    expected_cues=sorted((e['frame'],e['request']) for e in motion_audio['weapon_one_shots'] if e['source']==clip)
                    # Preserve log order: a long update can emit frame23 and
                    # frame24 together. Sorting by(actual_frame,request) would
                    # reverse these source cues just because their IDs differ.
                    actual=[(t/1000,r) for r,t,s in weapon_cues if s==clip]
                    clip_slot=230 if clip==306 else slot
                    clip_dt=max(dt for motion,dt in observed if motion==0x500+clip_slot)
                    assert 0<clip_dt<30,clip_dt
                    max_step=(1 if clip==306 else 2)*clip_dt+.1
                    assert len(actual)==len(expected_cues),(clip,actual,expected_cues)
                    for (frame_actual,req_actual),(frame_expected,req_expected) in zip(actual,expected_cues):
                        assert req_actual==req_expected and frame_expected<=frame_actual<frame_expected+max_step,(clip,actual,expected_cues,max_step)
            cases.append({'source':source,'rank_fixture':rank,'request':request,'frame':frame/1000,
                'expected_frame':expected['frame'],'observed_max_dt':max_dt,'delay_seconds':delay,'expected_delay':delay_source,
                'requests':[int(p[0],16) for p in plays],'native_voices_observed':True,'weapon_timeline_cues_verified':len(weapon_cues)})
            print('Paired source audio',source,'frame',frame/1000,'delay',delay,flush=True)
        report['status']='PASS_IAI_SOURCE_AUDIO_TIMING'
        report['limits']='Five source clips and paired native voices only. Spatial motion/attenuation, dynamic Wwise bus/RTPC effects, reverb and remaining six-move sound events are pending.'
    finally:
        (f.run/'audio_events.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
        (PROJECT/'research/world_audio_events.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
        if not args.keep:(f.run/'stop').touch()
        f.close()
    print(report['status'])

if __name__=='__main__':main()
