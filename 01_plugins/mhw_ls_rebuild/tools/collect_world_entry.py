"""Accept only matching reports produced by the actual installed CMD entry."""
import argparse,json
from pathlib import Path
from launch_world_test import ROOT,DEST,digest,verify_install

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--presentation-smoke',action='store_true');args=parser.parse_args()
    verify_install();project=Path(__file__).resolve().parents[1]
    manifest=json.loads((DEST/'manifest.json').read_text(encoding='utf8'))
    regression=json.loads((project/'research/world_regression.json').read_text(encoding='utf8'))
    entry=ROOT/'启动MHGU_独立太刀测试.cmd'
    assert regression['status']=='PASS_REQUIRED_FIXTURE_CASES'
    if args.presentation_smoke:
        assert manifest.get('presentation')==regression.get('presentation') and manifest['presentation'] in ('world-layers-v102','simple-native-v1')
        assert regression['plugin_sha256']==manifest['plugin_sha256']
        active=json.loads((ROOT/'.cache/mhw_ls_combat/active_session.json').read_text())
        assert active.get('installed_entry') and Path(active['installed_entry']).resolve()==DEST.resolve()
        run=Path(active['run']).resolve();assert run.is_relative_to((ROOT/'.cache/mhw_ls_combat/runs').resolve())
        assert not (run/'audio_attenuation_diagnostic.json').exists(),'Live resource edits are diagnostic evidence only'
        for rel,expected in manifest['files'].items():assert digest(run/rel)==expected,rel
        required=['simple_presentation.json','encounter_probe_rank1_seven_hit_report.json',
                  'audio_events.json','weapon_audio.json','weapon_transitions.json',
                  'lifecycle_ground_zone.json','simple_hit_fx.json','counter_foresight_7_14_0.15_report.json',
                  'input_feel.json','iai_line.json','reported_fixes.json']
        if b'world_loop_native' in (run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro').read_bytes():
            required+=['loop_control.json','encounter_probe_auto_seven_hit_report.json']
            assert len(json.loads((run/'loop_control.json').read_text())['cases'])==12
            automatic=json.loads((run/'encounter_probe_auto.json').read_text())
            air=[r for r in automatic['rows']if r['action']==243 and r['motion']==0x5e3]
            assert automatic['auto_down_no_attack_input'] and air and all(r['raw_attack_buttons']==0 for r in air)
        evidence=[]
        for name in required:
            p=run/name;d=json.loads(p.read_text());assert d['status'].startswith('PASS'),(name,d['status'])
            assert d['plugin_sha256']==manifest['plugin_sha256'],name
            evidence.append({'report':name,'status':d['status'],'path':str(p),'sha256':digest(p)})
        result={'status':'PASS_INSTALLED_SIMPLE_PRESENTATION','installed_entry':str(entry),'run':str(run),
            'plugin_sha256':manifest['plugin_sha256'],'files':manifest['files'],'evidence':evidence,
            'development_regression':str(project/'research/world_regression.json'),
            'development_regression_sha256':digest(project/'research/world_regression.json'),
            'development_cases':len(regression['cases']),'own_save_and_config':True,
            'presentation':manifest['presentation'],'six_move_functional_checks_passed':True,
            'complete_port_accepted':False,'remaining':regression['remaining'],
            'limits':'Full development regression plus a matching installed-entry smoke covering all six moves, native seven contacts, counter, area recovery and audio/visual loading; not exact World visual equivalence.'}
        (project/'research/world_entry_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        print(result['status'],len(evidence),'installed cases;',len(regression['cases']),'development cases');return
    assert regression['installed_entry'] and Path(regression['installed_entry']).resolve()==DEST.resolve()
    assert regression['plugin_sha256']==manifest['plugin_sha256']
    run=Path(regression['run']);assert run.resolve().is_relative_to((ROOT/'.cache/mhw_ls_combat/runs').resolve())
    for rel,expected in manifest['files'].items():assert digest(run/rel)==expected,rel
    evidence=[]
    for case in regression['cases']:
        p=run/case['name'];d=json.loads(p.read_text(encoding='utf8'))
        assert digest(p)==case['sha256'] and d['plugin_sha256']==manifest['plugin_sha256']
        evidence.append({'report':p.name,'status':d['status'],'sha256':case['sha256']})
    result={'status':'PASS_INSTALLED_ENTRY_REQUIRED_CASES','installed_entry':str(entry),'run':str(run),
            'plugin_sha256':manifest['plugin_sha256'],'files':manifest['files'],'evidence':evidence,
            'own_save_and_config':True,'full_visual_acceptance':False,'complete_port_accepted':False,
            'limits':regression['limits'],'remaining':regression['remaining']}
    (project/'research/world_entry_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(result['status'],len(evidence),'cases',manifest['plugin_sha256'])

if __name__=='__main__':main()
