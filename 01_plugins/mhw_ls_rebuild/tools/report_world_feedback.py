"""Collect the new loop/automatic Helm/source-flash observations without relabelling."""
import argparse,json,re
from pathlib import Path
from animation_port import PROJECT,sha

def main():
    ap=argparse.ArgumentParser();ap.add_argument('run',type=Path);args=ap.parse_args();run=args.run.resolve()
    plugin=sha(run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro')
    loop=json.loads((run/'loop_control.json').read_text());assert loop['status'].startswith('PASS') and len(loop['cases'])==12
    auto=json.loads((run/'encounter_probe_auto.json').read_text());hits=json.loads((run/'encounter_probe_auto_seven_hit_report.json').read_text())
    air=[r for r in auto['rows']if r['action']==243 and r['motion']==0x5e3]
    assert auto['auto_down_no_attack_input'] and air and all(r['raw_attack_buttons']==0 for r in air)
    assert {241,242,243,244,245}.issubset(auto['phases']) and hits['status']=='PASS_SEVEN_NATIVE_DAMAGE_CONTACTS'
    accepted=[]
    for path in run.glob('counter_big_*_report.json'):
        data=json.loads(path.read_text())
        if data['status']=='PASS_COUNTER_SUCCESS'and data['plugin_sha256']==plugin:accepted.append((path,data))
    assert accepted,'Need a matching real successful big-Iai counter'
    success_path,success=max(accepted,key=lambda pair:pair[0].stat().st_mtime_ns)
    record=Path(success['source']).resolve();assert record.parent==run
    counter=json.loads(record.read_text())
    with(run/'log.txt').open('rb')as stream:stream.seek(counter['log_start']);log=stream.read().decode(errors='replace')
    emits=[tuple(int(x,16)for x in row)for row in re.findall(r'world_simple_fx_emit [0-9A-F]+ (00003F6[678]|00003FC2) ([0-9A-F]+) ([0-9A-F]+)',log)]
    expected=(0x3fc2,) if 'presentation=world-layers-v102' in (run/'log.txt').read_text(errors='replace') else range(0x3f66,0x3f69)
    for uid in expected:assert sum(u==uid and source==311 and ok==1 for u,source,ok in emits)==1,emits
    shot=run/'shots/big_counter_source_flash.png';assert shot.exists() and shot.stat().st_size>0
    for data in (loop,hits,success,counter):assert data['plugin_sha256']==plugin
    evidence=[run/'loop_control.json',run/'encounter_probe_auto.json',run/'encounter_probe_auto_seven_hit_report.json',record,record.with_name(record.stem+'_report.json'),shot]
    report={'status':'PASS_LOOP_AUTO_HELM_AND_SOURCE_FLASHES','plugin_sha256':plugin,'run':str(run),
        'loop_transitions':12,'air_samples_with_released_attack_keys':len(air),'native_counter_flash_emits':emits,
        'fx_arc_sha256':sha(run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_simple_fx.arc'),
        'evidence':[{'path':str(p),'sha256':sha(p)}for p in evidence],
        'limits':'Current weapon and copied-save fixtures. Flash uses source atlas/colour/lifetime with GU shader and brightness compensation; full World rendering/mixing equivalence not claimed.'}
    for p in (run/'feedback_v2.json',PROJECT/'research/world_feedback_v2_validation.json'):
        p.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(report['status'])

if __name__=='__main__':main()
