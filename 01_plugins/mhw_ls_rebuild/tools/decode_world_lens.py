"""Decode the lens probe (world_lens / world_lens_at / world_lens_leak) from a log.

The probe in c/world_camera.inc logs the final GU camera lens while the lens is
pinned, only when a value changes:

    world_lens    <move> <fov bits> <near bits> <aspect bits>
    world_lens_at <frame> <action> <motion> <drawn>

Both lines are written in the same frame, in that order, so they are paired
here. Raw IEEE-754 words keep the log lossless; this prints the values.

Since the lens-off fix, the Spirit Roundslash zoom is suppressed during the
spirit-combo action (0x1E), every World private action, and a short tail, so a
healthy log shows one row per move at ~50 instead of the 44.8/65.5 swing.

A `world_lens_leak` row means the FOV was away from the resting value while the
pin was off (edge-triggered, capped). During normal play that is a cutscene or
another native effect; if it happens inside a spirit combo or a World move it
means the window missed a frame.

    python tools/decode_world_lens.py "log/log.txt"
"""
import struct
import sys
from pathlib import Path

MOVES = {0: 'NATIVE', 1: 'FORESIGHT', 2: 'THRUST', 3: 'RISE', 4: 'AIR',
         5: 'DOWN', 6: 'LAND', 7: 'SHEATHE', 8: 'SMALL', 9: 'BIG',
         10: 'SHEATHE_END', 11: 'GROUND'}
TAG = 'ML_REBUILD: '


def floats(*words):
    return [struct.unpack('<f', struct.pack('<I', w))[0] for w in words]


def rows(text):
    lens = None
    for line in text.splitlines():
        if TAG not in line:
            continue
        name, _, rest = line.split(TAG, 1)[1].partition(' ')
        if name == 'world_lens':
            v = [int(x, 16) for x in rest.split()[:4]]
            if len(v) == 4:
                fov, near, aspect = floats(v[1], v[2], v[3])
                lens = (v[0], fov, near, aspect)
        elif name == 'world_lens_at' and lens:
            v = [int(x, 16) for x in rest.split()[:4]]
            if len(v) == 4:
                yield lens + tuple(v)
                lens = None


def leaks(text):
    for line in text.splitlines():
        if TAG not in line:
            continue
        name, _, rest = line.split(TAG, 1)[1].partition(' ')
        if name == 'world_lens_leak':
            v = [int(x, 16) for x in rest.split()[:4]]
            if len(v) == 4:
                yield (floats(v[0])[0],) + tuple(v[1:])


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else 'log/log.txt')
    text = path.read_text(encoding='utf8', errors='replace')
    out = list(rows(text))
    if not out:
        print('no world_lens lines: the probe build was not running, or no World move bound')
    else:
        print(f'{"move":<12}{"frame":>7}{"fov":>9}{"near":>9}{"aspect":>8}  action motion drawn')
        for move, fov, near, aspect, frame, action, motion, drawn in out:
            print(f'{MOVES.get(move, str(move)):<12}{frame:>7}{fov:>9.3f}{near:>9.3f}{aspect:>8.3f}'
                  f'  {action:>6} {motion:#06x} {drawn}')
    bad = list(leaks(text))
    print(f'\nleaks: {len(bad)}')
    for fov, action, motion, drawn in bad:
        print(f'  fov={fov:7.3f}  action={action:>4} motion={motion:#06x} drawn={drawn}')


if __name__ == '__main__':
    main()
