"""Copied-save regression. Only meter/position/enemy setup uses fixture writes."""
import argparse
import json
import time
from pc_fixture import Fixture


def wait(f, predicate, seconds=10):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        state = f.state()
        if predicate(state):
            return state
        time.sleep(.012)
    raise TimeoutError(state)


def neutral(f):
    return wait(f, lambda s: s['state'] == 1 and s['action'] <= 5)


def draw(f):
    neutral(f)
    if not f.read(f.actor + 0x2749, '<B') & 1:
        f.command('X 8')
        wait(f, lambda s: f.read(f.actor + 0x2749, '<B') & 1 and s['motion'] == 0x501)
        neutral(f)
    time.sleep(.2)


def arts(f):
    f.camp_station()
    result = []
    for slot in range(2):
        draw(f)
        meter = f.actor + 0x2758 + 2 * slot
        capacity = f.read(meter + 6, '<h')
        assert capacity > 0
        f.fixture_bytes(meter, capacity, '<h')
        time.sleep(.15)
        for keys in ('UP', 'RIGHT', 'DOWN', 'LEFT', 'ZL+X', 'ZL+A', 'ZL+B'):
            f.command(chr(10).join(f'{key} 6' for key in keys.split('+')))
            states = []
            end = time.monotonic() + 1
            while time.monotonic() < end:
                s = f.state()
                row = [s['state'], s['action'], s['motion']]
                if not states or states[-1] != row:
                    states.append(row)
                time.sleep(.015)
            if f.read(meter, '<h') < capacity:
                recovered = neutral(f)
                draw(f)
                f.command('A 8')
                post = wait(f, lambda s: s['state'] == 16 and s['action'] == 4)
                result.append(dict(slot=slot+1, input=keys, full=capacity, after=f.read(meter,'<h'),
                                   states=states, recovered=recovered['state'], next_attack=post['action']))
                neutral(f)
                break
            neutral(f)
        else:
            raise AssertionError(('No activation', slot, capacity, states))
    return result


def hits(f):
    draw(f)
    enemy = next(e for e in f.state()['enemies'] if e['uid'] == 0)
    f.warp(enemy['area'])
    time.sleep(2)
    f.command('emact 2 5 1')
    draw(f)
    state=f.state()
    enemy=next(e for e in state['enemies'] if e['uid']==0 and e['area']==state['area'])
    target=enemy['actor']
    result=[]
    for key in ('A','X'):
        for gap in (90,55,130,20,160):
            f.command('emact 2 5 1')
            draw(f)
            enemy=next(e for e in f.state()['enemies'] if e['actor']==target)
            x,y,z=enemy['position']
            f.fixture_values([(f.actor+0x40,x,'<f'),(f.actor+0x44,y,'<f'),(f.actor+0x48,z-gap,'<f'),
                              (f.actor+0xfec,0,'<I'),(f.actor+0x14a0,0,'<I')])
            time.sleep(.1)
            before=f.state()
            hp=f.read(target+0x17b0)
            f.command(key+' 8')
            attack=wait(f,lambda s:s['state']==16)
            neutral(f)
            end=f.state()
            damage=hp-f.read(target+0x17b0)
            if damage>0:
                assert end['gauge']>before['gauge'], (key, damage, before['gauge'],end['gauge'])
                result.append(dict(key=key,action=attack['action'],hp_before=hp,hp_after=hp-damage,
                                   gauge_before=before['gauge'],gauge_after=end['gauge']))
                break
        else:raise AssertionError(('No contact',key))
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('case',choices=['arts','hits'])
    case=parser.parse_args().case
    f=Fixture()
    try:
        records={'arts':arts,'hits':hits}[case](f)
        print(json.dumps(records),flush=True)
        (f.run/('native_'+case+'.json')).write_text(json.dumps(records,indent=2))
    finally:f.close()
