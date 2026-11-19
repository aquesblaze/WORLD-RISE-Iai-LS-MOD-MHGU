"""Private PC instance, copied save, actual pad input and read-only observations."""
from pathlib import Path
import ctypes as C
from ctypes import wintypes as W
import argparse,json,os,re,shutil,struct,subprocess,time
from animation_port import ROOT,PROJECT,sha
from prepare_world_combat import DEST


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--quest',default='101')
    parser.add_argument('--hold',type=int,default=0)
    parser.add_argument('--profile-rendering',action='store_true',help='Keep the installed resolution/FSR for frame-pacing checks')
    parser.add_argument('--visible',action='store_true',help='Show the isolated game window for visual/frame-pacing verification')
    parser.add_argument('--installed',type=Path,help='Verify installed assets and copied test profile, without copying the development NRO')
    parser.add_argument('--audio-arc',type=Path,help='Replace world_audio.arc only in the copied run')
    parser.add_argument('--fx-arc',type=Path,help='Isolate effect layers using an ARC in the copied run')
    parser.add_argument('--plugin',type=Path,help='Run a candidate NRO against the installed test assets')
    parser.add_argument('--stock',action='store_true',help='Run stock GU as a control with the same copied profile')
    parser.add_argument('--production-mods',action='store_true',help='Test the actual PC installation mod set using a copied save')
    parser.add_argument('--mods-dir',type=Path,help='Copy a compatibility fixture mod set from the workspace cache')
    args=parser.parse_args()
    if args.production_mods and (not args.installed or not args.hold or args.stock):
        parser.error('--production-mods requires --installed --hold and cannot use --stock')
    if (args.fx_arc or args.plugin) and (not args.installed or not args.hold):
        parser.error('Candidate assets require an installed test profile and --hold')
    if args.stock and (not args.installed or not args.hold or args.audio_arc or args.fx_arc or args.plugin):
        parser.error('--stock requires an installed profile, --hold and no audio ARC override')
    game=ROOT/'Windows-MHGURecomp';run=DEST/'runs'/str(time.time_ns());run.mkdir(parents=True)
    profile=game;mods=DEST/'mods'
    if args.installed:
        from launch_world_test import verify_install
        verify_install(args.installed);profile=args.installed/'profile';mods=args.installed/'mods'
    if args.production_mods:mods=game/'mods'
    if args.mods_dir:
        mods=args.mods_dir.resolve(strict=True)
        if not args.installed or not args.hold or args.stock or args.production_mods or not mods.is_relative_to((ROOT/'.cache').resolve()):
            parser.error('--mods-dir requires --installed --hold and a cache fixture, without --stock or --production-mods')
    shutil.copytree(profile/'save',run/'save')
    if args.stock:(run/'mods').mkdir()
    else:shutil.copytree(mods,run/'mods')
    if args.audio_arc:
        bank=run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_audio.arc'
        if not bank.is_file():raise FileNotFoundError(bank)
        shutil.copyfile(args.audio_arc,bank)
        print('Run-only audio ARC:',sha(bank),flush=True)
    if args.fx_arc:
        bank=run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_simple_fx.arc'
        if not bank.is_file():raise FileNotFoundError(bank)
        shutil.copyfile(args.fx_arc,bank)
        print('Run-only effect ARC:',sha(bank),flush=True)
    plugin=run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'
    if not args.stock:
        plugin.parent.mkdir(parents=True,exist_ok=True)
        if args.plugin:shutil.copy2(args.plugin,plugin)
        elif not args.installed:shutil.copy2(PROJECT/'mhw_ls_rebuild.nro',plugin)
        if b'build=world-controller-dev' not in plugin.read_bytes():raise ValueError('Not controller test build')
    (run/'cache').mkdir()
    for n in ('programs.bin','pipelines.bin','vk_pipelines.bin'):shutil.copy2(game/'cache'/n,run/'cache'/n)
    cfg=(profile/'mhgurecomp.ini').read_text(encoding='utf-8-sig')
    overrides=[('SaveLocation',str(run/'save')),('ShaderPrewarm','Off')]
    if not args.profile_rendering:overrides += [('Resolution','640x360'),('RenderResolution','640x360'),('FSR','Off')]
    for key,value in overrides:
        cfg=re.sub(r'^'+key+r'\s*=.*$',lambda m:f'{key} = {value}',cfg,flags=re.M)
    (run/'mhgurecomp.ini').write_text(cfg,encoding='utf8')
    control=run/'control.txt';control.write_text('',encoding='ascii')
    env=os.environ.copy()
    for key in ('MHGU_INPUT','MHGU_HOME'):env.pop(key,None)
    env.update(MHGU_QUICKHUNT=args.quest,MHGU_HIDDEN='1',MHGU_EMTRACE='1',MHGU_CONTROL=str(control),MHGU_MODS_DIR=str(run/'mods'),MHGU_PAD='__isolated_world_controller__',SDL_JOYSTICK_DIRECTINPUT='0')
    if args.visible:env.pop('MHGU_HIDDEN',None)
    log_file=(run/'log.txt').open('wb');si=subprocess.STARTUPINFO();si.dwFlags=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
    proc=subprocess.Popen([str(game/'mhgurecomp.exe'),str(game/'data')],cwd=run,env=env,stdout=subprocess.DEVNULL,stderr=log_file,startupinfo=si,creationflags=subprocess.CREATE_NO_WINDOW)
    print('Controller probe',proc.pid,run,flush=True)
    k=C.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
    k.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.c_void_p];k.ReadProcessMemory.restype=W.BOOL
    k.CloseHandle.argtypes=[W.HANDLE];handle=k.OpenProcess(0x10,False,proc.pid);actor=0
    def log():return (run/'log.txt').read_text(encoding='utf8',errors='replace')
    def read(at,fmt):
        n=struct.calcsize(fmt);buf=C.create_string_buffer(n)
        if not k.ReadProcessMemory(handle,0x10000000000+actor+at,buf,n,None):raise RuntimeError('Read failed')
        return struct.unpack(fmt,buf.raw)[0]
    def state():return {'state':read(0x2506,'<H'),'action':read(0x250a,'<H'),'motion':read(0x4b4,'<H'),'frame':read(0x500,'<f'),'dt':read(0x1c,'<f'),'y':read(0x44,'<f'),'ground':read(0x10f0,'<f')}
    def command(s):
        with control.open('a',encoding='ascii') as f:f.write(s+'\n')
    def until(test,seconds,label):
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            if proc.poll() is not None:raise RuntimeError(f'Exited {proc.returncode}: '+label)
            value=test()
            if value:return value
            time.sleep(.025)
        raise TimeoutError(label+' '+str(state() if actor else log()[-800:]))
    def wait_move(move):
        until(lambda:read(0x2506,'<H')==16 and read(0x250a,'<H')==239+move,5,'move '+str(move))
        expected={1:{224},2:{225},3:{226},4:{227},5:{228},6:{229},7:{230},8:{238},9:{239,240,241,245}}[move]
        until(lambda:read(0x4b4,'<H')-0x500 in expected,2,'correct bound animation')
        command('shot world_move_'+str(move))
        result=state();print('Observed',move,result,flush=True);return result
    def neutral():until(lambda:read(0x2506,'<H')==1 and read(0x250a,'<H')<=5,10,'neutral')
    def chord(keys,frames=8):command('\n'.join(f'{key} {frames}' for key in keys))
    report={'run':str(run),'plugin_sha256':None if args.stock else sha(plugin),'save_is_copy':True,'tests':[],'combat_verified':False,
            'installed_entry':str(args.installed) if args.installed else None}
    try:
        def find_actor():
            nonlocal actor
            if args.stock:
                # Quest 229's sPlayer local slot. Only accept the local quest
                # Long Sword actor, after its native input state is initialized.
                try:
                    manager=read(0x1a85b58,'<I')
                    candidate=read(manager+0x1c,'<I') if manager else 0
                    if (candidate and read(candidate,'<I')==0x194cf64 and
                        read(candidate+0x13cc,'<I')&1 and read(candidate+0x2506,'<H')==1):
                        actor=candidate
                except RuntimeError:pass
                return actor
            match=re.findall(r'ML_REBUILD: local_actor ([0-9A-F]{8})',log())
            if match:actor=int(match[-1],16)
            return actor
        until(find_actor,70,'quest startup');time.sleep(2)
        if args.hold:
            (DEST/'active_session.json').write_text(json.dumps({'pid':proc.pid,'actor':actor,'run':str(run),'quest':args.quest,
                'installed_entry':str(args.installed) if args.installed else None}),encoding='utf8')
            command('shot initial');print('Interactive fixture ready',state(),flush=True)
            until(lambda:(run/'stop').exists(),args.hold,'interactive fixture timeout')
            report['status']='INTERACTIVE_FIXTURE_ENDED';return 0
        command('X 8');neutral();time.sleep(.4)
        chord(['R','X']);report['tests'].append({'name':'neutral_spirit_thrust','observed':wait_move(2)})
        first=state();start=time.monotonic();time.sleep(.2);last=state()
        report['clock']={'wall_seconds':time.monotonic()-start,'first':first,'last':last}
        neutral();time.sleep(.3)
        command('A 6');until(lambda:read(0x250a,'<H')==4,4,'native thrust');time.sleep(.3)
        chord(['R','A'],24);report['tests'].append({'name':'thrust_to_foresight','observed':wait_move(1)});neutral();time.sleep(.5)
        for key,move in [('X',8),('R',9)]:
            command('A 6');until(lambda:read(0x250a,'<H')==4,4,'native thrust');time.sleep(.3)
            chord(['R','B'],24);report['tests'].append({'name':'special_sheathe','observed':wait_move(7)})
            until(lambda:read(0x500,'<f')>=85,6,'sheathe ready');command(f'{key} 10')
            report['tests'].append({'name':'small_iai' if move==8 else 'big_iai','observed':wait_move(move)})
            neutral();time.sleep(.5)
        report['status']='PASS_GROUND_CONTROL_ONLY'
    except Exception as exc:
        report['status']='FAIL';report['error']=repr(exc);print(repr(exc),flush=True)
    finally:
        if handle:k.CloseHandle(handle)
        if proc.poll() is None:proc.terminate()
        try:proc.wait(timeout=10)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
        log_file.close();(run/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        if not args.hold:(PROJECT/'research/world_controller_smoke.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(report['status'],run,flush=True)
    return 0 if report['status'].startswith('PASS') else 1


if __name__=='__main__':raise SystemExit(main())
