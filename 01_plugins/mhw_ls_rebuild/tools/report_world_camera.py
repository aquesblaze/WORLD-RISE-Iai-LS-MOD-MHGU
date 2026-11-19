"""Assert camera requests and visible native view direction from a real Iai hit."""
import argparse,hashlib,json,math,re
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('record',type=Path);args=ap.parse_args()
    d=json.loads(args.record.read_text());rows=d['rows'];events=d['camera_events']
    requests=[[int(v,16) for v in re.search(r'world_camera_request (\w+) (\w+) (\w+) (\w+)',e).groups()]
              for e in events if 'world_camera_request ' in e]
    hp=[next(e['hp'] for e in s['enemies'] if e['actor']==d['target']) for s in rows]
    camera=[s['camera'] for s in rows if 'camera' in s]
    assert camera,'No native camera observations'
    if d['whiff_fixture']:
        assert not requests and hp[0]==hp[-1],('Whiff moved camera or hit',requests,hp[0],hp[-1])
    else:
        assert hp[-1]<hp[0],('No native damage contact',hp[0],hp[-1])
        assert [r[1] for r in requests]==[0,1],requests
        # Source reset-time is linear0:.7 ->37:.4 and is sampled at the
        # consumed frame, not nominal20. A variable simulation step can
        # legitimately cross20 at22.4; the former fixed.52 floor rejected it.
        active=[s for s in rows if s['action']==248 and s['motion']in(0x5ef,0x5f0,0x5f1,0x5f5)]
        step=max(s['dt']for s in active)*(1.5 if d['rank_fixture']==0 else 2)
        consumed=(.7-requests[0][3]/1e6)*37/.3
        observed=[s['frame']for s in active if 20<=s['frame']<37]
        assert observed and 20-.001<=consumed<=20+step+.01,(consumed,step)
        assert min(abs(f-consumed)for f in observed)<=step+.01,(consumed,observed)
        assert abs(requests[1][3]-400000)<=1,requests
        end=camera[-1];assert abs(((end['angles'][0]+32768)&65535)-32768+546)<=1,end
        assert abs(((end['angles'][1]-requests[-1][2]+32768)&65535)-32768)<=1,end
        dx,dy,dz=[b-a for a,b in zip(end['eye'],end['look_at'])]
        pitch=math.degrees(math.atan2(-dy,math.hypot(dx,dz)))
        yaw=math.degrees(math.atan2(dx,dz))%360
        target_view=((requests[-1][2]+32768)&65535)*360/65536
        assert abs(pitch-3)<.15,(pitch,end)
        assert abs((yaw-target_view+180)%360-180)<.15,(yaw,target_view,end)
    out={'status':'PASS_NATIVE_CAMERA_WHIFF' if d['whiff_fixture'] else 'PASS_NATIVE_CAMERA_CONTACT',
         'source_record':str(args.record.resolve()),'source_sha256':hashlib.sha256(args.record.read_bytes()).hexdigest(),
         'plugin_sha256':d['plugin_sha256'],'rank':d['rank_fixture'],'requests':requests,
         'native_damage':hp[0]-hp[-1],'camera_samples':len(camera),
         'limits':'Validates real contact triggers and native eye/look direction. GU posed bones adapt the source main-bone candidates; camera obstruction and multi-target cases remain separate.'}
    args.record.with_name(args.record.stem+'_camera_report.json').write_text(json.dumps(out,indent=2))
    print(out['status'],'rank',out['rank'],'damage',out['native_damage'],'requests',requests)

if __name__=='__main__':main()
