"""Collect matching-build fixture evidence; never equate it with complete acceptance."""
import argparse,hashlib,json
from pathlib import Path
from pc_fixture import ROOT

PROJECT=Path(__file__).resolve().parents[1]
CASES=[
    'camp_links.json','turn_report.json','small_spirit_follow.json','sheathe_skill.json',
    'ground_small_report.json','ground_big_report.json','ground_foresight_report.json',
    'encounter_probe_rank1_seven_hit_report.json','encounter_probe_rank2_seven_hit_report.json',
    'encounter_probe_sheathe_seven_hit_report.json','encounter_probe_primary1_seven_hit_report.json',
    'air_turn_report.json','armor_stun_report.json','weapon_transitions.json',
    'lifecycle_ground_zone.json','lifecycle_air_zone.json','lifecycle_down_zone.json',
    'ground_big_camera_report.json','ground_big_rank0_camera_report.json','ground_big_whiff_camera_report.json']
REMAINING=[
    '特殊纳刀超时的手部偏移残留已修正；8类GU太刀资产可加载，其他装备外形和刀鞘原点仍待视觉验收。',
    '大居合使用World直线亮光素材和GU原生线条渲染，其余特效简化。居合声音在源增益上加6dB作GU混音补偿，保留GU衰减/混响；首段镜头震动未复刻。',
    '大居合镜头已接入两次源触发、逐帧重置时长和四次缓出；当前用GU最近骨骼适配源6个主骨候选，逐怪物语义映射与遮挡仍待验收。',
    '已覆盖换区清理、刃色结算及真实怪物攻击导致的猫车后恢复；多目标、更多地形/帧率及更换角色仍需更多实战覆盖。']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('run',type=Path)
    ap.add_argument('--presentation-run',type=Path,help='Separate traced audio checks with identical gameplay code/body/weapon/FX; only audio ARC may differ')
    ap.add_argument('--audio-events-run',type=Path,help='Only native-voice audio_events comes from this matching traced run')
    args=ap.parse_args()
    run=args.run.resolve();plugin=run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'
    present=args.presentation_run.resolve() if args.presentation_run else run
    audio_run=args.audio_events_run.resolve() if args.audio_events_run else present
    assert audio_run.is_relative_to((ROOT/'.cache/mhw_ls_combat/runs').resolve())
    assert present.is_relative_to((ROOT/'.cache/mhw_ls_combat/runs').resolve())
    assert not (present/'audio_attenuation_diagnostic.json').exists(),'Live resource edits are diagnostic evidence only'
    assert not (run/'audio_attenuation_diagnostic.json').exists(),'Live resource edits are diagnostic evidence only'
    arc=run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/player/quest/w07.arc';build=sha(plugin)
    assert sha(present/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro')==build
    cases=[]
    required=list(CASES)
    presentation=next((name for name in ('world-layers-v102','simple-native-v1')
                       if ('presentation='+name).encode() in plugin.read_bytes()), None)
    extras=['simple_presentation.json','audio_events.json','weapon_audio.json','simple_hit_fx.json','faint_recovery.json','input_feel.json','iai_line.json','reported_fixes.json'] if presentation else []
    required+=extras
    if b'world_loop_native' in plugin.read_bytes():required.append('feedback_v2.json')
    required+=['feedback3.json','conditional_presentation.json','conditional_transport.json']
    # Faint/recovery depends on the identical gameplay code/body/FX, not
    # request overlap groups in the audio bank. Preserve its original run.
    present_names=set(extras)-{'faint_recovery.json'}
    for move,status in [('foresight','PASS_COUNTER_ROUND_SHEATHE'),('small','PASS_COUNTER_SUCCESS'),('big','PASS_COUNTER_SUCCESS')]:
        candidates=[]
        for p in run.glob(f'counter_{move}_*_report.json'):
            d=json.loads(p.read_text(encoding='utf8'))
            if d.get('status')==status and d.get('plugin_sha256')==build:candidates.append(p)
        assert candidates,('Missing matching counter case',move,status)
        required.append(max(candidates,key=lambda p:p.stat().st_mtime_ns).name)
    for name in required:
        p=(audio_run if name=='audio_events.json' else present if name in present_names else run)/name;d=json.loads(p.read_text());assert d['status'].startswith('PASS'),(name,d['status'])
        assert d['plugin_sha256']==build,('Different build',name)
        cases.append({'name':name,'status':d['status'],'path':str(p),'sha256':sha(p),'asset_scope':'presentation' if name in present_names else 'unchanged_gameplay'})
    manifest=ROOT/'.cache/mhw_ls_combat/active_session.json';active=json.loads(manifest.read_text())
    entry=active.get('installed_entry') if Path(active['run']).resolve()==run else None
    report={'status':'PASS_REQUIRED_FIXTURE_CASES','run':str(run),'plugin_sha256':build,'arc_sha256':sha(arc),
        'cases':cases,'copied_save':True,'installed_entry':entry,'complete_port_accepted':False,
        'remaining':REMAINING,'limits':'These assertions use native collision/damage and pad-driven transitions, with explicit fixture station/rank/HP/skill setup. They do not establish full gameplay or visual equivalence.'}
    weapon=json.loads((run/'weapon_transitions.json').read_text(encoding='utf8'))['weapon_assets']
    relative=['mods/MHW_WORLD_DEV/romfs/nativeNX/arc/player/quest/w07.arc',*weapon]
    if presentation:relative += ['mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/'+n+'.arc'for n in ('world_audio','world_simple_fx')]
    assets={rel:sha(present/rel)for rel in relative}
    assert sha(audio_run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro')==build
    for rel,expected in assets.items():assert sha(audio_run/rel)==expected,('Audio evidence assets changed',rel)
    if audio_run!=present:
        report['audio_events_run']=str(audio_run)
        report['audio_events_scope']='Same NRO and all eleven ARCs; only native voice trace uses this run. Actual report paths/hashes are retained.'
    # Only the audio bank may differ. Gameplay reports retain their original
    # paths/hashes and are never relabelled as runs of the revised audio bank.
    for rel in relative:
        if not rel.endswith('/forge/world_audio.arc'):assert sha(run/rel)==assets[rel],('Gameplay/FX changed; full regression required',rel)
    if present!=run:
        report['presentation_run']=str(present)
        audio_changed=sha(run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_audio.arc')!=assets['mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_audio.arc']
        report['reused_gameplay_evidence']=('Identical NRO, body, eight weapon ARCs and FX ARC; '+
            ('only audio bank differs.' if audio_changed else 'audio bank also identical; traced presentation and untraced gameplay use separate runs.')+
            ' Each case records its actual evidence path and hash; no report is relabelled.')
    assert len(weapon)==8 and all(assets.get(k)==v for k,v in weapon.items())
    if presentation:
        visual=json.loads((present/'simple_presentation.json').read_text())
        assert json.loads((run/'armor_stun_report.json').read_text()).get('half_damage_observed'),'Need native non-minimum half-damage evidence'
        assert visual['audio_arc_sha256']==assets[relative[-2]] and visual['fx_arc_sha256']==assets[relative[-1]]
        audio=json.loads((audio_run/'audio_events.json').read_text())
        assert audio['bank_sha256']==assets[relative[-2]]
        bank=json.loads((PROJECT/'research/world_audio_bank.json').read_text(encoding='utf8'))
        assert bank['arc_sha256']==assets[relative[-2]]
        assert audio['native_request_overlap_groups']==list(range(0x300,0x300+len(bank['requests'])))
        assert json.loads((present/'weapon_audio.json').read_text())['bank_sha256']==assets[relative[-2]]
        assert json.loads((present/'iai_line.json').read_text())['fx_arc_sha256']==assets[relative[-1]]
        report['presentation']=presentation
        report['six_move_functional_checks_passed']=True
        report['source_efx_visual_equivalence_required']=False
    report['asset_sha256']=assets
    out=PROJECT/'research/world_regression.json';out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (run/'regression_report.json').write_text(out.read_text(encoding='utf8'),encoding='utf8')
    print(report['status'],len(cases),'matching cases;',build)

if __name__=='__main__':main()
