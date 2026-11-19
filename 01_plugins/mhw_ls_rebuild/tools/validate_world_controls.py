"""Compose original native input stages and compare the portable controller.

The oracle executes real button countdowns, gesture conditions, collect/promote,
conflict resolution, queries, primary-motion bind and pruning. Only the input
permission/layer lookups are fixtures. There is no game-process access here.
"""
import ctypes as C,json,random,shutil,struct,subprocess
from validate_world_input_vm import *

OFFSETS=(0x780,0x7a0,0x7c0,0x7e0,0x800,0x820,0x840)
BUTTONS=(0x138,0x160,0x188,0x98)

def main():
    out=ROOT/'.cache/mhw_native_emulation';lib=out/'world_controls.dll'
    subprocess.run([shutil.which('gcc'),'-std=c11','-O2','-shared',str(PROJECT/'tests/world_input_vm_bridge.c'),'-o',str(lib)],check=True)
    p=C.CDLL(str(lib));p.controls_size.restype=C.c_uint
    p.controls_tick.argtypes=[C.c_void_p]+[C.c_uint]*4+[C.c_float,C.c_void_p,C.c_void_p]+[C.c_uint]*3
    p.controls_query.argtypes=[C.c_void_p]+[C.c_uint]*3;p.controls_query.restype=C.c_uint
    p.controls_bind.argtypes=[C.c_void_p];p.controls_finish.argtypes=[C.c_void_p,C.c_void_p]
    p.controls_snapshot.argtypes=[C.c_void_p,C.c_void_p]
    actual=C.create_string_buffer(p.controls_size());snapshot=C.create_string_buffer(412)
    n=Oracle();rng=random.Random(421811)
    n.uc.mem_write(CONTROLLER+0x30,struct.pack('<Q',HEAP+0x5000))
    for j,at in enumerate(BUTTONS):
        button=bytearray(40);struct.pack_into('<f',button,12,.10 if j==2 else .07 if j<2 else 0)
        n.uc.mem_write(CONTROLLER+at,bytes(button))
    current=bytes(32);mask=C.create_string_buffer(current);direction=C.create_string_buffer(16)
    p.controls_tick(actual,1,1,0,0,1/60,mask,direction,0,5,5)
    rates=(30,60,120,144);queries=(60,53,52,51,46,39,25,32,24,17)
    held=0;query_count=0
    def block(start,end):
        n.uc.emu_start(BASE+start,BASE+end,count=50000)
        if n.uc.reg_read(UC_X86_REG_RIP)!=BASE+end:raise RuntimeError(('Incomplete native block',hex(start)))
    for tick in range(1,3201):
        seconds=C.c_float(1/rates[(tick//800)%4]).value
        if rng.random()<.22:held=rng.randrange(16)
        values=[rng.uniform(-1,1),0,rng.uniform(-1,1),0];d=struct.pack('<4f',*values)
        direction=C.create_string_buffer(d);mask=C.create_string_buffer(current)
        stick=rng.randrange(2);face=rng.randrange(6);roll=rng.randrange(6)
        p.controls_tick(actual,1,1,tick,held,seconds,mask,direction,stick,face,roll)
        n.permission=int.from_bytes(current,'little');n.secondary=n.layer=0;n.query_override=False
        for j,at in enumerate(BUTTONS):
            n.uc.mem_write(CONTROLLER+at+8,bytes([(held>>j)&1]));n.call(0x11edc90,CONTROLLER+at,seconds=seconds)
        n.uc.reg_write(UC_X86_REG_R15,CONTROLLER);n.uc.reg_write(UC_X86_REG_RAX,0)
        block(0x123187f,0x12318a9)
        n.uc.mem_write(CONTROLLER+0x8f0,d);n.uc.mem_write(CONTROLLER+0x958,bytes([stick]))
        n.uc.mem_write(CONTROLLER+0x9b0,struct.pack('<2I',face,roll))
        n.uc.reg_write(UC_X86_REG_RSP,STACK+0xf000);n.uc.reg_write(UC_X86_REG_RBP,STACK+0x8000)
        block(0x1231d57,0x1232442)
        n.call(0x122f4f0,CONTROLLER);n.uc.reg_write(UC_X86_REG_R15,CONTROLLER)
        block(0x1232ed1,0x1232f06)
        n.query_override=True;n.allowed=1
        for command in queries:
            edge=command!=17;kind=0x122fdb0 if edge else 0x122fe60
            bit=n.bits[command]
            n.execute=int(bool(n.permission&(1<<bit))or bool(n.permission&(1<<203)))
            expected=p.controls_query(actual,command,edge,0)
            n.call(kind,CONTROLLER,command)
            value=n.uc.reg_read(UC_X86_REG_RAX)&255
            if expected!=value:raise AssertionError(('query',tick,command,expected,value))
            query_count+=1
        n.query_override=False
        if rng.random()<.09:
            p.controls_bind(actual);n.call(0x122f440,CONTROLLER)
            current=rng.randbytes(32)
        n.permission=int.from_bytes(current,'little');mask=C.create_string_buffer(current)
        p.controls_finish(actual,mask);n.call(0x1230230,CONTROLLER)
        p.controls_snapshot(actual,snapshot)
        native=b''.join(bytes(n.uc.mem_read(CONTROLLER+at,40))for at in BUTTONS)
        native+=b''.join(bytes(n.uc.mem_read(CONTROLLER+at,20))for at in OFFSETS)
        native+=bytes(n.uc.mem_read(CONTROLLER+0x8f0,16))+bytes(n.uc.mem_read(CONTROLLER+0x910,16))
        native+=b''.join(bytes(n.uc.mem_read(CONTROLLER+at,20))for at in(0x860,0x880,0x8a0,0x8c0))
        if snapshot.raw!=native:
            difference=next(i for i,(a,b)in enumerate(zip(snapshot.raw,native))if a!=b)
            raise AssertionError(('state',tick,'byte',difference,snapshot.raw[difference:difference+8].hex(),native[difference:difference+8].hex()))
    report={'status':'PASS','frames':3200,'queries':query_count,'seed':421811,'rates':list(rates),
        'oracle':'Composed owned x64 instructions; 412-byte controller state compared after every frame',
        'exe_sha256':n.sha,'limitation':'Portable controller pipeline only. Integration into GU and full FSM/native-world timing validation are still required.'}
    (PROJECT/'research/world_controls_differential.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
