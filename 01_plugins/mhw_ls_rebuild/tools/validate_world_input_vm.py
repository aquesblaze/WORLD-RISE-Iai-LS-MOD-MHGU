"""Differential test: execute owned World x64 instructions vs portable C.

No game-process access. Unicorn executes the matching local .text snapshot.
Only the permission lookup and action-layer query are supplied as fixtures;
the button countdown, command collection and promotion are original code.
"""
from pathlib import Path
import ctypes as C
import hashlib
import json
import random
import shutil
import struct
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
PROJECT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'.cache/mhw_native_emulation'))
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *

BASE=0x140000000
HEAP=0x10000000
STACK=0x11000000
STOP=STACK+0x1000
CONTROLLER=HEAP+0x1000
PERMISSION=HEAP+0x3000
SECONDARY=HEAP+0x4000

class Oracle:
    def __init__(self):
        self.uc=Uc(UC_ARCH_X86,UC_MODE_64)
        data=(ROOT/'.cache/mhw_native/text.bin').read_bytes()
        self.uc.mem_map(BASE+0x1000,(len(data)+4095)&~4095)
        self.uc.mem_write(BASE+0x1000,data)
        self.uc.mem_map(HEAP,0x10000)
        self.uc.mem_map(STACK,0x10000)
        self.uc.mem_map(BASE+0x3eea000,0x2000)
        self.uc.mem_map(BASE+0x503c000,0x1000)
        self.uc.mem_map(BASE+0x3241000,0x1000)
        rdata=(ROOT/'.cache/mhw_native/rdata.bin').read_bytes()
        self.uc.mem_write(BASE+0x3241000,rdata[0x3241000-0x2e13000:0x3242000-0x2e13000])
        # Read the command->TIML bit table from the matching owned executable.
        exe=Path(r'D:\APP\steam\steamapps\common\Monster Hunter World\MonsterHunterWorld.exe')
        raw=exe.read_bytes()
        self.sha=hashlib.sha256(raw).hexdigest()
        expected=json.loads((ROOT/'.cache/mhw_native/source.json').read_text())['exe_sha256']
        if self.sha!=expected:raise ValueError('Native snapshot/executable mismatch')
        pe=struct.unpack_from('<I',raw,60)[0]
        count=struct.unpack_from('<H',raw,pe+6)[0]
        size=struct.unpack_from('<H',raw,pe+20)[0]
        for n in range(count):
            vs,va,rs,off=struct.unpack_from('<4I',raw,pe+24+size+n*40+8)
            if va<=0x503c418<va+rs:
                self.uc.mem_write(BASE+0x503c418,raw[off+0x503c418-va:off+0x503c418-va+8])
            if va<=0x3eeabf0<va+rs:
                self.bits=struct.unpack_from('<137i',raw,off+0x3eeabf0-va)
        if not hasattr(self,'bits'):raise ValueError('Missing native command table')
        self.uc.mem_write(BASE+0x3eeabf0,struct.pack('<137i',*self.bits))
        self.uc.hook_add(UC_HOOK_CODE,self.hook)
        self.permission=self.secondary=self.layer=0
        self.query_override=False;self.allowed=self.execute=0

    def hook(self,uc,address,size,user):
        rva=address-BASE
        if self.query_override and rva==0x1230000:value=self.allowed
        elif self.query_override and rva==0x1230070:value=self.execute
        elif rva==0x1f62080:value=PERMISSION
        elif rva==0x1f620b0:value=SECONDARY
        elif rva==0x1bff740:value=self.layer
        elif rva==0x268290:
            bit=uc.reg_read(UC_X86_REG_EDX)
            mask=self.permission if uc.reg_read(UC_X86_REG_RCX)==PERMISSION else self.secondary
            value=(mask>>bit)&1
        else:return
        uc.reg_write(UC_X86_REG_RAX,value)
        sp=uc.reg_read(UC_X86_REG_RSP)
        ret=struct.unpack('<Q',uc.mem_read(sp,8))[0]
        uc.reg_write(UC_X86_REG_RSP,sp+8)
        uc.reg_write(UC_X86_REG_RIP,ret)

    def call(self,rva,rcx,edx=0,r8=0,seconds=0):
        self.uc.mem_write(STACK+0xf000,struct.pack('<Q',STOP))
        self.uc.reg_write(UC_X86_REG_RSP,STACK+0xf000)
        self.uc.reg_write(UC_X86_REG_RCX,rcx)
        self.uc.reg_write(UC_X86_REG_EDX,edx)
        self.uc.reg_write(UC_X86_REG_R8D,r8)
        self.uc.reg_write(UC_X86_REG_XMM1,struct.unpack('<I',struct.pack('<f',seconds))[0])
        self.uc.emu_start(BASE+rva,STOP,count=50000)
        if self.uc.reg_read(UC_X86_REG_RIP)!=STOP:raise RuntimeError('Native call did not return')

def main():
    out=ROOT/'.cache/mhw_native_emulation';out.mkdir(parents=True,exist_ok=True)
    library=out/'world_input_vm.dll'
    subprocess.run([shutil.which('gcc'),'-std=c11','-O2','-shared',
                    str(PROJECT/'tests/world_input_vm_bridge.c'),'-o',str(library)],check=True)
    portable=C.CDLL(str(library));portable.button_tick.argtypes=[C.c_void_p,C.c_float]
    portable.command_collect.argtypes=[C.c_void_p]+[C.c_uint]*6
    portable.command_promote.argtypes=[C.c_void_p,C.c_uint]
    portable.command_query.argtypes=[C.c_void_p,C.c_void_p]+[C.c_uint]*5
    portable.command_query.restype=C.c_uint
    portable.command_prune.argtypes=[C.c_void_p]*5+[C.c_uint]*3
    portable.command_conflicts.argtypes=[C.c_void_p]*3
    native=Oracle();rng=random.Random(421810)
    button_cases=0
    for fps in (30,60,120,144):
        for wait in (0,.07,.10):
            for frames in (0,1,3):
                actual=C.create_string_buffer(40)
                struct.pack_into('<f',actual,12,wait);struct.pack_into('<i',actual,24,frames)
                native.uc.mem_write(HEAP,actual.raw)
                for tick in range(1200):
                    raw=int(rng.random()<.7)
                    actual[8]=bytes([raw]);native.uc.mem_write(HEAP+8,bytes([raw]))
                    seconds=C.c_float(1/fps*(.5+rng.random())).value
                    portable.button_tick(actual,seconds)
                    native.call(0x11edc90,HEAP,seconds=seconds)
                    reference=bytes(native.uc.mem_read(HEAP,40))
                    if actual.raw!=reference:
                        raise AssertionError(('button',fps,wait,frames,tick,actual.raw.hex(),reference.hex()))
                    button_cases+=1
    command_cases=0
    # The C representation is compact; compare each native array by offset.
    offsets=(0x780,0x7a0,0x7c0,0x7e0,0x800,0x820,0x840)
    native.uc.mem_write(CONTROLLER+0x30,struct.pack('<Q',HEAP+0x5000))
    actual=C.create_string_buffer(172)
    for tick in range(6000):
        if tick%19==0:
            C.memset(actual,0,172)
            for off in offsets:native.uc.mem_write(CONTROLLER+off,bytes(20))
            native.uc.mem_write(CONTROLLER+0x910,bytes(16))
        direction=[rng.uniform(-1,1)for _ in range(4)]
        struct.pack_into('<4f',actual,140,*direction)
        native.uc.mem_write(CONTROLLER+0x8f0,struct.pack('<4f',*direction))
        command=rng.choice([17,24,25,32,39,46,51,52,53,60])
        p,g,p2,g2=[rng.randrange(4)for _ in range(4)];layer=rng.randrange(2)
        bit=native.bits[command]
        native.permission=((p&1)<<(bit-1))|((p>>1)<<bit)|((g&1)<<202)|((g>>1)<<203)
        native.secondary=((p2&1)<<(bit-1))|((p2>>1)<<bit)|((g2&1)<<202)|((g2>>1)<<203)
        native.layer=layer
        portable.command_collect(actual,command,p,g,p2,g2,layer)
        native.call(0x1230990,CONTROLLER,command)
        if rng.randrange(2):
            portable.command_promote(actual,command)
            native.call(0x12308d0,CONTROLLER,command)
        reference=b''.join(bytes(native.uc.mem_read(CONTROLLER+off,20))for off in offsets)
        reference+=bytes(native.uc.mem_read(CONTROLLER+0x8f0,16))
        reference+=bytes(native.uc.mem_read(CONTROLLER+0x910,16))
        if actual.raw!=reference:
            raise AssertionError(('commands',tick,command,p,g,p2,g2,layer,actual.raw.hex(),reference.hex()))
        command_cases+=1
    query_cases=0;native.query_override=True;queries=C.create_string_buffer(60)
    for tick in range(12000):
        data=rng.randbytes(140)+bytes(32);C.memmove(actual,data,172)
        query_data=rng.randbytes(60);C.memmove(queries,query_data,60)
        for j,off in enumerate(offsets):native.uc.mem_write(CONTROLLER+off,data[j*20:j*20+20])
        for j,off in enumerate((0x860,0x880,0x8a0)):
            native.uc.mem_write(CONTROLLER+off,query_data[j*20:j*20+20])
        command=rng.choice([17,24,25,32,39,46,51,52,53,60]);kind=rng.randrange(3);mode=rng.randrange(2)
        native.allowed=rng.randrange(2);native.execute=rng.randrange(2)
        value=portable.command_query(actual,queries,command,kind,mode,native.allowed,native.execute)
        native.call((0x122fe60,0x122fdb0,0x122fcd0)[kind],CONTROLLER,command,mode)
        expected=native.uc.reg_read(UC_X86_REG_RAX)&255
        reference=b''.join(bytes(native.uc.mem_read(CONTROLLER+off,20))for off in(0x860,0x880,0x8a0))
        if value!=expected or queries.raw!=reference:
            raise AssertionError(('query',tick,command,kind,mode,native.allowed,native.execute,value,expected))
        query_cases+=1
    prune_cases=0;native.query_override=False;previous=C.create_string_buffer(20)
    for tick in range(6000):
        data=rng.randbytes(140)+bytes(32);C.memmove(actual,data,172)
        query_data=rng.randbytes(60);C.memmove(queries,query_data,60)
        for j,off in enumerate(offsets):native.uc.mem_write(CONTROLLER+off,data[j*20:j*20+20])
        for j,off in enumerate((0x860,0x880,0x8a0)):
            native.uc.mem_write(CONTROLLER+off,query_data[j*20:j*20+20])
        p=rng.randbytes(32);p2=rng.randbytes(32)
        native.permission=int.from_bytes(p,'little');native.secondary=int.from_bytes(p2,'little')
        primary=C.create_string_buffer(p);secondary=C.create_string_buffer(p2)
        force=int(rng.random()<.1);changed=rng.randrange(2);changed2=rng.randrange(2)
        native.uc.mem_write(CONTROLLER+0x9e1,bytes([force]))
        native.uc.mem_write(CONTROLLER+0x9e6,bytes([changed,changed2]))
        portable.command_prune(actual,queries,previous,primary,secondary,force,changed,changed2)
        native.call(0x1230230,CONTROLLER)
        reference=b''.join(bytes(native.uc.mem_read(CONTROLLER+off,20))for off in offsets)
        if actual.raw[:140]!=reference:raise AssertionError(('prune commands',tick,force,changed,changed2))
        reference_q=b''.join(bytes(native.uc.mem_read(CONTROLLER+off,20))for off in(0x860,0x880,0x8a0))
        if queries.raw!=reference_q or previous.raw!=bytes(native.uc.mem_read(CONTROLLER+0x8c0,20)):
            raise AssertionError(('prune queries',tick,force,changed,changed2))
        prune_cases+=1
    conflict_cases=0
    for tick in range(12000):
        data=rng.randbytes(140)+bytes(32);C.memmove(actual,data,172)
        query_data=rng.randbytes(60);C.memmove(queries,query_data,60)
        prev=rng.randbytes(20);C.memmove(previous,prev,20)
        for j,off in enumerate(offsets):native.uc.mem_write(CONTROLLER+off,data[j*20:j*20+20])
        for j,off in enumerate((0x860,0x880,0x8a0)):
            native.uc.mem_write(CONTROLLER+off,query_data[j*20:j*20+20])
        native.uc.mem_write(CONTROLLER+0x8c0,prev)
        portable.command_conflicts(actual,queries,previous)
        native.call(0x122f4f0,CONTROLLER)
        reference=b''.join(bytes(native.uc.mem_read(CONTROLLER+off,20))for off in offsets)
        if actual.raw[:140]!=reference:raise AssertionError(('conflict',tick,actual.raw[:140].hex(),reference.hex()))
        conflict_cases+=1
    report=dict(status='PASS',exe_sha256=native.sha,oracle='owned x64 instructions in Unicorn 2.1.4',
        native_rvas=['11edc90','1230990','12308d0','122fe60','122fdb0','122fcd0','1230230','122f4f0'],
        button_steps=button_cases,command_steps=command_cases,query_steps=query_cases,prune_steps=prune_cases,
        conflict_steps=conflict_cases,
        rates=[30,60,120,144],seed=421810,
        limitation='Pure input primitives only; controller gesture ordering/FSM/runtime integration need separate validation.')
    (PROJECT/'research/world_input_vm_differential.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
