"""Read-only telemetry and existing control-file commands for our copied-save PC fixture."""
from pathlib import Path
import ctypes as C
from ctypes import wintypes as W
import json,struct,sys,time,os
ROOT=Path(os.environ.get('MHGU_WORLD_RUNTIME_ROOT',Path(__file__).resolve().parents[3])).resolve()

class Fixture:
    def __init__(self):
        self.meta=json.loads((ROOT/'.cache/mhw_ls_combat/active_session.json').read_text())
        self.run=Path(self.meta['run']).resolve()
        if not self.run.is_relative_to((ROOT/'.cache/mhw_ls_combat/runs').resolve()):raise ValueError('Unexpected fixture')
        self.actor=self.meta['actor'];self.k=C.WinDLL('kernel32',use_last_error=True)
        self.k.CreateMutexW.argtypes=[C.c_void_p,W.BOOL,W.LPCWSTR];self.k.CreateMutexW.restype=W.HANDLE
        self.k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD]
        self.k.ReleaseMutex.argtypes=[W.HANDLE];self.k.CloseHandle.argtypes=[W.HANDLE]
        self.mutex=self.k.CreateMutexW(None,False,'Local\\MHGU_WorldFixture_'+str(self.meta['pid']))
        if not self.mutex or self.k.WaitForSingleObject(self.mutex,0) not in (0,0x80):
            if self.mutex:self.k.CloseHandle(self.mutex)
            raise RuntimeError('Another fixture probe is active; run input/mutation probes sequentially')
        self.k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];self.k.OpenProcess.restype=W.HANDLE
        self.k.ReadProcessMemory.argtypes=[W.HANDLE,C.c_void_p,C.c_void_p,C.c_size_t,C.c_void_p]
        self.k.QueryFullProcessImageNameW.argtypes=[W.HANDLE,W.DWORD,W.LPWSTR,C.POINTER(W.DWORD)]
        self.k.CloseHandle.argtypes=[W.HANDLE]
        self.h=self.k.OpenProcess(0x1010,False,self.meta['pid'])
        buf=C.create_unicode_buffer(32768);size=W.DWORD(len(buf))
        if not self.h or not self.k.QueryFullProcessImageNameW(self.h,0,buf,C.byref(size)):raise RuntimeError('Fixture process unavailable')
        if Path(buf.value).resolve()!= (ROOT/'Windows-MHGURecomp/mhgurecomp.exe').resolve():raise ValueError('Wrong process')
    def read(self,address,fmt='<I'):
        n=struct.calcsize(fmt);buf=C.create_string_buffer(n)
        if not self.k.ReadProcessMemory(self.h,0x10000000000+address,buf,n,None):raise RuntimeError(f'Read failed {address:x}')
        values=struct.unpack(fmt,buf.raw);return values[0] if len(values)==1 else values
    def state(self):
        a=self.actor;r=self.read
        result={'state':r(a+0x2506,'<H'),'action':r(a+0x250a,'<H'),'motion':r(a+0x4b4,'<H'),
            'frame':r(a+0x500,'<f'),'dt':r(a+0x1c,'<f'),'position':r(a+0x40,'<3f'),
            'velocity':r(a+0x1010,'<3f'),'gravity':r(a+0x1024,'<f'),'floor':r(a+0x10f0,'<f'),
            'area':r(a+0x1054,'<B'),'heading':r(a+0xfec),'mode':r(a+0x2505,'<B'),
            'air':r(a+0x2514),'rank':r(a+0x3330),'gauge':r(a+0x2780),'hp':r(a+0x13d6,'<h')}
        enemies=[];manager=r(0x1a51fe0)
        for i in range(10):
            en=r(manager+0x1c+4*i) if manager else 0
            if not en:continue
            data=r(en+0x1428)
            if data:enemies.append({'actor':en,'uid':r(data+0x1b5,'<B'),'area':r(en+0x1054,'<B'),
                'position':r(data+0x40,'<3f'),'action':r(en+0x73e0),'hp':r(en+0x17b0),
                'motion':r(en+0x4b4,'<H'),'frame':r(en+0x500,'<f')})
        result['enemies']=enemies;return result
    def command(self,command):
        deadline=time.monotonic()+.5
        while True:
            try:stream=(self.run/'control.txt').open('a',encoding='ascii');break
            except PermissionError:
                if time.monotonic()>=deadline:raise
                time.sleep(.005)
        with stream:stream.write(command+'\n')
    def camp_station(self):
        """Recorded interior camp station; let prior motion/load finish first.

        Native camp entrance spawns at a zone boundary. Starting the next
        probe during the preceding Iai can cross it after the area check.
        This fixture changes station/heading only, never action or clock.
        """
        end=time.monotonic()+15
        while time.monotonic()<end:
            s=self.state()
            if s['state']==1 and s['action']<=5:break
            time.sleep(.025)
        else:raise TimeoutError('Previous action did not finish before camp fixture')
        if s['area']!=0:self.warp(0)
        # Surveyed native floor: eastward x=0..1000 at z=250 rises from
        # -188 to -135. The previous downhill station could invoke native
        # state 4 during Iai and invalidate presentation/audio measurements.
        for at,value in zip((0x40,0x44,0x48),(0.,-188.1220703125,250.)):
            self.fixture_bytes(self.actor+at,value,'<f')
        for at in (0xfec,0x14a0):self.fixture_bytes(self.actor+at,16384)
        time.sleep(.3)
    def fixture_bytes(self,address,value,fmt='<I'):
        self.fixture_values([(address,value,fmt)])
    def fixture_values(self,changes):
        """Publish related setup fields in one control-file append/frame."""
        commands=[];records=[];covered=set()
        for address,value,fmt in changes:
            raw=struct.pack(fmt,value);start=address&~3;end=(address+len(raw)+3)&~3
            words=set(range(start,end,4));assert not words&covered,'Overlapping setup fields need a combined value'
            covered|=words
            old=bytes(self.read(start,f'<{end-start}B'));new=bytearray(old)
            new[address-start:address-start+len(raw)]=raw
            commands.extend(f'poke {start+i:x} {struct.unpack_from("<I",new,i)[0]:x}' for i in range(0,len(new),4))
            records.append({'at':time.time(),'address':address,'format':fmt,'value':value,'before':old.hex(),'batch':True})
        self.command('\n'.join(commands))
        with (self.run/'fixture_changes.jsonl').open('a',encoding='utf8') as f:
            for record in records:f.write(json.dumps(record)+'\n')
    def warp(self,zone):
        stage=self.read(0x1a977a0);area=self.read(0x1a8ca48)
        # A player can report its destination area before the previous load
        # has finished consuming the manager's request. Do not issue a second
        # fixture warp in that handoff (the first loader can erase it).
        deadline=time.monotonic()+12;stable=None
        while time.monotonic()<deadline:
            # Quick-hunt's first camp keeps the current area in this byte;
            # later loads use255. Both are settled when no load is pending.
            ready=self.read(area+0x4a,'<B') in (255,self.read(self.actor+0x1054,'<B')) and not self.read(stage+420)&2
            if ready:
                if stable is None:stable=time.monotonic()
                if time.monotonic()-stable>=.5:break
            else:stable=None
            time.sleep(.025)
        else:raise TimeoutError('Previous native area request did not settle')
        if self.state()['area']==zone:return
        data=self.read(stage+904+zone*4);point=self.read(self.read(data+0xd8))
        spawn=self.read(point+0x20,'<B')
        self.fixture_bytes(area+0x4a,zone,'<B');self.fixture_bytes(area+0x51,spawn,'<B')
        self.fixture_bytes(stage+420,self.read(stage+420)|2)
        deadline=time.monotonic()+25;stable=None;wake=0
        while time.monotonic()<deadline:
            s=self.state()
            ready=(s['area']==zone and s['state']==1 and s['action']<=5 and
                   self.read(area+0x4a,'<B') in (255,zone) and not self.read(stage+420)&2)
            if ready:
                if stable is None:stable=time.monotonic()
                if time.monotonic()-stable>=.5:return
            else:stable=None
            # Native KO can legitimately survive a zone load (the armor
            # negative control deliberately accumulates enough to stun).
            # Recover with ordinary input instead of calling a load failure.
            if s['state']==64 and s['frame']>60 and time.monotonic()>wake:
                self.command('B 8');wake=time.monotonic()+.6
            time.sleep(.05)
        raise TimeoutError(('Native area transition did not finish',zone,s))
    def close(self):
        self.k.CloseHandle(self.h);self.k.ReleaseMutex(self.mutex);self.k.CloseHandle(self.mutex)

if __name__=='__main__':
    f=Fixture()
    try:
        if len(sys.argv)>1:f.command('\n'.join(sys.argv[1:]));time.sleep(.25)
        print(json.dumps(f.state(),indent=2))
    finally:f.close()
