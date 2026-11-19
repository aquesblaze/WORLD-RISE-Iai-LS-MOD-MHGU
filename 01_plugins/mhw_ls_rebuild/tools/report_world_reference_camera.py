"""Cross-check source camera semantics against read-only training telemetry."""
import argparse,hashlib,json,math
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('turn',type=Path);ap.add_argument('scalars',type=Path)
    args=ap.parse_args();turn=json.loads(args.turn.read_text())['rows'];rows=json.loads(args.scalars.read_text())['rows']
    values=[];last=None
    for s in rows:
        x=s['common_camera_duration']
        if x!=last and x<.6999:values.append(x)
        last=x
    # This observed source no-color clip308 was sampled at60simulation Hz.
    # Linear speed1->1.5->1 drives linear reset-time. The compounded sequence
    # sharply distinguishes continuous speed from the old stepped adapter.
    frame=0;errors=[]
    for x in values:
        frame+=1+.5*frame/23 if frame<23 else max(1,1.5-.5*(frame-23)/17)
        errors.append(abs(x-(.7-.3*min(frame,37)/37)))
    assert len(values)==30 and max(errors)<.00001,(len(values),max(errors))
    easing=[]
    for s in turn:
        clock,duration=s['clock_duration']
        if duration<=.1 or not .04<clock<.2:continue
        t=min(max((clock-1/60)/duration,0),1);q=1-(1-t)**4
        easing.append(max(abs((s['start'][k]+((s['target'][k]-s['start'][k]+180)%360-180)*q-s['angles'][k]+180)%360-180) for k in (0,1)))
    assert len(easing)>10 and max(easing)<.001,(len(easing),max(easing))
    s=rows[-1];dx,dy,dz=[b-a for a,b in zip(s['eye'],s['look_at'])]
    pitch=math.degrees(math.atan2(-dy,math.hypot(dx,dz)));yaw=math.degrees(math.atan2(dx,dz))
    assert abs(pitch-3)<.001 and abs((yaw-s['angles'][1]+180)%360-180)<.001
    report={'status':'PASS_READ_ONLY_SOURCE_CAMERA_AND_FLOAT_CURVES','source_build':'World421810/15.23',
            'records':{str(p.resolve()):hashlib.sha256(p.read_bytes()).hexdigest() for p in (args.turn,args.scalars)},
            'scalar_samples':len(values),'max_scalar_error':max(errors),'max_quartic_error_degrees':max(easing),
            'clock_order':'Evaluate using current elapsed clock, then add simulation dt.',
            'pitch_degrees_from_eye_and_look':pitch,'yaw_degrees_from_eye_and_look':yaw,
            'typed_TIML':'The local reader display labels are off by one: raw1 holds, raw2 linearly interpolates. Motion speed and camera reset time are both raw2; AIR turn speed is raw1.',
            'limits':'One local no-color Iai training clip,60Hz. No source incoming-attack timing or complete port acceptance.'}
    out=Path(__file__).resolve().parents[1]/'research/world_camera_observation.json'
    out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(report['status'],max(errors),max(easing))

if __name__=='__main__':main()
