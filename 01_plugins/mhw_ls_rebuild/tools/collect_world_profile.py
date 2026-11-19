"""Collect matching installed-entry evidence with the user's rendering settings."""
import json,re
from pathlib import Path
from launch_world_test import ROOT,DEST,digest,verify_install


def main():
    manifest=verify_install()
    active=json.loads((ROOT/'.cache/mhw_ls_combat/active_session.json').read_text())
    assert Path(active['installed_entry']).resolve()==DEST.resolve()
    run=Path(active['run']).resolve()
    assert run.is_relative_to((ROOT/'.cache/mhw_ls_combat/runs').resolve())
    for relative,expected in manifest['files'].items():
        assert digest(run/relative)==expected,relative
    def settings(path):
        return dict(re.findall(r'^([A-Za-z]+)\s*=\s*([^\r\n]*)',path.read_text(encoding='utf-8-sig'),re.M))
    config=settings(run/'mhgurecomp.ini');installed=settings(DEST/'profile/mhgurecomp.ini')
    rendering={k:config[k] for k in ('Mode','Resolution','RenderResolution','FSR','FSRQuality')}
    assert all(v==installed[k] for k,v in rendering.items()),rendering
    reports={}
    for name in ('input_feel.json','early_r_repeated.json','reported_fixes.json'):
        data=json.loads((run/name).read_text())
        assert data['status'].startswith('PASS'),(name,data['status'])
        assert data['plugin_sha256']==manifest['plugin_sha256'],name
        reports[name]=data
    assert len(reports['input_feel.json']['cases'])==9
    trials=reports['early_r_repeated.json']['cases']
    assert len(trials)==8 and all(c['passed'] and c['after']['action']==16 for c in trials)
    log=(run/'log.txt').read_text(encoding='utf8',errors='replace')
    dense=re.findall(r'^.*\[audren\] (?:f\d+|hf f\d+|aux:|i3dl2 init:|reverb init:|v\d+ biquad).*$',log,re.M)
    assert not dense and '[atrace]' not in log,'Audio diagnostic logging was enabled'
    result={'status':'PASS_INSTALLED_PROFILE_INPUT_AUDIO_MOTION',
        'run':str(run),'plugin_sha256':manifest['plugin_sha256'],
        'installed_entry':str(ROOT/'启动MHGU_独立太刀测试.cmd'),
        'rendering_config':rendering,'config_sha256':digest(run/'mhgurecomp.ini'),
        'all_installed_assets_match':True,'dense_audio_trace_lines':len(dense),
        'input_cases':9,'early_R_trials':8,'early_R_successes':8,
        'audio_peak':reports['reported_fixes.json']['audio_peak'],
        'evidence':[{'path':str(run/n),'sha256':digest(run/n),'status':d['status']} for n,d in reports.items()],
        'limits':'Rendering configuration preserved; actual display resolution/FPS not asserted. Copied save, current weapon and surveyed camp fixture. Source PCM and advancing bone/animation clocks do not establish exact World mixing or full visual equivalence.'}
    first=run/'profile_first_reported_motion_audio.json'
    if first.exists():
        result['prior_capture_not_accepted']={
            'path':str(first),'sha256':digest(first),
            'reason':'Timeout frame34..50 had only one completed clock interval, insufficient for the unchanged >2 interval requirement. Raw clocks included a14.67-frame step. Audio and Iai clock assertions passed before this failure.',
            'followup':'Omitted full voice-manager diagnostics using --skip-voices; retained PCM, clock, bone and attachment acceptance. Subsequent capture passed. This comparison does not establish the cause of long frames or guarantee smooth rendering.'}
    project=Path(__file__).resolve().parents[1]
    for path in (run/'profile_rendering_validation.json',project/'research/world_profile_rendering_validation.json'):
        path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(result['status'],'9 input cases; 8/8 early R; peak',result['audio_peak'])


if __name__=='__main__':main()
