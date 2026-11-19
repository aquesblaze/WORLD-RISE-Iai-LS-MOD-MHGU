"""Repeated raw early-R inputs, including recovery after short solo R."""
import sys,time,json
from pathlib import Path
from pc_fixture import Fixture
from animation_port import sha
f=Fixture();cases=[]
def sample():
 s=f.state();pad=f.read(0x2326888);idx=f.read(pad+0x6b60,'<i')
 s['raw_pad']=f.read(pad+idx*0xb50+0x1d0) if 0<=idx<=8 else None
 s['coherent']=(s['motion'],s['frame'],s['action'])==(f.read(f.actor+0x4b4,'<H'),f.read(f.actor+0x500,'<f'),f.read(f.actor+0x250a,'<H'))
 return s
def wait(pred,rows=None,seconds=10):
 end=time.monotonic()+seconds
 while time.monotonic()<end:
  s=sample()
  if rows is not None:rows.append(s)
  if s['coherent'] and pred(s):return s
  time.sleep(.004)
 raise TimeoutError(s)
def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
try:
 for i in range(8):
  f.camp_station()
  if not f.read(f.actor+0x2749,'<B')&1:f.command('X 8');time.sleep(2);idle()
  f.fixture_bytes(f.actor+0x2780,100);time.sleep(.2)
  if i%2:
   f.command('A 8');wait(lambda s:s['action']==4 and s['motion']==0x569 and s['frame']>=60)
   f.command('R 2');wait(lambda s:s['state']==16 and 16<=s['action']<154);idle()
   f.fixture_bytes(f.actor+0x2780,100);time.sleep(.2)
  rows=[];f.command('A 8');pressed=wait(lambda s:s['action']==4 and s['motion']==0x569 and s['frame']>=20,rows)
  f.command('R 30');ok=True
  try:after=wait(lambda s:s['state']==16 and 16<=s['action']<154,rows)
  except TimeoutError:after=rows[-1];ok=False
  cases.append({'case':i,'after_short_R':bool(i%2),'pressed':pressed,'after':after,'passed':ok,'rows':rows})
  print(i,ok,'pressed',round(pressed['frame'],3),'action',after['action'],flush=True)
  idle()
finally:
 report={'status':'PASS_EARLY_R_REPEATED'if len(cases)==8 and all(c['passed']for c in cases)else 'FAIL','run':str(f.run),'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),'cases':cases}
 (f.run/'early_r_repeated.json').write_text(json.dumps(report,indent=2));f.close()
print(report['status'])
if report['status']=='FAIL':raise SystemExit(1)
