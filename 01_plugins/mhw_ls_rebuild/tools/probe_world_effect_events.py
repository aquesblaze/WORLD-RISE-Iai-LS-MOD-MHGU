"""Pad-driven source306 two start edges; a one-billboard experiment only."""
import json,re,time,struct
from pc_fixture import Fixture
from animation_port import PROJECT,sha
import animation_port as p

def main():
    action=next(a for a in p.read_lmt_file(p.WORLD).actions if a.id==306)
    curve=p.compile_pose_curve(next(t for t in action.tracks if t.header.bone_id==47 and t.header.usage==1))
    f=Fixture();log=f.run/'log.txt';report={'status':'FAIL','run':str(f.run),
        'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
        'complete_effect':False,'pad_driven':True}
    pose_samples=[]
    def wait(test,seconds=10):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            s=f.state()
            if s['motion']==0x5e6:
                mapping=f.read(f.actor+0x498);records=f.read(f.actor+0x494)
                raw=f.read(mapping+12,'<B');matrix=f.read(records+160*raw+16,'<16f')
                local=curve.sample(s['frame'])
                point=[matrix[12+k]+sum(matrix[4*j+k]*local[j]for j in range(3))for k in range(3)]
                pose_samples.append({'frame':s['frame'],'point':point})
            if test(s):return s
            time.sleep(.01)
        raise TimeoutError(s)
    def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
    try:
        text=log.read_text(errors='replace');assert 'world_fx_ready' in text
        mailbox=int(re.search(r'world_fx_queued [0-9A-F]+ [0-9A-F]+ ([0-9A-F]+)',text)[1],16)
        if f.state()['area']!=0:f.warp(0)
        idle()
        if not f.read(f.actor+0x2749,'<B')&1:f.command('X 8');time.sleep(2);idle()
        f.fixture_bytes(mailbox,3);time.sleep(.1);start=log.stat().st_size
        f.command('A 8');wait(lambda s:s['motion']==0x569 and s['frame']>=24)
        f.command('R 24\nB 24');wait(lambda s:s['motion']==0x5e6)
        wait(lambda s:s['motion']==0x5e6 and s['frame']>=35);f.command('shot fx_sheathe_first')
        wait(lambda s:s['motion']==0x5e6 and s['frame']>=79);f.command('shot fx_sheathe_second')
        wait(lambda s:s['motion']==0x5e6 and s['frame']>=90);f.command('X 8');idle();time.sleep(.3)
        with log.open('rb')as stream:stream.seek(start);text=stream.read().decode(errors='replace')
        cues=[[int(v,16)for v in row]for row in re.findall(r'world_fx_cue [0-9A-F]+ ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+)',text)]
        source=json.loads((PROJECT/'research/world_presentation_map.json').read_text())
        expected=[]
        for e in source['events']:
            if e['source']==306 and e['work_keys'] in ([[0.,3010]],[[0.,3011]]):
                expected.extend((int(e['work_keys'][0][1]),frame)for frame,on in e['enable_keys']if on)
        assert len(cues)==len(expected)==2,(cues,expected)
        for (clip,work,at),(want,frame)in zip(cues,expected):assert clip==306 and work==want and frame<=at/1000<frame+2.1,(cues,expected)
        points=[[struct.unpack('<f',struct.pack('<I',int(v,16)))[0]for v in row]for row in re.findall(r'world_fx_origin [0-9A-F]+ ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+)',text)]
        assert len(points)==2 and all(abs(v)<100000 for point in points for v in point),points
        errors=[]
        for actual,(_,_,frame)in zip(points,cues):
            adjacent=[s for s in pose_samples if abs(s['frame']-frame/1000)<=2.1]
            assert adjacent,pose_samples
            error=min(sum((a-b)**2 for a,b in zip(actual,s['point']))**.5 for s in adjacent)
            assert error<5,('Source47 world point mismatch',actual,adjacent,error)
            errors.append(error)
        report.update(status='PASS_SPECIAL_SHEATHE_TWO_FX_START_EDGES',cues=cues,points=points,
            source_lmt_sha256=sha(p.WORLD),source47_adjacent_pose_errors=errors,pose_samples=pose_samples,
            limitations=['Start timing and source47-derived spawn points only; stop edge50, persistent attachment, complete emitter/shader composition and visual equivalence remain unverified.'])
        print(report['status'],cues)
    except Exception as exc:report['error']=repr(exc);raise
    finally:
        (f.run/'effect_events.json').write_text(json.dumps(report,indent=2)+'\n')
        (PROJECT/'research/world_effect_events.json').write_text(json.dumps(report,indent=2)+'\n');f.close()

if __name__=='__main__':main()
