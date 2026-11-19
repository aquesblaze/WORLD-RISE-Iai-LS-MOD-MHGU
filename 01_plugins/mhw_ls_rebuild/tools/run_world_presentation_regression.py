"""Sequential matching-build presentation and feedback regression."""
import json,subprocess,sys
from pathlib import Path
from pc_fixture import ROOT

def main():
    run=Path(json.loads((ROOT/'.cache/mhw_ls_combat/active_session.json').read_text())['run']);here=Path(__file__).resolve().parent
    commands=[('verify_conditional_transport',),('probe_world_input_feel',),('probe_world_loop_control',),
        ('probe_world_encounter','--auto-down'),('report_world_encounter',str(run),'encounter_probe_auto.json'),
        ('probe_world_simple_fx',),('probe_world_audio_events','--keep'),('probe_world_weapon_audio',),
        ('probe_world_iai_line',),('probe_world_faint',),('probe_reported_motion_audio','--burst','--skip-voices'),
        ('analyze_reported_audio',),('report_reported_fixes',),('report_world_simple_hits',),('report_world_feedback',str(run))]
    for tool,*args in commands:
        print('Running',tool,flush=True)
        result=subprocess.run([sys.executable,str(here/(tool+'.py')),*args],capture_output=True,text=True,encoding='utf8',errors='replace')
        with(run/'regression_commands.log').open('a',encoding='utf8')as log:log.write('\n'+tool+' '+' '.join(args)+'\n'+result.stdout+result.stderr)
        if result.returncode:print(result.stdout[-1000:]+result.stderr[-2000:],flush=True);raise SystemExit(result.returncode)
        print('OK',tool,flush=True)

if __name__=='__main__':main()
