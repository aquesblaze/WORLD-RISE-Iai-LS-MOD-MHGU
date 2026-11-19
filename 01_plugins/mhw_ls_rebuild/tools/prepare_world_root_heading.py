"""Export World root rotation for the actor-heading adapter.

Native World open-floor traces show actor forward following usage3. GU's
bone matrices were instead equal to the body-local pose at fixed heading.
Keep original T/Q in the LMT and apply usage3 to actor heading, which also
cancels GU's inverse-root translation transform without modifying the path.
"""
import json
import math
import numpy as np
import animation_port as p

def main():
    wanted={c for c,_,_ in p.CLIPS};profiles=[];angles=[]
    for action in p.read_lmt_file(p.WORLD).actions:
        if action.id not in wanted:continue
        root=next((t for t in action.tracks if t.header.bone_id==-1 and t.header.usage==3),None)
        if not root:continue
        curve=p.compile_pose_curve(root)
        values=[]
        for f in range(action.header.frame_count):
            m=p.quat_matrix(curve.sample(f))
            if not np.allclose(m[1],(0,1,0),atol=2e-4):raise ValueError('Non-yaw root needs a full orientation adapter')
            values.append(math.atan2(m[0,2],m[2,2]))
        values=np.unwrap(values)*(65536/(2*math.pi))
        if np.max(np.abs(values))<.001:continue
        profiles.append((action.id,len(angles),len(values)));angles.extend(values)
    header='/* Generated from original World usage3, heading units per turn=65536. */\n#pragma once\n'
    header+='typedef struct {unsigned source,offset,count;} WRootTrack;\nstatic const WRootTrack world_root_tracks[]={\n'
    header+=''.join(' {'+','.join(map(str,r))+'},\n'for r in profiles)+'};\n'
    header+='static const float world_root_angles[]={\n'
    header+=''.join(' '+format(float(v),'.9f')+'f,\n'for v in angles)+'};\n'
    (p.PROJECT/'c/world_roots.h').write_text(header,encoding='ascii')
    (p.PROJECT/'research/world_root_heading_source.json').write_text(json.dumps({
        'world_lmt_sha256':p.sha(p.WORLD),'tracks':[{'source':r[0],'frames':r[2]}for r in profiles],
        'gu_baseline':'native bone0 matrices track body-local pose without usage3 rotation; heading remains fixed',
        'world_reference':'open-floor source308 trace; actor forward rotates through the authored half turn',
        'rule':'Original root T/Q plus entry-heading+usage3 yaw; no baked translation pre-rotation',
        'status':'CANDIDATE_REQUIRES_NATIVE_GU_POSE_AND_TRAJECTORY_CHECK'},indent=2)+'\n')
    print(profiles)

if __name__=='__main__':main()
