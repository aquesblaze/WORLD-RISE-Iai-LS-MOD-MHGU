"""The independent entry uses its own save/config and exactly the installed pair."""
import argparse,hashlib,json,os,subprocess,sys
from pathlib import Path

ROOT=Path(os.environ.get('MHGU_WORLD_RUNTIME_ROOT',Path(__file__).resolve().parents[3])).resolve()
DEST=ROOT/'02_build/testing/mhw_ls_rebuild'

PREVIEW=ROOT/'02_build/testing/mhw_ls_ground_preview'

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify_install(dest=DEST):
    dest=dest.resolve()
    if dest not in (DEST.resolve(),PREVIEW.resolve()):raise ValueError('Unexpected install directory')
    m=json.loads((dest/'manifest.json').read_text(encoding='utf-8-sig'))
    if m.get('build')!='world-controller-dev':raise ValueError('Six-move test build is not installed')
    for relative,expected in m['files'].items():
        p=(dest/relative).resolve()
        if not p.is_relative_to(dest) or digest(p)!=expected:raise ValueError('Installed asset mismatch: '+relative)
    cfg=(dest/'profile/mhgurecomp.ini').read_text(encoding='utf-8-sig')
    import re
    save=re.search(r'^SaveLocation\s*=\s*(.+)$',cfg,re.M)
    if not save or Path(save[1].strip()).resolve()!=(dest/'profile/save').resolve():
        raise ValueError('Independent save path is not configured')
    return m

def main():
    p=argparse.ArgumentParser();p.add_argument('--verify',action='store_true')
    p.add_argument('--quest',default='229');p.add_argument('--hold',type=int,default=0)
    p.add_argument('--profile-rendering',action='store_true',help='Verification only: preserve installed rendering settings')
    p.add_argument('--visible',action='store_true',help='Verification only: show the isolated game window')
    p.add_argument('--ground-preview',action='store_true')
    p.add_argument('--verify-audio-arc',type=Path,help='Use an A/B sound bank in the temporary verification run')
    p.add_argument('--verify-stock',action='store_true',help='Native baseline with an empty run-local mods directory')
    args=p.parse_args()
    if args.verify_audio_arc and not args.verify:p.error('--verify-audio-arc requires --verify')
    if args.verify_stock and (not args.verify or not args.hold or args.verify_audio_arc):
        p.error('--verify-stock requires --verify --hold and an unmodified game')
    dest=PREVIEW if args.ground_preview else DEST
    m=verify_install(dest);game=ROOT/'Windows-MHGURecomp'
    print('Unmodded reference' if args.verify_stock else 'Independent six-move test: '+m['plugin_sha256'],flush=True)
    if args.verify:
        return subprocess.call([sys.executable,str(Path(__file__).with_name('smoke_world_controller.py')),
            '--installed',str(dest),'--quest',args.quest,'--hold',str(args.hold),
            *(['--audio-arc',str(args.verify_audio_arc.resolve(strict=True))] if args.verify_audio_arc else []),
            *(['--stock'] if args.verify_stock else []),
            *(['--profile-rendering'] if args.profile_rendering else []),
            *(['--visible'] if args.visible else [])])
    env=os.environ.copy()
    for key in ('MHGU_QUICKHUNT','MHGU_CONTROL','MHGU_HIDDEN','MHGU_PAD','MHGU_INPUT','MHGU_HOME','MHGU_EMTRACE','MHGU_AUDIO_LOG','MHGU_AUDIO_TRACE'):
        env.pop(key,None)
    env.update(MHGU_MODS_DIR=str(dest/'mods'),SDL_JOYSTICK_DIRECTINPUT='0',SDL_XINPUT_ENABLED='1')
    si=subprocess.STARTUPINFO();si.dwFlags=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
    log=(dest/'profile/last_launch.log').open('wb')
    subprocess.Popen([str(game/'mhgurecomp.exe'),str(game/'data')],cwd=dest/'profile',env=env,
        stdout=subprocess.DEVNULL,stderr=log,startupinfo=si,creationflags=subprocess.CREATE_NO_WINDOW)
    log.close();return 0

if __name__=='__main__':raise SystemExit(main())
