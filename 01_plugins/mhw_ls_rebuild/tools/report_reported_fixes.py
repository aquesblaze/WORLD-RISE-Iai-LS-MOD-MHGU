"""Accept recorded output, advancing blended poses, sheath restoration and pad timing."""
import json,math
from pathlib import Path
from animation_port import ROOT,PROJECT,sha

def main():
    run=Path(json.loads((ROOT/'.cache/mhw_ls_combat/active_session.json').read_text())['run'])
    d=json.loads((run/'reported_motion_audio.json').read_text())
    audio=json.loads((run/'reported_audio_correlation.json').read_text())
    inputs=json.loads((run/'input_feel.json').read_text())
    plugin=sha(run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro')
    bank=sha(run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_audio.arc')
    assert plugin==d['plugin_sha256']==inputs['plugin_sha256']
    assert bank==d['audio_arc_sha256']
    assert inputs['status'].startswith('PASS')
    assert any(c['name']=='early_R_waits_during_recovery_not_after_it' for c in inputs['cases'])
    assert 0<d['audio_peak']<.98
    assert {x['media']for x in audio}=={12607224,83129473,196974904,1045293969}
    for row in audio:
        assert max(x['correlation']for x in row['channels'])>.1,row
        assert all(x['gain']>0 for x in row['channels']),row
    for pair in (audio[:2],audio[2:]):
        times=[max(row['channels'],key=lambda x:x['correlation'])['time']for row in pair]
        assert abs(times[0]-times[1])<.003,times
    moves=[]
    for motion in (0x5ef,0x5f5):
        rows=[x for x in d['samples']if x['motion']==motion and x.get('coherent')]
        assert rows and max(x['frame']for x in rows)>170,'Interrupted Iai is not acceptance'
        # The remaining blend is sampled AFTER this update, while FRAME is
        # the update's entry clock. One long simulation step can finish the
        # blend. Check consecutive distinct states, not only simultaneous
        # positive FRAME/remaining values; do not collapse held-frame states.
        transition_states=[]
        for x in rows:
            if not transition_states or (x['frame'],x['blend_remaining'])!=(transition_states[-1]['frame'],transition_states[-1]['blend_remaining']):
                transition_states.append(x)
        blended=[b for a,b in zip(transition_states,transition_states[1:])
                 if a['blend_remaining']>0 and b['frame']>a['frame']]
        assert blended,'Pose interpolation must not freeze the destination clock'
        unique=[]
        for x in rows:
            if not unique or unique[-1]['frame']!=x['frame']:unique.append(x)
        assert all(b['frame']>a['frame'] for a,b in zip(unique,unique[1:]))
        moving=[(a,b)for a,b in zip(unique,unique[1:])if 12<a['frame']<60]
        unchanged=sum(a['bones']==b['bones'] for a,b in moving)
        assert len(moving)>=8 and unchanged==0,(motion,len(moving),unchanged)
        moves.append({'motion':motion,'unique_frames':len(unique),'last_frame':unique[-1]['frame'],
                      'blend_advances_at_frame':blended[0]['frame'],'moving_pose_intervals':len(moving),
                      'unchanged_pose_intervals':unchanged,'max_simulation_step':max(x['dt']for x in rows)})
    # FRAME is published before native attachment evaluation. Even a stable
    # clock can therefore expose the old hand pose during that update. Use
    # the last coherent sample of each completed clock interval, without
    # filtering on joint/pose or discarding the raw transition observations.
    completed=[];last=None
    for x in d['samples']:
        if not x.get('coherent'):continue
        if last is not None and (last['motion'],last['frame'])!=(x['motion'],x['frame']):
            completed.append(last)
        last=x
    exits=[x for x in completed if x['motion']==0x5f6 and 34<=x['frame']<50]
    assert len(exits)>2
    for x in exits:
        assert x['weapon']['joint']==2
        assert math.dist(x['weapon']['pose'][:3],[10,0,58])<.001
    report={'status':'PASS_REPORTED_INPUT_AUDIO_MOTION_FIXTURES','run':str(run),'plugin_sha256':plugin,
            'audio_arc_sha256':bank,'output_device':d['device']['name'],'recording':str(run/'reported_loopback.wav'),
            'recording_sha256':sha(run/'reported_loopback.wav'),'audio_peak':d['audio_peak'],
            'source_audio_matches':audio,'moves':moves,'timeout_native_back_pose_samples':len(exits),
            'input_report_sha256':sha(run/'input_feel.json'),
            'limits':'Rank0/red Iai on copied-save surveyed camp fixture, current equipped weapon. PCM correlation proves original source media reached the selected output; it does not establish equal World mixing. Advancing clocks and bone matrices do not alone establish full visual equivalence.'}
    for p in (run/'reported_fixes.json',PROJECT/'research/world_reported_fixes_validation.json'):
        p.write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],d['device']['name'],'peak',round(d['audio_peak'],4))

if __name__=='__main__':main()
