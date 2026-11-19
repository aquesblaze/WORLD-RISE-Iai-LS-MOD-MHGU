"""Compare native World forward, GU posed pelvis, and source root curves."""
import argparse
import json
import math
import numpy as np
import animation_port as p

def angle(matrix):
    return math.degrees(math.acos(float(np.clip((np.trace(matrix)-1)/2,-1,1))))

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--world',type=p.Path,required=True)
    ap.add_argument('--gu',type=p.Path,required=True);args=ap.parse_args()
    world=json.loads(args.world.read_text());gu=json.loads(args.gu.read_text())
    wr=[r for r in world['rows']if r['motion']==308]
    source=gu.get('source_clip',308);slot={308:239,309:240,310:241,311:245}[source]
    gr=[r for r in gu['rows']if r['action']==248 and r['motion']==0x500+slot]
    assert wr and gr
    a=next(a for a in p.read_lmt_file(p.WORLD).actions if a.id==source)
    root=p.compile_pose_curve(next(t for t in a.tracks if t.header.bone_id==-1 and t.header.usage==3))
    translation=p.compile_pose_curve(next(t for t in a.tracks if t.header.bone_id==-1 and t.header.usage==4))
    src=p.read_skeleton(p.WORLD_MODEL,True);dst=p.read_skeleton(p.GU_MODEL,False)
    pose,base=p.source_pose(a,src)
    entry=gr[0]['heading']*(2*math.pi/65536)
    heading=np.array([[math.cos(entry),0,math.sin(entry)],[0,1,0],[-math.sin(entry),0,math.cos(entry)]])
    pelvis_errors=[];lateral=[];path_errors=[]
    for r in gr:
        f=r['frame']
        if f<23:continue # entry pose blend is deliberately a separate check
        actual=np.array(r['bones']['0']).reshape(4,4).T[:3,:3]
        actual/=np.linalg.norm(actual,axis=0)
        local=p.quat_matrix(p.sample_body(pose,base,src,dst,f)[0,0])
        expected=heading@p.quat_matrix(root.sample(f))@local
        pelvis_errors.append(angle(actual.T@expected))
        displacement=heading.T@(np.array(r['position'])-gr[0]['position'])
        lateral.append(abs(displacement[0]))
        expected_translation=np.array(translation.sample(f))-translation.sample(gr[0]['frame'])
        path_errors.append(float(np.linalg.norm((displacement-expected_translation)[[0,2]])))
    world_heading=math.atan2(wr[0]['forward'][0],wr[0]['forward'][2])
    forward_errors=[]
    for r in wr:
        q=p.quat_matrix(root.sample(r['frame']));yaw=math.atan2(q[0,2],q[2,2])
        observed=math.atan2(r['forward'][0],r['forward'][2])
        forward_errors.append(abs(math.degrees(math.atan2(math.sin(observed-world_heading-yaw),math.cos(observed-world_heading-yaw)))))
    final=heading.T@(np.array(gr[-1]['position'])-gr[0]['position'])
    endpoint=p.np.array(translation.sample(gr[-1]['frame']))
    report={'status':'POSE_AND_HORIZONTAL_ROOT_CURVE_MATCH' if max(path_errors)<.1 and max(pelvis_errors)<.06 else 'ROOT_CONTRACT_MISMATCH',
        'world_record':str(args.world),'gu_record':str(args.gu),
        'world_record_sha256':p.sha(args.world),'gu_record_sha256':p.sha(args.gu),
        'plugin_sha256':gu['plugin_sha256'],'source_clip':source,'world_runtime_reference_clip':308,
        'world_actor_forward_error_degrees':max(forward_errors),
        'gu_posed_pelvis_error_degrees':{'max':max(pelvis_errors),'mean':float(np.mean(pelvis_errors))},
        'gu_horizontal_entry_space_endpoint':final[[0,2]].tolist(),
        'source_horizontal_endpoint':endpoint[[0,2]].tolist(),
        'gu_max_lateral_units':max(lateral),
        'gu_horizontal_source_curve_error_units':{'max':max(path_errors),'mean':float(np.mean(path_errors))},
        'limits':'World trace on open training floor; GU on surveyed camp floor. Pelvis rotation and horizontal root curve after entry blend only. Authored lateral movement is retained. Floor/entry blend, the full ground FSM and effects need separate validation.'}
    (p.PROJECT/f'research/world_iai_root_contract_comparison_{source}.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()
