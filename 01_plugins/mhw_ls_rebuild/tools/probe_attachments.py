"""Record raw channels; interpreted native selector evidence is kept separately."""
import json
import animation_port as p


def main():
    skeleton=p.read_skeleton(p.WORLD_MODEL,True)
    actions={a.id:a for a in p.read_lmt_file(p.WORLD).actions}
    report={'status':'raw channel archive; see attachment_rules.json and world_attachment_native.json for native selector semantics',
            'source_sha256':p.sha(p.WORLD),'function_ids':[30,47],'clips':[]}
    for clip,_,name in p.CLIPS[:11]:
        action=actions[clip]
        curves={(t.header.bone_id,t.header.usage):p.compile_pose_curve(t)
                for t in action.tracks if t.header.bone_id in (30,47)}
        channels=[]
        for bone in (30,47):
            modes=[];last=None
            for f in range(action.header.frame_count):
                value=curves[bone,2].sample(f)
                if value!=last:modes.append([f,list(value)]);last=value
            frames=sorted(set([0,min(10,action.header.frame_count-1),min(30,action.header.frame_count-1),
                               action.header.frame_count//2,action.header.frame_count-1]))
            samples=[{'frame':f,'translation':curves[bone,1].sample(f),
                      'rotation_wxyz':curves[bone,0].sample(f)} for f in frames]
            channels.append({'function':bone,
                'model_parent_function':skeleton.functions[skeleton.parents[skeleton.mapping[bone]]],
                'raw_scale_transitions':modes,'samples':samples})
        report['clips'].append({'world_clip':clip,'name_candidate':name,'channels':channels})
    report['next_validation']=('Native selector established separately: scale Y 2/main, 3/sub, 4/either. '
        'Do not use these flags as geometric scale. Model-origin corrections, '
        'native weapon motion transitions and full visual validation remain separate work.')
    path=p.PROJECT/'research/attachment_probe.json'
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print('Recorded attachment candidates for',len(report['clips']),'clips')


if __name__=='__main__':main()
