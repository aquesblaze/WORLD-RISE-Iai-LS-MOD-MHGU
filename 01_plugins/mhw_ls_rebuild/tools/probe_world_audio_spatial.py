"""Observe actual GU voice positions while pad-driven moves pose the weapon."""
import argparse,json,math,re,struct,time
from collections import defaultdict
from pc_fixture import Fixture
from animation_port import PROJECT,sha

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--keep',action='store_true');args=ap.parse_args()
    f=Fixture();a=f.actor;log=f.run/'log.txt';rows=[]
    bank=json.loads((PROJECT/'research/world_audio_bank.json').read_text())
    anchors={r:g['root_position']for g in bank['weapon_groups']for r in g['requests']}
    text=log.read_text(encoding='utf8',errors='replace')
    resource=int(re.search(r'world_audio_ready [0-9A-F]+ ([0-9A-F]+)',text)[1],16)
    manager=f.read(0x2326d8c);count=f.read(manager+202864);assert 0<count<=128
    report={'status':'FAIL','run':str(f.run),'rows':rows,'pad_driven':True,
        'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
        'bank_sha256':bank['arc_sha256'],'source_sha256':sha(PROJECT/'research/world_audio_spatial_source.json')}
    def sample():
        state=f.state();w=f.read(a+0x23a0);assert w and f.read(w+0x30)==a
        raw_bone=f.read(f.read(w+0x498),'<B');posed=f.read(w+0x494)+160*raw_bone+16
        m=f.read(posed,'<16f');data=bytes(f.read(manager+64,f'<{2784*count}B'));voices=[]
        for i in range(count):
            at=i*2784;res,request=struct.unpack_from('<2I',data,at+12)
            if res!=resource or request not in anchors:continue
            voices.append({'address':manager+64+at,'serial':struct.unpack_from('<I',data,at+52)[0],
                'request':request,'point':struct.unpack_from('<3f',data,at+64),
                'owner':struct.unpack_from('<I',data,at+20)[0],
                'mode':struct.unpack_from('<I',data,at+172)[0]})
        rows.append({'time':time.monotonic(),'motion':state['motion'],'frame':state['frame'],
            'actor_point':state['position'],'root':m,'coherent':m==f.read(posed,'<16f'),'voices':voices})
        return state
    def wait(test,seconds=12):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            s=sample()
            if test(s):return s
            time.sleep(.005)
        raise TimeoutError(s)
    def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
    try:
        if f.state()['area']!=0:f.warp(0)
        if not f.read(a+0x2749,'<B')&1:f.command('X 8');time.sleep(2);idle()
        start=log.stat().st_size
        for key,slot in (('A',224),('X',225)):
            idle();f.fixture_bytes(a+0x2780,100);time.sleep(.2)
            f.command('A 8');wait(lambda s:s['motion']==0x569 and s['frame']>=24)
            f.command('R 24\n'+key+' 24');wait(lambda s:s['motion']==0x500+slot);idle()
        with log.open('rb')as stream:stream.seek(start);text=stream.read().decode('utf8',errors='replace')
        follows={(int(at,16),int(serial,16)):int(req,16) for _,req,at,serial in re.findall(
            r'world_audio_follow ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+)',text)}
        assert len(follows)>=10,('No native follow callbacks',follows)
        matches=defaultdict(list)
        for i,row in enumerate(rows):
            if row['motion']not in(0x5e0,0x5e1)or not row['coherent']:continue
            # The reader and native sound/model updates are separate tasks.
            # Compare adjacent coherent poses within one60Hz simulation tick.
            near=[v for v in rows[max(0,i-5):i+6]if v['coherent']and abs(v['time']-row['time'])<.025]
            for voice in row['voices']:
                key=(voice['address'],voice['serial'])
                if key not in follows:continue
                assert voice['owner']==a and voice['mode']==1
                p=anchors[voice['request']]
                expected=[[r['root'][12+k]+sum(r['root'][4*j+k]*p[j]for j in range(3))for k in range(3)]for r in near]
                error=min((math.dist(voice['point'],v)for v in expected),default=1e9)
                if error<.05:matches[key].append({'time':row['time'],'point':voice['point'],'error':error,
                    'from_hunter':math.dist(voice['point'],row['actor_point'])})
        verified=[]
        for key,samples in matches.items():
            if len(samples)<4:continue
            travel=max(math.dist(s['point'],samples[0]['point'])for s in samples)
            if travel<20:continue
            verified.append({'address':hex(key[0]),'serial':key[1],'request':follows[key],
                'source_root_offset':anchors[follows[key]],'matched_samples':len(samples),
                'movement_distance':travel,'max_error':max(s['error']for s in samples),
                'max_distance_from_hunter':max(s['from_hunter']for s in samples)})
        assert len(verified)>=4,verified
        assert {v['source_root_offset'][2]for v in verified}=={0.,80.},verified
        assert max(v['max_distance_from_hunter']for v in verified)>80,verified
        report['verified_voices']=verified;report['native_follow_callbacks']=len(follows)
        report['status']='PASS_NATIVE_WEAPON_AUDIO_FOLLOW'
        report['limits']='Weapon model1 baseline spatial mapping only; Iai effect speakers, dynamic mix and visual/audio listening acceptance remain separate.'
    except Exception as exc:report['error']=repr(exc);raise
    finally:
        (f.run/'audio_spatial.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
        compact={k:v for k,v in report.items()if k!='rows'};compact['raw_evidence']=str(f.run/'audio_spatial.json')
        (PROJECT/'research/world_audio_spatial_playback.json').write_text(json.dumps(compact,indent=2)+'\n',encoding='utf8')
        if not args.keep:(f.run/'stop').touch()
        f.close()
    print(report['status'],len(verified),'moving voices')

if __name__=='__main__':main()
