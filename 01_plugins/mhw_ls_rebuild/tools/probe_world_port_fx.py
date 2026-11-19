"""Capture the release's weapon effects at repeatable actor/camera poses in a copied save."""
import argparse
import json
import re
import time

from animation_port import sha
from pc_fixture import Fixture
from probe_guild_ownership import draw, wait


def capture(f, name, rank, gauge, yaw):
    f.camp_station()
    draw(f)
    actor = f.actor
    owners = re.findall(r'world_camera_owner ' + f'{actor:08X}' + r' (\w+)',
                        (f.run / 'log.txt').read_text(errors='replace'))
    camera = int(owners[-1], 16) if owners else 0
    if not camera or f.read(camera + 0x85c) != actor:
        raise ValueError('Camera no longer follows the test actor')
    setup = [(actor + 0x3330, rank, '<I'), (actor + 0x332c, 6000., '<f'),
             (actor + 0x2780, gauge, '<I')]
    if camera:
        setup.extend((camera + offset, yaw, '<I') for offset in (0x9dc, 0x9e4, 0x9ec))
    f.fixture_values(setup)
    time.sleep(.25)
    base = f.state()
    label = f'port_{name}_r{rank}_g{gauge}_v{yaw}'
    f.command('shot ' + label + '_idle')
    f.command('A 8')
    wait(f, lambda s: s['motion'] == 0x569 and s['frame'] >= 24)
    if name == 'iai':
        f.command('R 18\nB 18')
        wait(f, lambda s: s['motion'] == 0x5e6 and s['frame'] >= 82)
        f.command('R 8')
        motion = (0x5ef, 0x5f0, 0x5f1, 0x5f5)[rank]
        frames = (2, 12, 21, 48, 55, 64, 78, 91)
    else:
        f.command('R 18\n' + ('A' if name == 'foresight' else 'X') + ' 18')
        motion = 0x5e0 if name == 'foresight' else 0x5e1
        frames = (2, 7, 12, 19, 27, 42, 72) if name == 'foresight' else (3, 10, 15, 22, 43, 78, 85, 89)
    shots = []
    for target in frames:
        state = wait(f, lambda s: s['motion'] == motion and s['frame'] >= target, 5)
        shot = f'{label}_f{target}'
        f.command('shot ' + shot)
        deadline=time.monotonic()+1
        while not (f.run/'shots'/(shot+'.png')).exists():
            if time.monotonic()>=deadline:raise TimeoutError('Screenshot request was not saved: '+shot)
            time.sleep(.002)
        shots.append(dict(target=target, frame=state['frame'], motion=motion, file=shot + '.png',
                          pos=state['position'], heading=state['heading']))
    wait(f, lambda s: s['state'] == 1 and s['action'] <= 5, 12)
    for row in shots:
        if not (f.run / 'shots' / row['file']).is_file():
            raise ValueError('Capture missing: ' + row['file'])
    print(label, ' '.join(f"{s['frame']:.0f}" for s in shots), flush=True)
    return dict(move=name, rank=rank, gauge=gauge, yaw=yaw, camera=camera, base=base['position'],
                baseline=label+'_idle.png', shots=shots)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--foresight-only', action='store_true')
    args = parser.parse_args()
    f = Fixture()
    native = f.run / 'mods/MHW_WORLD_DEV/romfs/nativeNX'
    report = dict(plugin=sha(native / 'plugins/mhw_ls_rebuild.nro'),
                  effects=sha(native / 'arc/forge/world_simple_fx.arc'), cases=[])
    try:
        # The PC camera reports its owner on the first Iai. Warm it before
        # positioning the three comparison views, even on a fresh session.
        f.camp_station()
        draw(f)
        f.command('A 8')
        wait(f, lambda s: s['motion'] == 0x569 and s['frame'] >= 24)
        f.command('R 18\nB 18')
        wait(f, lambda s: s['motion'] == 0x5e6 and s['frame'] >= 82)
        f.command('R 8')
        wait(f, lambda s: s['action'] == 248)
        wait(f, lambda s: s['state'] == 1 and s['action'] <= 5)
        cases = [('foresight', 3, 100, yaw) for yaw in (16384, 32768, 49152, 1275)]
        if not args.foresight_only:
            cases += [('foresight', 0, 0, 16384), ('thrust', 0, 100, 16384),
                      ('thrust', 3, 100, 16384), ('thrust', 2, 100, 49152)] + [('iai', r, 100, 16384) for r in range(4)]
        for case in cases:
            report['cases'].append(capture(f, *case))
    finally:
        (f.run / 'port_fx_shots.json').write_text(json.dumps(report, indent=2))
        f.close()


if __name__ == '__main__':
    main()
