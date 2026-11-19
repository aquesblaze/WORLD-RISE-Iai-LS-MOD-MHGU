"""Load/play converted body clips in a disposable Recomp instance.

Uses a copied save and private ARC/plugin layer. Does not enable combat moves
in the user's test installation. Screenshots are taken by Recomp itself.
"""
from pathlib import Path
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import time
from animation_port import ROOT, PROJECT, OUT, CLIPS


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--native-only',action='store_true',help='Capture GU native draw/sheathe equipment baseline')
    args=parser.parse_args()
    probe=(OUT/'body_preview.nro').read_bytes()
    if not any(marker in probe for marker in (b'build=body-preview-',b'build=attachment-preview-')):
        raise SystemExit('Expected a separately built preview NRO, not the normal plugin')
    game=ROOT/'Windows-MHGURecomp'
    run=OUT/'runs'/str(time.time_ns());run.mkdir(parents=True)
    shutil.copytree(game/'save',run/'save')
    shutil.copytree(OUT/'mods',run/'mods')
    plugin=run/'mods/MHW_BODY_PREVIEW/romfs/nativeNX/plugins/body_preview.nro'
    plugin.parent.mkdir(parents=True);shutil.copy2(OUT/'body_preview.nro',plugin)
    (run/'cache').mkdir()
    for name in ('programs.bin','pipelines.bin','vk_pipelines.bin'):
        shutil.copy2(game/'cache'/name,run/'cache'/name)
    config=(game/'mhgurecomp.ini').read_text(encoding='utf-8-sig')
    for key,value in [('SaveLocation',str(run/'save')),('Resolution','960x540'),
                      ('RenderResolution','960x540'),('FSR','Off'),('ShaderPrewarm','Off')]:
        config=re.sub(r'^'+key+r'\s*=.*$',lambda m:f'{key} = {value}',config,flags=re.M)
    (run/'mhgurecomp.ini').write_text(config,encoding='utf8')
    control=run/'control.txt';control.write_text('',encoding='ascii')
    env=os.environ.copy()
    for key in ('MHGU_INPUT','MHGU_HOME'):env.pop(key,None)
    env.update(MHGU_QUICKHUNT='101',MHGU_HIDDEN='1',MHGU_CONTROL=str(control),
               MHGU_MODS_DIR=str(run/'mods'),MHGU_PAD='__isolated_body_preview__',
               SDL_JOYSTICK_DIRECTINPUT='0')
    startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    log_file=(run/'log.txt').open('wb')
    process=subprocess.Popen([str(game/'mhgurecomp.exe'),str(game/'data')],cwd=run,env=env,
        stdout=subprocess.DEVNULL,stderr=log_file,startupinfo=startup,creationflags=subprocess.CREATE_NO_WINDOW)
    print('Animation probe',process.pid,run,flush=True)
    kernel=C.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];kernel.OpenProcess.restype=W.HANDLE
    kernel.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.c_void_p]
    kernel.ReadProcessMemory.restype=W.BOOL;kernel.CloseHandle.argtypes=[W.HANDLE]
    handle=kernel.OpenProcess(0x10,False,process.pid);actor=0
    attachment_preview=b'build=attachment-preview-' in plugin.read_bytes()
    report={'run':str(run),'plugin_sha256':hashlib.sha256(plugin.read_bytes()).hexdigest(),
            'arc_sha256':hashlib.sha256((run/'mods/MHW_BODY_PREVIEW/romfs/nativeNX/arc/player/quest/w07.arc').read_bytes()).hexdigest(),
            'save_is_copy':True,'in_place':True,'attachment_preview':attachment_preview,
            'attachment_visual_pass':False,'combat_validation':False,'tests':[]}
    expected_frames={c['world_clip']:c['frames'] for c in json.loads((PROJECT/'research/animation_port.json').read_text(encoding='utf8'))['clips']}
    def log():return (run/'log.txt').read_text(encoding='utf8',errors='replace')
    def command(text):
        with control.open('a',encoding='ascii') as f:f.write(text+'\n')
    def read(offset,fmt,address=None):
        n=struct.calcsize(fmt);b=C.create_string_buffer(n)
        if not kernel.ReadProcessMemory(handle,0x10000000000+(actor if address is None else address)+offset,b,n,None):
            raise OSError('Cannot read probe actor')
        return struct.unpack(fmt,b.raw)[0]
    def state():return [read(0x2506,'<H'),read(0x250a,'<H'),read(0x4b4,'<H'),read(0x500,'<f')]
    def until(predicate,seconds,label):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            if process.poll() is not None:raise RuntimeError(f'Game exited {process.returncode}: {label}')
            value=predicate()
            if value:return value
            time.sleep(.03)
        raise TimeoutError(label+': '+str(state() if actor else None))
    try:
        def find_actor():
            nonlocal actor
            matches=re.findall(r'ML_REBUILD: local_actor ([0-9A-F]{8})',log())
            if matches:actor=int(matches[-1],16)
            return actor
        until(find_actor,70,'quest startup');time.sleep(2)
        command('X 8');time.sleep(3)
        def equipment_snapshot():
            objects={int(role,16):int(obj,16) for obj,role in re.findall(
                r'ML_REBUILD: equip_state ([0-9A-F]{8}) ([0-9A-F]{8})',log())}
            if set(objects)!={9,10}:raise AssertionError('Missing equipment objects')
            return {role:{'address':hex(obj),'parent':read(0x13cc,'<I',obj),
                          'mode':read(0x13d4,'<I',obj),'motion':read(0x4b4,'<H',obj),
                          'mask':hex(read(0x110,'<I',obj)),
                          'pose':[read(0x40+4*i,'<f',obj) for i in range(12)]}
                    for role,obj in objects.items()}
        report['native_drawn']=equipment_snapshot()
        for world,slot,name in ([] if args.native_only else CLIPS):
            until(lambda:state()[0:3]==[1,0,0x501],5,'drawn neutral before '+name)
            command('L 4');time.sleep(.35)
            command('A 6')
            # Actual main-layer memory is authoritative; diagnostic logs are
            # intentionally bounded and may stop before the final test.
            until(lambda:state()[2]==0x500+slot,4,'correct slot '+name)
            samples=[];shots=[];equipment=[];marks=(10,30,60,100,160,230);taken=set()
            start=time.monotonic();max_frame=0
            while time.monotonic()-start<7:
                if process.poll() is not None:raise RuntimeError('Game exited during '+name)
                s=state()
                if s[2]!=0x500+slot:break
                samples.append(s);max_frame=max(max_frame,s[3])
                for mark in marks:
                    if mark not in taken and s[3]>=mark:
                        shot=f'{world}_{name}_{mark}';command('shot '+shot);shots.append(shot);taken.add(mark)
                        eq=equipment_snapshot();equipment.append({'frame':s[3],'objects':eq})
                        if attachment_preview and world==306 and mark>=100:
                            if (eq[9]['mode'],eq[9]['motion'])!=(2,0):
                                raise AssertionError('Special sheathe did not select native closed weapon')
                time.sleep(.025)
            if max_frame<expected_frames[world]-4:
                raise AssertionError(f'Clip ended early: {name}, {max_frame}/{expected_frames[world]}')
            if state()[0:3]!=[1,0,0x501]:raise AssertionError('Clip did not return to drawn neutral')
            report['tests'].append({'world_clip':world,'slot':slot,'max_observed_frame':max_frame,
                                    'observations':samples,'shots_requested':shots,'equipment':equipment,'after':state()})
            if equipment_snapshot()[9]['motion']!=1:
                raise AssertionError('Main weapon did not return to native drawn motion')
            print(name,'slot',slot,'max_frame',round(max_frame,1),'after',state(),flush=True)
            time.sleep(.5)
        command('Y 8');time.sleep(3)
        report['native_sheathed']=equipment_snapshot();report['sheathed_actor']=state()
        if read(0x2749,'<B')&1:raise AssertionError('Native sheathe did not finish')
        if report['native_sheathed'][9]['motion']!=0:
            raise AssertionError('Native closed weapon motion missing after playback')
        command('shot native_sheathed');time.sleep(.2)
        report['result']='PASS_NATIVE_CAPTURE_ONLY' if args.native_only else 'PASS_PLAYBACK_ONLY'
    except Exception as exc:
        report['result']='FAIL';report['error']=str(exc);print(type(exc).__name__,str(exc),flush=True)
    finally:
        if process.poll() is None:process.terminate()
        try:process.wait(timeout=8)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        log_file.close();kernel.CloseHandle(handle)
        text=json.dumps(report,indent=2)
        (run/'report.json').write_text(text,encoding='utf8')
        name='native_equipment_smoke.json' if args.native_only else 'animation_game_smoke.json'
        (PROJECT/'research'/name).write_text(text,encoding='utf8')
        print(report['result'],run,flush=True)
    return 0 if report['result'].startswith('PASS_') else 1


if __name__=='__main__':raise SystemExit(main())
