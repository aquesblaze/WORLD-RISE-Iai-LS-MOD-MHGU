"""Bounded scan-code input for the user's local World reference playtests.

Install PyDirectInput==1.0.4 in .cache/mhw_game_input/venv. This helper never
activates windows: use the observed World window, then check its foreground PID.
No process memory writes, drivers, game hooks or persistent key remapping.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import time

import pydirectinput as direct

EXPECTED = Path(r'D:\APP\steam\steamapps\common\Monster Hunter World\MonsterHunterWorld.exe')
OUT = Path(__file__).resolve().parents[3] / '.cache/mhw_game_input'
ALLOWED = {'esc', 'h', 'm', 'n', 'f', 'w', 'a', 's', 'd', 'q', 'e', 'space', 'alt', 'f4',
           'shift', 'ctrl', 'left', 'right', 'up', 'down',
           'mouse_left', 'mouse_right', 'mouse_middle'}
user = C.WinDLL('user32', use_last_error=True)
kernel = C.WinDLL('kernel32', use_last_error=True)
user.GetForegroundWindow.restype = W.HWND
user.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
kernel.OpenProcess.argtypes = [W.DWORD, W.BOOL, W.DWORD]
kernel.OpenProcess.restype = W.HANDLE
kernel.QueryFullProcessImageNameW.argtypes = [W.HANDLE, W.DWORD, W.LPWSTR, C.POINTER(W.DWORD)]
kernel.QueryFullProcessImageNameW.restype = W.BOOL
kernel.CloseHandle.argtypes = [W.HANDLE]


def verify_process(pid):
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise OSError(C.get_last_error(), 'Cannot query target process')
    try:
        size = W.DWORD(32768)
        name = C.create_unicode_buffer(size.value)
        if not kernel.QueryFullProcessImageNameW(handle, 0, name, C.byref(size)):
            raise OSError(C.get_last_error(), 'Cannot query target executable')
        if Path(name.value) != EXPECTED:
            raise RuntimeError('Target process is not the configured World executable')
    finally:
        kernel.CloseHandle(handle)


def foreground_is(pid):
    found = W.DWORD()
    user.GetWindowThreadProcessId(user.GetForegroundWindow(), C.byref(found))
    return found.value == pid


def event(key, down):
    if key.startswith('mouse_'):
        (direct.mouseDown if down else direct.mouseUp)(button=key[6:], _pause=False)
    else:
        (direct.keyDown if down else direct.keyUp)(key, _pause=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pid', type=int, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--keys', help='One chord, joined by +')
    mode.add_argument('--sequence', type=Path, help='JSON list of {keys: [], seconds: number}; empty keys wait')
    mode.add_argument('--look', type=int, nargs=2, metavar=('DX', 'DY'), help='Bounded relative camera movement')
    parser.add_argument('--hold', type=float, default=.18)
    parser.add_argument('--capture', action='store_true', help='Save the World window after each step')
    args = parser.parse_args()
    steps = (json.loads(args.sequence.read_text(encoding='utf8')) if args.sequence
             else [{'keys': [] if args.look else args.keys.split('+'), 'seconds': args.hold}])
    if args.look and any(abs(v) > 800 for v in args.look):
        parser.error('Camera movement must be within 800 units per axis')
    if not isinstance(steps, list) or not 1 <= len(steps) <= 16:
        parser.error('Require 1..16 steps')
    for step in steps:
        keys, seconds = step['keys'], step['seconds']
        if not isinstance(keys, list) or not 0.03 <= seconds <= 3 or len(keys) > 3:
            parser.error('Require 0..3 keys and a 0.03..3 second hold per step')
        if len(set(keys)) != len(keys) or any(k not in ALLOWED for k in keys):
            parser.error('Unsupported or duplicate key')
    if sum(s['seconds'] for s in steps) > 12:
        parser.error('Sequence exceeds 12 seconds')
    verify_process(args.pid)
    if not foreground_is(args.pid):
        raise RuntimeError('World is not foreground; no input sent')
    held = []
    started = time.time()
    captures = OUT / ('capture_' + str(time.time_ns()))
    if args.capture:
        from PIL import ImageGrab
        captures.mkdir(parents=True, exist_ok=False)
    outcome = 'released'
    try:
        for step_index, step in enumerate(steps):
            for key in step['keys']:
                if not foreground_is(args.pid):
                    raise RuntimeError('Focus changed before input')
                held.append(key)
                event(key, True)
            begin = time.monotonic()
            end = begin + step['seconds']
            sent = [0, 0]
            while time.monotonic() < end:
                if not foreground_is(args.pid):
                    raise RuntimeError('Focus changed during hold; releasing keys')
                if args.look:
                    fraction = min(1, (time.monotonic() - begin + .01) / step['seconds'])
                    target = [round(v * fraction) for v in args.look]
                    direct.moveRel(*(target[i] - sent[i] for i in range(2)), relative=True, _pause=False)
                    sent = target
                time.sleep(min(.01, max(0, end-time.monotonic())))
            for key in reversed(held):
                event(key, False)
            held.clear()
            if args.capture:
                if not foreground_is(args.pid):
                    raise RuntimeError('Focus changed before capture')
                ImageGrab.grab(window=int(user.GetForegroundWindow())).save(
                    captures / ('step_%02d.png' % step_index))
    except BaseException:
        outcome = 'aborted_and_released'
        raise
    finally:
        # A mouse-corner fail-safe must not prevent releasing a held key.
        failsafe = direct.FAILSAFE
        direct.FAILSAFE = False
        try:
            for key in reversed(held):
                event(key, False)
        finally:
            direct.FAILSAFE = failsafe
        OUT.mkdir(parents=True, exist_ok=True)
        record = {'time': started, 'pid': args.pid, 'steps': steps, 'look': args.look, 'outcome': outcome,
                  'captures': str(captures) if args.capture else None,
                  'note': 'Input delivery only; verify gameplay separately.'}
        with (OUT/'input.jsonl').open('a', encoding='utf8') as stream:
            stream.write(json.dumps(record)+'\n')
        print(json.dumps(record))


if __name__ == '__main__':
    main()
