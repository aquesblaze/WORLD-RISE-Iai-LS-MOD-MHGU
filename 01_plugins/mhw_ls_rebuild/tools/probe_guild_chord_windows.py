"""Sample pad bits, the GU thrust clock, and the next bound move in a copied quest."""
import argparse
import json
import re
import time
from pc_fixture import Fixture
from probe_guild_ownership import draw, wait

BITS={'R':0x200,'A':0x2000,'B':0x4000,'X':0x1000}
TARGET={'A':(240,0x5e0),'B':(246,0x5e6),'X':(241,0x5e1)}

def probe(f,partner,frame,first,short=False):
    f.camp_station()
    draw(f)
    f.fixture_bytes(f.actor+0x2780,100)
    f.command('A 3')
    # The host polls the control file every 50 ms. Submit the buffered
    # cases earlier so the actual pad edges are sampled inside 18..37.
    submit=18 if frame==22 else frame
    ready=wait(f,lambda s:s['action']==4 and s['motion']==0x569 and s['frame']>=submit)
    pad=f.read(0x2326888)
    mask=BITS['R']|BITS[partner]
    def buttons():
        slot=f.read(pad+0x6b60,'<i')
        assert 0<=slot<=8
        return f.read(pad+slot*0xb50+0x1d0)&mask
    phases=[]
    samples=[]
    log=f.run/'log.txt'
    offset=log.stat().st_size
    if first:
        other=partner if first=='R' else 'R'
        # R must still qualify at the partner's matured pulse (.07 s).
        # Schedule both edges on the presentation clock, not via host sleeps.
        delay=max(1,round(2/max(.1,ready['dt'])))
        f.command(f'{first} {6 if short else 9}\n{other} {4 if short else 6} {delay}')
    else:
        f.command('R 4\n'+partner+' 4')
    deadline=time.monotonic()+4
    while time.monotonic()<deadline:
        s={'frame':f.read(f.actor+0x500,'<f'),'action':f.read(f.actor+0x250a,'<H'),
           'motion':f.read(f.actor+0x4b4,'<H'),'state':f.read(f.actor+0x2506,'<H')}
        raw=buttons()
        samples.append([s['frame'],raw,s['action'],s['motion']])
        if not phases or phases[-1]!=[s['state'],s['action'],s['motion']]:
            phases.append([s['state'],s['action'],s['motion']])
        if (s['action'],s['motion'])==TARGET[partner] or s['state']==1 and s['action']==0:break
        time.sleep(.003)
    chord=[r[0] for r in samples if r[1]==mask and r[3]==0x569]
    release=[r[0] for r in samples if chord and r[0]>max(chord) and not r[1] and r[2:]==[4,0x569]]
    actual=[16,*TARGET[partner]] in phases
    if frame==5:
        delivered=bool(chord and max(chord)<18)
    elif frame==22:
        delivered=bool(chord and 18<=min(chord)<38 and
                       (first or release and min(release)<38))
    else:
        delivered=any(r[1]==mask for r in samples)
    starts={k:next((r[0] for r in samples if r[1]&BITS[k] and r[3]==0x569),None) for k in ('R',partner)}
    with log.open('rb') as stream:
        stream.seek(offset)
        scheduled={k:int(n) for k,n in re.findall(rb'\[control\] (R|A|B|X) \d+ at frame (\d+)',stream.read())}
    scheduled={k.decode():n for k,n in scheduled.items()}
    if first:
        a,b=starts[first],starts[other]
        # An immediate transition may bind before the polling sample of
        # the second button. The host's presented frame still timestamps it.
        gap=scheduled.get(other,0)-scheduled.get(first,0)
        delivered=bool(delivered and first in scheduled and other in scheduled and
                       0<gap<=delay+1 and (a is None or b is None or 0<=b-a<=3.5))
    else:
        delivered=bool(delivered and 'R' in scheduled and scheduled['R']==scheduled.get(partner))
    return dict(partner=partner,first=first,at=frame,short=short,scheduled=scheduled,raw_edges=starts,raw_chord_frames=chord,release_frame=min(release,default=None),
                phases=phases,samples=samples,delivered=delivered,passed=delivered and actual==(frame>=18))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--partner',choices=['A','B','X'],action='append')
    args=parser.parse_args()
    f=Fixture()
    cases=[]
    try:
        for partner in args.partner or ('A','B','X'):
            variants=[(5,None,False),(22,None,False),(22,'R',True),(60,None,False),(60,'R',False)]
            if partner!='B':variants.extend([(22,partner,True),(60,partner,False)])
            for at,first,short in variants:
                for attempt in range(3):
                    r=probe(f,partner,at,first,short)
                    if r['delivered']:break
                r['delivery_attempts']=attempt+1
                cases.append(r)
                print(partner,at,first,r['passed'],r['raw_chord_frames'][:1],r['release_frame'],r['phases'],flush=True)
        assert all(c['passed'] for c in cases)
    finally:
        (f.run/'guild_chord_windows.json').write_text(json.dumps(cases,indent=2))
        f.close()
if __name__=='__main__':main()
