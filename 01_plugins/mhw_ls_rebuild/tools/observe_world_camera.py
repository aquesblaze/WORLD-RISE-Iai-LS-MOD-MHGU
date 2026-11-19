"""Read-only camera telemetry from the configured local World reference game.

Locate the proven uMhCamera vtable and validate its owner backlink. No game
writes, code injection or other-process snapshots. Cache only validated pointers.
"""
import argparse,ctypes as C,json,struct,time
from ctypes import wintypes as W
from pathlib import Path

ROOT=Path(__file__).resolve().parents[3]
EXPECTED=Path(r'D:\APP\steam\steamapps\common\Monster Hunter World\MonsterHunterWorld.exe')
BASE=0x140000000

class Region(C.Structure):
    _fields_=[('base',C.c_void_p),('allocation',C.c_void_p),('allocation_protect',W.DWORD),
              ('partition',W.WORD),('size',C.c_size_t),('state',W.DWORD),('protect',W.DWORD),('kind',W.DWORD)]

class WorldCamera:
    def __init__(self,pid):
        self.pid=pid;k=self.k=C.WinDLL('kernel32',use_last_error=True)
        k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
        k.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.POINTER(C.c_size_t)]
        k.VirtualQueryEx.argtypes=[W.HANDLE,C.c_void_p,C.POINTER(Region),C.c_size_t];k.VirtualQueryEx.restype=C.c_size_t
        k.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
        k.CloseHandle.argtypes=[W.HANDLE]
        self.h=k.OpenProcess(0x1010,False,pid)
        if not self.h:raise OSError(C.get_last_error(),'OpenProcess')
        name=C.create_unicode_buffer(32768);n=W.DWORD(len(name))
        if not k.QueryFullProcessImageNameW(self.h,0,name,C.byref(n)) or Path(name.value)!=EXPECTED:
            self.close();raise ValueError('Wrong reference process')
        with (ROOT/'.cache/mhw_native/text.bin').open('rb') as f:
            f.seek(0x1f9dfa0-0x1000);guard=f.read(24)
        assert self.raw(BASE+0x1f9dfa0,24)==guard,'Different World camera implementation'
        cache=ROOT/'.cache/mhw_game_input/camera_pointer.json'
        old=json.loads(cache.read_text()) if cache.exists() else {}
        self.camera=old.get('camera',0) if old.get('pid')==pid else 0
        if not self.valid(self.camera):self.camera=self.locate()
        self.owner=self.read(self.camera+0x268,'<Q')
        cache.parent.mkdir(parents=True,exist_ok=True)
        cache.write_text(json.dumps({'pid':pid,'camera':self.camera,'owner':self.owner}))
    def raw(self,at,n):
        b=C.create_string_buffer(n);got=C.c_size_t()
        return b.raw[:got.value] if self.k.ReadProcessMemory(self.h,at,b,n,C.byref(got)) else b''
    def read(self,at,fmt):
        b=self.raw(at,struct.calcsize(fmt))
        if len(b)!=struct.calcsize(fmt):raise ValueError('Unreadable camera data')
        v=struct.unpack(fmt,b);return v[0] if len(v)==1 else v
    def valid(self,at):
        if not at:return False
        try:
            owner=self.read(at+0x268,'<Q')
            return self.read(at,'<Q')==BASE+0x3497340 and owner>0x10000 and self.read(owner+0x7690,'<Q')==at
        except ValueError:return False
    def locate(self):
        at=0;needle=struct.pack('<Q',BASE+0x3497340);found=[];end=time.monotonic()+45
        while at<0x7fffffff0000 and time.monotonic()<end:
            region=Region()
            if not self.k.VirtualQueryEx(self.h,at,C.byref(region),C.sizeof(region)):break
            top=(region.base or 0)+region.size
            if top<=at:break
            if region.state==0x1000 and region.kind==0x20000 and not region.protect&0x101:
                for start in range(region.base,top,4*1024*1024):
                    if time.monotonic()>=end:break
                    b=self.raw(start,min(4*1024*1024+7,top-start));i=b.find(needle)
                    while i>=0:
                        if self.valid(start+i):found.append(start+i)
                        i=b.find(needle,i+8)
            at=top
        assert len(found)==1,('Expected one owner-validated camera',list(map(hex,found)))
        return found[0]
    def sample(self):
        c=self.camera
        assert self.valid(c),'Camera owner changed'
        common=self.read(self.owner+0xe470,'<Q')
        return {'time':time.monotonic(),'angles':self.read(c+0x998,'<2f'),
                'start':self.read(c+0x14d0,'<2f'),'target':self.read(c+0x1530,'<2f'),
                'clock_duration':self.read(c+0x1480,'<2f'),
                'interpolator':self.read(c+0xaa8,'<Q')-BASE,
                'common_camera_duration':self.read(common+0xb4,'<f'),
                'eye':self.read(c+0x150,'<3f'),'look_at':self.read(c+0x340,'<3f'),
                'player_position':self.read(self.owner+0x160,'<3f')}
    def close(self):self.k.CloseHandle(self.h)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pid',type=int,required=True)
    ap.add_argument('--seconds',type=float,default=0);args=ap.parse_args()
    assert 0<=args.seconds<=60
    c=WorldCamera(args.pid)
    try:
        rows=[];end=time.monotonic()+args.seconds
        while True:
            rows.append(c.sample())
            if time.monotonic()>=end:break
            time.sleep(.01)
        out=ROOT/'.cache/mhw_game_input'/('camera_'+str(time.time_ns())+'.json')
        out.write_text(json.dumps({'pid':args.pid,'camera':c.camera,'owner':c.owner,'read_only':True,'rows':rows},indent=2))
        print(out);print(json.dumps(rows[-1]))
    finally:c.close()

if __name__=='__main__':main()
