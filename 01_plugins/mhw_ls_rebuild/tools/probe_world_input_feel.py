"""Real pad regression: alternating loop, staggered chords and native solo R."""
import json,re,time
from pc_fixture import Fixture
from animation_port import PROJECT,sha

def main():
    f=Fixture();log=f.run/'log.txt';cases=[]
    report={'status':'FAIL','run':str(f.run),'cases':cases,
        'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro')}
    def wait(test,seconds=10):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            s=f.state()
            if test(s):return s
            time.sleep(.005)
        raise TimeoutError(s)
    def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
    def attack(action,frame=0):
        return wait(lambda s:s['state']==16 and s['action']==action and
            s['motion']=={4:0x569,25:0x56b,240:0x5e0}.get(action,s['motion']) and s['frame']>=frame)
    def segment(start):
        with log.open('rb')as stream:stream.seek(start);return stream.read().decode(errors='replace')
    try:
        f.camp_station()
        idle()
        if not f.read(f.actor+0x2749,'<B')&1:f.command('X 8');time.sleep(2.5);idle()
        start=log.stat().st_size;f.command('A 8')
        sequence=[]
        for action,key,next_action in [(4,'X',25),(25,'A',4)]*4:
            before=attack(action,25);f.command(key+' 8');after=attack(next_action)
            sequence.append({'from':action,'input':key,'at_frame':before['frame'],'to':next_action,'motion':after['motion']})
        idle();t=segment(start)
        assert len(re.findall('world_native_follow',t))>=4,t[-3000:]
        cases.append({'name':'eight_alternating_transitions','transitions':sequence})
        for order,gap in [('R',0),('R',.025),('R',.050),('A',.025),('A',.050)]:
            idle();f.fixture_bytes(f.actor+0x2780,100);time.sleep(.2)
            f.command('A 8');attack(4,60)
            start=log.stat().st_size
            # R-first after thrust, A-first after rising slash: both have a
            # real native solo destination, so this detects stolen chords.
            if order=='A':
                f.command('X 8');attack(25,60)
            f.command(order+' 16');time.sleep(gap);f.command(('A'if order=='R'else'R')+' 16')
            after=attack(240);idle();t=segment(start)
            assert 'world_chord_solo' not in t,t[-2000:]
            cases.append({'name':'staggered_foresight','first':order,'gap_seconds':gap,'entered_motion':after['motion']})
        idle();f.fixture_bytes(f.actor+0x2780,100);time.sleep(.2)
        f.command('A 8');attack(4,25);f.command('X 8');attack(25,25)
        # Control holds count presented frames, not the actor animation
        # clock. Verify the modifier is actually still down at the R tap.
        f.command('A 180');attack(4,20)
        pad=f.read(0x2326888);index=f.read(pad+0x6b60,'<i');assert 0<=index<=8
        raw=f.read(pad+index*0xb50+0x1d0);assert raw&0x2000,'A expired before R: invalid held-modifier fixture'
        f.command('R 16');attack(240);idle()
        cases.append({'name':'held_A_plus_new_R_after_loop','entered_motion':0x5e0,'raw_pad_before_R':raw})
        idle();f.fixture_bytes(f.actor+0x2780,100);time.sleep(.2)
        f.command('A 8');attack(4,60);start=log.stat().st_size;f.command('R 2')
        s=wait(lambda s:s['state']==16 and 16<=s['action']<154)
        time.sleep(.2);assert 'world_chord_solo' in segment(start)
        cases.append({'name':'short_solo_R_preserved','action':s['action']});idle()
        # Press during the source buffer window: its .10s raw-key wait
        # must finish before frame38, rather than restarting at execution.
        f.fixture_bytes(f.actor+0x2780,100);time.sleep(.2)
        f.command('A 8');pressed=attack(4,20);f.command('R 30');observed=[]
        def ready(s):
            observed.append(s)
            return s['state']==16 and 16<=s['action']<154
        after=wait(ready)
        previous=[s for s in observed if s['motion']==0x569]
        assert previous and pressed['frame']<28,pressed
        last=previous[-1];max_dt=max(s['dt']for s in previous)
        assert 38-max_dt-1<=last['frame']<38+2*max_dt+1,(last,max_dt)
        cases.append({'name':'early_R_waits_during_recovery_not_after_it','pressed_frame':pressed['frame'],
            'last_source_frame':last['frame'],'max_simulation_step':max_dt,'action':after['action']});idle()
        report['status']='PASS_LOOP_AND_STAGGERED_CHORDS'
    except Exception as exc:report['error']=repr(exc);raise
    finally:
        (f.run/'input_feel.json').write_text(json.dumps(report,indent=2)+'\n')
        (PROJECT/'research/world_input_feel.json').write_text(json.dumps(report,indent=2)+'\n');f.close()
    print(report['status'],len(cases),flush=True)

if __name__=='__main__':main()
