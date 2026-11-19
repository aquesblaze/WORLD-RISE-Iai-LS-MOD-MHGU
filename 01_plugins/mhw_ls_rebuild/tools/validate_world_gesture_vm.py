"""Differential test against World's real ground gesture instruction block.

Only collect/promote calls are intercepted to record emitted command IDs.
All native conditions and the directional promotion helper execute unchanged.
The input objects are post-11edc90 fixtures, not writes to a game process.
"""
import ctypes as C,json,random,shutil,struct,subprocess
from validate_world_input_vm import *

class GestureOracle(Oracle):
    def __init__(self):
        self.tracing=False;self.events=None
        super().__init__()
    def hook(self,uc,address,size,user):
        if self.tracing and address-BASE in(0x1230990,0x12308d0):
            ident=uc.reg_read(UC_X86_REG_EDX)+uc.reg_read(UC_X86_REG_R8D)
            if ident>=137:raise ValueError(ident)
            self.events[0 if address-BASE==0x1230990 else 1][ident//32]|=1<<(ident%32)
            sp=uc.reg_read(UC_X86_REG_RSP);ret=struct.unpack('<Q',uc.mem_read(sp,8))[0]
            uc.reg_write(UC_X86_REG_RSP,sp+8);uc.reg_write(UC_X86_REG_RIP,ret)
            return
        super().hook(uc,address,size,user)
    def gesture(self,buttons,stick,direction,roll_direction):
        self.events=[[0]*5,[0]*5];self.tracing=True
        self.uc.mem_write(CONTROLLER+0x30,struct.pack('<Q',HEAP+0x5000))
        self.uc.mem_write(HEAP+0x500c,bytes(4))
        for index,offset in enumerate((0x138,0x160,0x188,0x98)):
            self.uc.mem_write(CONTROLLER+offset,buttons[index*40:index*40+40])
        self.uc.mem_write(CONTROLLER+0x958,bytes([stick]))
        self.uc.mem_write(CONTROLLER+0x9b0,struct.pack('<2I',direction,roll_direction))
        self.uc.reg_write(UC_X86_REG_R15,CONTROLLER)
        self.uc.reg_write(UC_X86_REG_RSP,STACK+0xf000)
        self.uc.reg_write(UC_X86_REG_RBP,STACK+0x8000)
        self.uc.emu_start(BASE+0x1231d57,BASE+0x1232442,count=10000)
        if self.uc.reg_read(UC_X86_REG_RIP)!=BASE+0x1232442:raise RuntimeError('Incomplete gesture block')
        self.tracing=False
        return struct.pack('<10I',*self.events[0],*self.events[1])

def main():
    out=ROOT/'.cache/mhw_native_emulation';lib=out/'world_gesture_vm.dll'
    subprocess.run([shutil.which('gcc'),'-std=c11','-O2','-shared',
        str(PROJECT/'tests/world_input_vm_bridge.c'),'-o',str(lib)],check=True)
    portable=C.CDLL(str(lib));portable.gestures.argtypes=[C.c_void_p,C.c_void_p]+[C.c_uint]*3
    native=GestureOracle();rng=random.Random(1231);actual=C.create_string_buffer(40)
    for tick in range(20000):
        buttons=bytearray(160)
        for n in range(4):
            for off in(8,9,10,32,33,34,35,36):buttons[n*40+off]=rng.randrange(2)
        b=C.create_string_buffer(bytes(buttons));stick=rng.randrange(2);direction=rng.randrange(6);roll=rng.randrange(6)
        portable.gestures(actual,b,stick,direction,roll)
        expected=native.gesture(bytes(buttons),stick,direction,roll)
        if actual.raw!=expected:raise AssertionError((tick,stick,direction,roll,actual.raw.hex(),expected.hex()))
    report={'status':'PASS','cases':20000,'seed':1231,'exe_sha256':native.sha,
        'oracle':'Owned x64 block1231d57..1232442 plus original1233390/1232f20 helpers',
        'intercepted':['1230990 collect command IDs','12308d0 promote command IDs'],
        'limitations':'Ground gesture generation only. Native query-context flags and command pruning/runtime binding remain separate work.'}
    (PROJECT/'research/world_gesture_vm_differential.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
