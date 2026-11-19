"""Bake local attachment candidates for the isolated body playback build.

Native World 421810 evidence: RVA 0x210d360 scans usage-2 records in file order.
Main weapon requests scale Y ~= 2, sub weapon ~= 3; ~= 4 serves either role.
It samples the integer animation frame and returns 2 for function30, 1 for47.
RVA 0x210b8f0 then reads that joint's matrix and normalizes its basis axes.
The EVWP/weapon-origin correction is NOT yet reproduced by this experiment.
No generated game animation arrays are written into the source repository.
"""
import json
import math
import struct
import argparse
import animation_port as p


def select_function(action, frame, role):
    if role not in (9, 10) or not math.isfinite(frame) or frame < 0:
        raise ValueError('Invalid attachment sample')
    target = 2.0 if role == 9 else 3.0
    for track in action.tracks:
        h = track.header
        if h.usage != 2 or h.bone_id not in (30, 47):
            continue
        y = p.compile_pose_curve(track).sample(int(frame))[1]
        if target - .1 < y < target + .1 or 3.9 < y < 4.1:
            return h.bone_id
    return None


def weapon_motion_keys(raw, action):
    tracks = [t['keys'] for event in p.timeline(raw, action)
              if event['type'] == 'PlMotionCommon' for t in event['tracks']
              if t['name'] == 'mWeaponMotionNo']
    if len(tracks) > 1:
        raise ValueError('Ambiguous weapon motion event track')
    return tracks[0] if tracks else []


def weapon_motion_at(keys, frame):
    value = -1
    for at, candidate in keys:
        if at > frame:
            break
        value = int(candidate)
    return value


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--ground',action='store_true');args=ap.parse_args()
    raw = p.WORLD.read_bytes()
    actions = {a.id: a for a in p.read_lmt_file(p.WORLD).actions}
    skeleton = p.read_skeleton(p.WORLD_MODEL, True)
    samples = []; records = []; selections = []; evidence = []; weapon_motions = []; weapon_ages = []
    clips=p.CLIPS
    if args.ground:
        from prepare_ground_motion_bank import source_actions
        sources=source_actions()
        plan=json.loads((p.PROJECT/'research/world_ground_motion_plan.json').read_text(encoding='utf8'))
        clips=[(r['world_clip'],r['gu_slot'],'ground')for r in plan['clips']]
    for world, slot, name in clips:
        if args.ground:
            action,path=sources[world];actions[world]=action;raw=path.read_bytes()
        a = actions[world]; offset = len(samples)
        curves = {(t.header.bone_id, t.header.usage):p.compile_pose_curve(t)
                  for t in a.tracks if t.header.bone_id in (30, 47)}
        changes=[]; last=None; weapon_keys=weapon_motion_keys(raw,a)
        for frame in range(a.header.frame_count):
            row=[]
            for function in (30, 47):
                parent=skeleton.functions[skeleton.parents[skeleton.mapping[function]]]
                if parent != (8 if function == 30 else 12):
                    raise ValueError('Unexpected source equipment parent')
                if (function,0) in curves and (function,1) in curves:
                    q=curves[function,0].sample(frame)
                    row.extend((*curves[function,1].sample(frame),*q[1:],q[0]))
                else:
                    # Common holster clips can omit a constant equipment
                    # channel. Its owning joint retains the model rest pose.
                    local=skeleton.local[skeleton.mapping[function]]
                    q=p.matrix_quat(local[:3,:3])
                    row.extend((*local[:3,3],*q[1:],q[0]))
            samples.append(row)
            chosen=[select_function(a,frame,role) for role in (9,10)]
            selections.append([0 if f is None else 1 if f==30 else 2 for f in chosen])
            weapon_motions.append(weapon_motion_at(weapon_keys,frame))
            last_key=max((at for at,_ in weapon_keys if at<=frame),default=frame)
            weapon_ages.append(int(frame-last_key))
            if chosen != last:changes.append({'frame':frame,'functions':chosen});last=chosen
        records.append((slot,a.header.frame_count,offset))
        evidence.append({'world_clip':world,'slot':slot,'selection_changes':changes,
                         'source_weapon_motion_keys':weapon_keys})
    lines=['/* Generated local game data: preview only. Do not distribute. */',
           'typedef struct {unsigned slot,frames,offset;} MLAttachmentClip;',
           'static const MLAttachmentClip ml_attachment_clips[]={']
    lines += ['{%d,%d,%d},'%r for r in records];lines += ['};', 'static const float ml_attachment_samples[][14]={']
    def cfloat(v):
        if not math.isfinite(v):raise ValueError('Nonfinite source sample')
        text=format(struct.unpack('<f',struct.pack('<f',v))[0],'.9g')
        if not any(c in text for c in '.eE'):text+='.'
        return text+'f'
    lines += ['{'+','.join(cfloat(v) for v in row)+'},' for row in samples]
    lines += ['};','static const unsigned char ml_attachment_selection[][2]={']
    lines += ['{%d,%d},'%tuple(row) for row in selections];lines+=['};']
    lines += ['static const signed char ml_attachment_weapon_motion[]={',
              ','.join(map(str,weapon_motions)), '};']
    lines += ['static const unsigned short ml_attachment_weapon_age[]={',
              ','.join(map(str,weapon_ages)), '};']
    p.OUT.mkdir(exist_ok=True)
    header=p.OUT/'attachment_data.h';header.write_text('\n'.join(lines)+'\n',encoding='ascii')
    report={'status':'native selector established; model-origin correction candidate, visual validation required',
            'world_lmt_sha256':p.sha(p.WORLD),'header_sha256':p.sha(header),
            'source_build':'World 421810','native_selector_rva':'0x210d360',
            'native_matrix_consumer_rva':'0x210b8f0',
            'roles':{'9':{'requested_scale_y':2},'10':{'requested_scale_y':3}},
            'common_scale_y':4,'native_tolerance':0.1,'clock':'truncate to integer frame',
            'clips':evidence,'generated_header':str(header)}
    (p.PROJECT/'research/attachment_rules.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('Baked',len(samples),'attachment frames to',header)


if __name__=='__main__':main()
