"""Exercise the clean plugin in an isolated hidden Recomp instance.

Uses Recomp's own quickhunt/control interface and a COPY of the user's save.
The normal install, active mod selection and original savedata are untouched.
"""
from pathlib import Path
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
import re
import shutil
import subprocess
import time

PROJECT=Path(__file__).resolve().parents[1]
GAME=Path(r'C:\gumod\Windows-MHGURecomp')
RUN=Path(r'C:\gumod\.cache\mhw_ls_rebuild_smoke')
RUN.mkdir(parents=True,exist_ok=True)
run=RUN/str(int(time.time()));run.mkdir()
shutil.copytree(GAME/'save',run/'save')
cache=run/'cache';cache.mkdir()
for name in ['programs.bin','pipelines.bin','vk_pipelines.bin']:
    shutil.copy2(GAME/'cache'/name,cache/name)
cfg=(GAME/'mhgurecomp.ini').read_text(encoding='utf-8-sig')
for key,value in [('SaveLocation',str(run/'save')),('Resolution','640x360'),
                  ('RenderResolution','640x360'),('FSR','Off'),('ShaderPrewarm','Off')]:
    cfg=re.sub(r'^'+key+r'\s*=.*$',lambda m:f'{key} = {value}',cfg,flags=re.M)
(run/'mhgurecomp.ini').write_text(cfg,encoding='utf8')
plugins=run/'mods/MHW_LS_REBUILD/romfs/nativeNX/plugins';plugins.mkdir(parents=True)
shutil.copy2(PROJECT/'mhw_ls_rebuild.nro',plugins/'mhw_ls_rebuild.nro')
control=run/'control.txt';control.write_text('',encoding='ascii')
env=os.environ.copy();env.update(MHGU_QUICKHUNT='101',MHGU_HIDDEN='1',
    MHGU_CONTROL=str(control),MHGU_MODS_DIR=str(run/'mods'),
    MHGU_PAD='__isolated_smoke_no_physical_pad__',SDL_JOYSTICK_DIRECTINPUT='0')
for key in ['MHGU_INPUT','MHGU_HOME']:env.pop(key,None)
logfile=open(run/'log.txt','wb')
si=subprocess.STARTUPINFO();si.dwFlags=subprocess.STARTF_USESHOWWINDOW;si.wShowWindow=0
process=subprocess.Popen([str(GAME/'mhgurecomp.exe'),str(GAME/'data')],cwd=run,env=env,
    stdout=subprocess.DEVNULL,stderr=logfile,startupinfo=si,creationflags=subprocess.CREATE_NO_WINDOW)
(PROJECT/'research/active_smoke.json').write_text(json.dumps({'pid':process.pid,'run':str(run)}),encoding='utf8')
print('Isolated game PID',process.pid,'run',run,flush=True)

k=C.WinDLL('kernel32',use_last_error=True)
k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
k.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.c_void_p];k.ReadProcessMemory.restype=W.BOOL
k.CloseHandle.argtypes=[W.HANDLE]
h=k.OpenProcess(0x10,False,process.pid)
actor=0
def log():return (run/'log.txt').read_text(encoding='utf8',errors='replace')
def command(text):
    with control.open('a',encoding='ascii') as f:f.write(text.rstrip()+'\n')
def read(offset,fmt):
    import struct
    size=struct.calcsize(fmt);b=C.create_string_buffer(size)
    if not k.ReadProcessMemory(h,0x10000000000+actor+offset,b,size,None):return None
    return struct.unpack(fmt,b.raw)[0]
def state():return (read(0x2506,'<H'),read(0x250a,'<H'),read(0x4b4,'<H'),read(0x500,'<f'))
def until(test,seconds,label):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if process.poll() is not None:raise RuntimeError(f'Game exited {process.returncode} while {label}')
        value=test()
        if value:return value
        time.sleep(.05)
    raise TimeoutError(label+'; last state '+str(state() if actor else None))

report={'build_sha256':hashlib.sha256((PROJECT/'mhw_ls_rebuild.nro').read_bytes()).hexdigest(),
        'build':'rebuild-b4','save_is_copy':True,'run':str(run),'tests':[]}
try:
    def find_actor():
        global actor
        matches=re.findall(r'ML_REBUILD: local_actor ([0-9A-F]{8})',log())
        if matches:actor=int(matches[-1],16)
        return actor
    until(find_actor,70,'quest actor startup')
    print('Quest actor',hex(actor),'state',state(),flush=True)
    time.sleep(2)
    command('X 8')
    time.sleep(3)
    for direction,expected in [('LEFT',(28,)),('RIGHT',(29,)),('DOWN',tuple(range(8,15)))]:
        # Native L centers the camera; direction classification then uses the
        # game's camera+stick heading against the hunter, not raw screen X.
        command('L 4');time.sleep(.5)
        # Thrust from drawn neutral, then hold the authored chord through its window.
        command('A 6')
        until(lambda:state()[0:3]==(16,4,0x569),4,'enter thrust '+direction)
        start=log().count('ML_REBUILD: commit')
        time.sleep(.6)
        command(f'X 12\nA 12\nSTICK_{direction} 12')
        until(lambda:state()[0]==16 and (8<=state()[1]<=14 or state()[1] in (28,29)),4,'native fade '+direction)
        actual=state()[1]
        assert actual in expected,(direction,'wrong native direction',actual,expected)
        until(lambda:state()[2] in (0x567,0x580,0x581),2,'native main clip')
        print(direction,'native fade',actual,'state',state(),flush=True)
        assert log().count('ML_REBUILD: commit')==start,'plugin forced the thrust transition'
        # Wait until the chord script has released, then buffer R on the fade.
        time.sleep(.3)
        before=log().count('ML_REBUILD: commit')
        command('R 90')
        until(lambda:log().count('ML_REBUILD: commit')>before,4,'spirit step '+direction)
        latest=re.findall(r'ML_REBUILD: commit [0-9A-F]+ ([0-9A-F]+) ([0-9A-F]+) ([0-9A-F]+)',log())[-1]
        assert int(latest[1],16)==48,(direction,'wrong follow-up',latest)
        until(lambda:'binding_ack' in log().split('ML_REBUILD: commit')[-1],2,'step binding '+direction)
        print(direction,'Spirit Step native48 bound',state(),flush=True)
        # Continue holding R through the next window. A consumed physical
        # gesture must not turn into a second attack in the new semantic state.
        count=log().count('ML_REBUILD: commit')
        time.sleep(1.5)
        assert log().count('ML_REBUILD: commit')==count,(direction,'held R repeated a commit')
        report['tests'].append({'direction':direction,'fade_native':actual,'follow_native':48,'binding_ack':True,'held_R_did_not_repeat':True})
        time.sleep(.3)
        command('B 5');time.sleep(1)
    report['result']='PASS'
except Exception as e:
    report['result']='FAIL';report['error']=str(e);print(type(e).__name__,str(e),flush=True)
finally:
    # Only the process launched above is ended; it uses private copied saves.
    if process.poll() is None:process.terminate()
    try:process.wait(timeout=8)
    except subprocess.TimeoutExpired:process.kill();process.wait()
    logfile.close();k.CloseHandle(h)
    (run/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    (PROJECT/'research/game_smoke_result.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report),flush=True)
raise SystemExit(0 if report['result']=='PASS' else 1)
