"""Trace the first actual GU follow-up on the isolated PC save."""
import argparse
import hashlib
import json
import time

from pc_fixture import Fixture
from probe_guild_ownership import draw, wait


def key(f, buttons):
    f.command('\n'.join(f'{button} 6' for button in buttons))


def motion(f, value, frame):
    return wait(f, lambda s: s['state'] == 16 and s['motion'] == value and s['frame'] >= frame, 5)


def observe(f, case, gauge):
    f.camp_station()
    draw(f)
    f.fixture_values([(f.actor+0x2780, gauge, '<I'), (f.actor+0x3334, 0., '<f')])
    time.sleep(.13)
    buttons = 'R'
    if case in ('thrust', 'upper'):
        key(f, 'A')
        start = motion(f, 0x569, 26)
        if case == 'upper':
            key(f, 'X')
            start = motion(f, 0x56b, 29)
        expected = (16 if start['gauge'] >= 15 else 17, 0x568)
    elif case == 'spirit_insert':
        key(f, 'R')
        motion(f, 0x568, 55)
        key(f, 'R')
        motion(f, 0x56a, 55)
        key(f, 'A')
        start = motion(f, 0x56b, 30)
        expected = (27, 0x56c)
    else:
        if case == 'slope':
            f.fixture_values([(f.actor+0x40, 500., '<f'), (f.actor+0x44, -190., '<f')])
            time.sleep(.16)
            floor = f.state()['floor']
            key(f, 'R')
            start = motion(f, 0x568, 57)
            assert start['floor'] > floor, (floor, start)
        else:
            # Stock jump action runs its own landing. The follow-up always uses pad input.
            with (f.run/'log.txt').open('rb') as logs:
                if b'[moves] logging command table changes' not in logs.read(256*1024):
                    raise AssertionError('Restart the isolated PC fixture with MHGU_LOG_MOVES=1 for jump setup')
            f.command('plact 10 ' + ('32' if case == 'jump' else '42'))
            start = motion(f, 0x565 if case == 'jump' else 0x568, 72 if case == 'jump' else 42)
        buttons, expected = 'RB', (246, 0x5e6)
    previous = f.read(f.actor + 0x250c, '<H')
    key(f, buttons)
    # Native actions may have a preparation clip (Spirit III is 0x577 -> 0x56c).
    end = wait(f, lambda s: (s['state'], s['action']) != (16, start['action']), 5)
    if end['state'] == 16 and end['action'] == expected[0]:
        end = wait(f, lambda s: s['motion'] == expected[1] or s['action'] != expected[0], 3)
    return dict(case=case, pad=buttons, previous=previous, source=start['action'],
                source_motion=start['motion'], source_frame=start['frame'], gauge=start['gauge'],
                result=[end['action'], end['motion']], expected=expected,
                passed=end['state'] == 16 and (end['action'], end['motion']) == expected)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--baseline', action='store_true')
    parser.add_argument('--case', choices=['thrust','upper','jump','jump_spirit','slope','spirit_insert'], action='append')
    args = parser.parse_args()
    f = Fixture()
    cases = []
    try:
        plan = [(case, 100) for case in (args.case or ['thrust','upper','jump','jump_spirit','slope','spirit_insert'])]
        if not args.case:
            plan.extend([('thrust', 0), ('upper', 0)])
        for case, gauge in plan:
            try:
                row = observe(f, case, gauge)
            except (TimeoutError, AssertionError) as exc:
                row = dict(case=case, gauge=gauge, passed=False, error=str(exc))
            cases.append(row)
            print(row, flush=True)
        nro = f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'
        report = dict(plugin_sha256=hashlib.sha256(nro.read_bytes()).hexdigest(), cases=cases)
        path = f.run/f'guild_route_fixes_{time.time_ns()}.json'
        path.write_text(json.dumps(report, indent=2)+'\n', encoding='utf8')
        print(path, flush=True)
        if not args.baseline and not all(row['passed'] for row in cases):
            raise SystemExit(1)
    finally:
        f.close()


if __name__ == '__main__':
    main()
