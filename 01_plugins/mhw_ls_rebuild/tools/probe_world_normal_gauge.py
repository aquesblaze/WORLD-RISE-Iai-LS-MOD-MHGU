"""Pad-driven ordinary overhead contacts; position/resources/monster idle are fixture setup."""
import argparse,json,time,hashlib,re
from pc_fixture import Fixture

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--label',default='boost');args=ap.parse_args()
 f=Fixture();a=f.actor;rows=[]
 def wait(test,seconds=12):
  end=time.monotonic()+seconds
  while time.monotonic()<end:
   f.command('emact 2 5 1');s=f.state()
   if test(s):return s
   time.sleep(.025)
  raise TimeoutError(s)
 try:
  for _ in range(4):
   e=next(e for e in f.state()['enemies'] if e['uid']==0);f.command('emact 2 5 1');f.warp(e['area']);s=f.state()
   e=next(e for e in s['enemies'] if e['uid']==0)
   if e['area']==s['area']:break
  target=e['actor'];station={2:(-1500.,0.,-1000.),5:(-1000.,-30.,1600.),6:(-2000.,-22.5,-3400.),7:(0.,0.,0.)}.get(s['area'],e['position'])
  for owner in (target,f.read(target+0x1428)):
   for off,v in zip((0x40,0x44,0x48),station):f.fixture_bytes(owner+off,v,'<f')
  for other in s['enemies']:
   if other['actor']!=target and other['area']==s['area']:f.fixture_bytes(other['actor']+0x17b0,0)
  f.fixture_bytes(target+0x17b0,3000);f.fixture_bytes(target+0x17b4,3000);f.fixture_bytes(a+0x13d6,100,'<h')
  for off,v in zip((0x40,0x44,0x48),(station[0],station[1],station[2]+700)):f.fixture_bytes(a+off,v,'<f')
  wait(lambda s:s['state']==1 and s['action']<=5)
  if not f.read(a+0x2749,'<B')&1:f.command('X 8');time.sleep(2)
  wait(lambda s:s['state']==1 and s['action']<=5 and s['motion']==0x501)
  f.fixture_bytes(a+0x3330,0)
  log_start=(f.run/'log.txt').stat().st_size
  for i in range(10):
   wait(lambda s:s['state']==1 and s['action']<=5);time.sleep(.25)
   for off,v in zip((0x40,0x44,0x48),(station[0],station[1],station[2]-150)):f.fixture_bytes(a+off,v,'<f')
   f.fixture_bytes(a+0xfec,0);f.fixture_bytes(a+0x14a0,0)
   initial=95 if i==8 else 100 if i==9 else 0
   f.fixture_bytes(a+0x2780,initial);f.fixture_bytes(a+0x3334,0.,'<f');time.sleep(.1)
   before=f.read(target+0x17b0);f.command('X 8')
   end=time.monotonic()+5
   while time.monotonic()<end:
    f.command('emact 2 5 1');contact=f.state()
    if f.read(target+0x17b0)<before:break
    if contact['state']==16 and contact['action']<=14 and contact['frame']<45:
     for off,v in zip((0x40,0x44,0x48),(station[0],station[1],station[2]-150)):f.fixture_bytes(a+off,v,'<f')
     f.fixture_bytes(a+0xfec,0);f.fixture_bytes(a+0x14a0,0)
    time.sleep(.01)
   else:raise TimeoutError(('No ordinary thrust contact',contact))
   assert contact['state']==16 and contact['action']<=14 and contact['motion'] in (0x565,0x566),contact
   time.sleep(.1)
   row=dict(index=i,initial=initial,gauge=f.state()['gauge'],damage=before-f.read(target+0x17b0),frame=contact['frame'])
   rows.append(row);print(row,flush=True)
  total=sum(r['gauge'] for r in rows);result=dict(status='OBSERVED_NATIVE_CONTACTS',rows=rows,total=total,station_fixture=station,monster_idle_fixture=True,position_and_gauge_reset_between_hits=True,plugin_sha256=hashlib.sha256((f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro').read_bytes()).hexdigest())
  with (f.run/'log.txt').open('rb') as log:log.seek(log_start);events=log.read().decode('utf8',errors='replace')
  gains=[tuple(int(v,16) for v in m) for m in re.findall(r'world_normal_gain '+f'{a:08X}'+r' (\w+) (\w+) (\w+)',events)]
  assert len(gains)==10,gains
  raw=sum(x[0] for x in gains[:8]);boost=sum(x[1] for x in gains[:8])
  assert boost==raw*11//10,(raw,boost,gains)
  assert rows[8]['gauge']==100 and rows[9]['gauge']==100,rows[-2:]
  assert all((x[2]&65535)<=100 for x in gains)
  result.update(status='PASS_NORMAL_GAUGE_1_1',base_gain_total=raw,boosted_gain_total=boost,native_gain_events=gains,contact_position_pinned_until_frame45_fixture=True)
  (f.run/f'normal_gauge_{args.label}.json').write_text(json.dumps(result,indent=2));print(result['status'],total,flush=True)
  f.warp(0)
 finally:f.close()
if __name__=='__main__':main()
