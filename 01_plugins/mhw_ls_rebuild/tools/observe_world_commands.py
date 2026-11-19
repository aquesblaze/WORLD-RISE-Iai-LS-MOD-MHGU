"""Read-only native command-state trace for the configured World reference.

Resolve command objects through their actual DTI vtables and live player/
controller backlinks. Never write or inject into the reference process.
"""
import argparse,json,struct,time,sys
from observe_world_camera import WorldCamera,ROOT,BASE,Region
sys.path.insert(0,str(ROOT/'.cache/mhw_anim_tools_core'))
from inspect_world_actions import resolve
import ctypes as C

class WorldCommands(WorldCamera):
    def __init__(self,pid):
        super().__init__(pid)
        cache=ROOT/'.cache/mhw_game_input/command_pointer.json'
        old=json.loads(cache.read_text())if cache.exists()else{}
        prior=old.get('objects',[])if old.get('pid')==pid and old.get('owner')==self.owner else[]
        self.objects=prior if old.get('version')==2 else[]
        names=['cCommand','cWp03Iaigiri','cActCommand','cActCommandDownToUp']
        self.vtables={BASE+r['vtable']for r in resolve(['nHmTransition::'+n for n in names]).values()}
        if not self.objects or not all(self.valid_command(v)for v in self.objects):
            if prior:self.objects=self.scan_range(max(0,min(prior)-2*1024*1024),max(prior)+2*1024*1024)
            ids={self.read(v+0x28,'<I')for v in self.objects}
            if not {25,32,39}<=ids:self.objects=self.locate_commands()
        controllers={self.read(v+0x20,'<Q')for v in self.objects}
        if len(controllers)!=1:raise ValueError(('Expected one owned controller',controllers))
        self.controller=controllers.pop()
        cache.write_text(json.dumps({'pid':pid,'owner':self.owner,'objects':self.objects,'version':2}))
    def valid_command(self,at):
        try:
            return self.read(at,'<Q')in self.vtables and self.read(at+0x10,'<Q')==self.owner and \
                self.read(self.read(at+0x20,'<Q')+0x30,'<Q')==self.owner and 0<=self.read(at+0x28,'<I')<137
        except ValueError:return False
    def locate_commands(self):
        needles=[struct.pack('<Q',v)for v in self.vtables];found=[];at=0;deadline=time.monotonic()+45
        while at<0x7fffffff0000 and time.monotonic()<deadline:
            region=Region()
            if not self.k.VirtualQueryEx(self.h,at,C.byref(region),C.sizeof(region)):break
            top=(region.base or 0)+region.size
            if top<=at:break
            if region.state==0x1000 and region.kind==0x20000 and not region.protect&0x101:
                for start in range(region.base,top,4*1024*1024):
                    if time.monotonic()>=deadline:break
                    blob=self.raw(start,min(4*1024*1024+7,top-start))
                    for needle in needles:
                        p=blob.find(needle)
                        while p>=0:
                            if self.valid_command(start+p):found.append(start+p)
                            p=blob.find(needle,p+8)
            at=top
        if not found:raise ValueError('No owner-validated native command object')
        return sorted(set(found))
    def scan_range(self,start,end):
        found=[]
        for at in range(start,end,65536):
            blob=self.raw(at,min(65536+7,end-at))
            for vt in self.vtables:
                needle=struct.pack('<Q',vt);p=blob.find(needle)
                while p>=0:
                    if self.valid_command(at+p):found.append(at+p)
                    p=blob.find(needle,p+8)
        return sorted(set(found))
    def command_sample(self):
        if not all(self.valid_command(v)for v in self.objects):raise ValueError('Command owner changed')
        c=self.controller;a=self.owner;component=self.read(a+0x468,'<Q')+0xb0
        primary=self.read(a+0xe480,'<Q')
        return {'time':time.monotonic(),'motion':self.read(component+10,'<H')&511,
            'frame':self.read(component+0x5c,'<f'),
            'last_frame':self.read(component+0x64,'<f'),
            'primary_input':self.read(primary+8,'<8I'),
            'query_flags':[{ 'id':self.read(v+0x28,'<I'),'flags':self.read(v+8,'<B'),
                            'mode':self.read(v+0x30,'<B')}for v in self.objects],
            'commands':{name:self.read(c+offset,'<5I')for name,offset in
                [('observed',0x780),('raw',0x7a0),('executable',0x7c0),('raw_executable',0x7e0),
                 ('buffered',0x800),('secondary',0x820),('secondary_buffered',0x840),
                 ('tested',0x860),('other',0x880),('queried',0x8a0),('previous_queries',0x8c0)]},
            'buttons':{name:self.raw(c+offset,40).hex()for name,offset in
                [('X',0x138),('A',0x160),('R',0x188),('B',0x98)]},
            'direction':self.read(c+0x9b0,'<3I'),'lifecycle':self.raw(c+0x9e0,9).hex()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--pid',type=int,required=True)
    ap.add_argument('--seconds',type=float,default=0);ap.add_argument('--tag',default='commands');args=ap.parse_args()
    assert 0<=args.seconds<=30 and args.tag.replace('_','').isalnum()
    c=WorldCommands(args.pid)
    try:
        rows=[];end=time.monotonic()+args.seconds
        while True:
            rows.append(c.command_sample())
            if time.monotonic()>=end:break
            time.sleep(.004)
        path=ROOT/'.cache/mhw_game_input'/f'{args.tag}_{time.time_ns()}.json'
        path.write_text(json.dumps({'pid':args.pid,'owner':c.owner,'controller':c.controller,
            'read_only':True,'source_build':421810,'rows':rows},indent=2))
        wanted={17,24,25,32,39,46,51,52,53,60}
        print(path);print(json.dumps({'objects':len(c.objects),'query_flags':[r for r in rows[-1]['query_flags']if r['id']in wanted]}))
    finally:c.close()

if __name__=='__main__':main()
