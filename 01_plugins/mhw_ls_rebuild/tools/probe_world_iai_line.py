"""Pad-driven Iai line: source cue, native geometry, screenshots and teardown."""
import json,re,time,math
from pc_fixture import Fixture
from animation_port import PROJECT,sha

def main():
    f=Fixture();log=f.run/'log.txt';cases=[]
    report={'status':'FAIL','run':str(f.run),'cases':cases,
        'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
        'fx_arc_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_simple_fx.arc'),
        'renderer':'Native GU polyline, source wp03_004 ACT_glow0 atlas and appearance; simplified bloom/expansion.'}
    observed=[]
    def wait(test,seconds=12):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            s=f.state()
            observed.append(s)
            if test(s):return s
            time.sleep(.005)
        raise TimeoutError(s)
    def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
    try:
        f.camp_station()
        idle();origin=f.state()['position'];heading=f.state()['heading']
        for rank,slot in [(0,239),(1,240),(2,241),(3,245)]:
            idle()
            for off,v in zip((0x40,0x44,0x48),origin):f.fixture_bytes(f.actor+off,v,'<f')
            for off in (0xfec,0x14a0):f.fixture_bytes(f.actor+off,heading)
            if not f.read(f.actor+0x2749,'<B')&1:f.command('X 8');time.sleep(2.5);idle()
            f.fixture_bytes(f.actor+0x3330,rank);f.fixture_bytes(f.actor+0x332c,6000.,'<f')
            time.sleep(.25);start=log.stat().st_size
            f.command('A 8');wait(lambda s:s['motion']==0x569 and s['frame']>=24)
            f.command('R 24\nB 24');wait(lambda s:s['motion']==0x5e6 and s['frame']>=90)
            observed.clear();f.command('R 10');wait(lambda s:s['motion']==0x500+slot and s['frame']>=16)
            name='world_iai_line_rank'+str(rank);f.command('shot '+name)
            # FRAME is written before the effect update/log drain. A long
            # step can cross both cue12 and sample16 in that same update.
            # Await the emitted event before resolving its live controller.
            deadline=time.monotonic()+1
            while True:
                with log.open('rb')as stream:stream.seek(start);text=stream.read().decode(errors='replace')
                match=re.search(r'world_iai_line [0-9A-F]+ ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+)',text)
                if match or time.monotonic()>=deadline:break
                time.sleep(.005)
            assert match,text[-2000:]
            assert f.state()['motion']==0x500+slot,'Effect owner ended before live geometry read'
            controller,angle,frame=(int(x,16)for x in match.groups());expected=10 if rank in (0,2)else 12
            max_dt=max(s['dt']for s in observed)
            assert expected<=frame/1000<expected+2*max_dt+.1,(rank,frame,max_dt)
            # Resolve the current proof controller's live child; never retain
            # a particle pointer past the still-active source animation.
            child=f.read(controller+336);resource=f.read(child+244)
            path=bytes(f.read(resource+8,'<64B')).split(b'\0')[0].decode()
            assert path=='effect/world/iai_line',path
            generator=f.read(child+496);particle=f.read(generator+36)
            vertices=f.read(particle+f.read(generator+212,'<H'),'<8f')
            length=math.dist(vertices[:3],vertices[4:7]);assert 399<length<401,vertices
            assert abs(f.read(particle+64,'<f')-1)<.001
            idle();time.sleep(.2)
            with log.open('rb')as stream:stream.seek(start);text=stream.read().decode(errors='replace')
            assert len(re.findall('world_iai_line ',text))==1
            uid=0x3f64
            assert text.count('world_iai_counter_line ')==int(rank!=0),rank
            assert text.count('world_counter_ribbon ')==int(rank!=0),rank
            assert 'world_counter ' not in text
            assert re.search(r'world_simple_fx_emit [0-9A-F]+ '+f'{uid:08X} {308+rank:08X}'+r' 00000001',text)
            assert (f.run/'shots'/f'{name}.png').exists()
            cases.append({'rank':rank,'resource':path,'source':308+rank,'frame':frame/1000,'heading':angle,
                'native_vertices':vertices,'line_length':length,'screenshot':str(f.run/'shots'/f'{name}.png')})
            print('Native source line',rank,round(length,3),flush=True)
        report['status']='PASS_IAI_LINE_NATIVE_GEOMETRY'
    except Exception as exc:report['error']=repr(exc);raise
    finally:
        (f.run/'iai_line.json').write_text(json.dumps(report,indent=2)+'\n')
        if report['status'].startswith('PASS'):(PROJECT/'research/world_iai_line.json').write_text(json.dumps(report,indent=2)+'\n')
        f.close()
    print(report['status'])

if __name__=='__main__':main()
