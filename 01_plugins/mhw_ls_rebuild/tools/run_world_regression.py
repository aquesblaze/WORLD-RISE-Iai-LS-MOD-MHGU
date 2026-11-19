"""Sequential regression against one existing fixture; stop at the first failure."""
import argparse,json,subprocess,sys
from pathlib import Path
from pc_fixture import ROOT

def main():
    ap=argparse.ArgumentParser();ap.add_argument('section',choices=['camp','combat','camera','counter','lifecycle','finish','all']);args=ap.parse_args()
    run=Path(json.loads((ROOT/'.cache/mhw_ls_combat/active_session.json').read_text())['run'])
    here=Path(__file__).resolve().parent
    def call(tool,*argv):
        print('Running',tool,*map(str,argv),flush=True)
        result=subprocess.run([sys.executable,str(here/(tool+'.py')),*map(str,argv)],capture_output=True,text=True,encoding='utf8',errors='replace')
        with (run/'regression_commands.log').open('a',encoding='utf8') as log:log.write('\n'+tool+' '+' '.join(map(str,argv))+'\n'+result.stdout+result.stderr)
        if result.returncode:print(result.stdout[-1000:]+result.stderr[-2000:],flush=True);raise SystemExit(result.returncode)
        print('OK',tool,flush=True)
    if args.section in ('camp','all'):
        # links covers the dedicated action250 opener; the historical Spirit
        # probe expects the superseded native action16 route.
        for name in ['probe_world_links','probe_world_turn','probe_world_sheathe_skill']:call(name)
    if args.section in ('combat','all'):
        for move in ['small','big','foresight']:
            call('probe_world_ground_hit',move,*(['--regen-check'] if move=='small' else []))
            call('report_world_ground',run/f'ground_{move}.json')
        for options,name in [(['--rank','1'],'rank1'),(['--rank','2'],'rank2'),
                (['--landing-follow','sheathe'],'sheathe'),(['--primary-limit','1'],'primary1'),(['--air-turn'],'airturn')]:
            call('probe_world_encounter',*options);call('report_world_encounter',run,f'encounter_probe_{name}.json')
    if args.section in ('camera','all'):
        for options,name in [([],''),(['--rank','0'],'_rank0'),(['--whiff'],'_whiff')]:
            call('probe_world_ground_hit','big',*options,*([]if name=='_whiff'else['--contact-offset-x','60','--contact-gap','300','--static-contact-station']))
            call('report_world_camera',run/f'ground_big{name}.json')
        call('report_world_ground',run/'ground_big.json')
    if args.section in ('counter','finish','all'):
        # The target may already be enraged after combat fixtures (1.2x
        # animation speed). This prelude delay places contact inside the
        # source counter window at both native speeds, without seeking either
        # actor's measured action clock or enlarging the counter window.
        call('probe_world_counter','foresight','--attack','14','--delay','0.15','--contact-fixture','--rank','2','--round','--sheathe-after-round')
        call('report_world_counter',run/'counter_foresight_7_14_0.15.json','--expect','round_sheathe')
        call('probe_world_counter','small','--attack','14','--contact-fixture','--at-frame','63','--stun-start','17','--armor-follow-hit')
        record=run/'counter_small_7_14_0.3_frame63.0_armor.json'
        call('report_world_counter',record,'--expect','success');call('report_world_armor',record)
        call('probe_world_counter','big','--attack','14','--contact-fixture','--at-frame','65')
        call('report_world_counter',run/'counter_big_7_14_0.3_frame65.0.json','--expect','success')
    if args.section in ('finish','all'):call('probe_weapon_transitions')
    if args.section in ('lifecycle','finish','all'):
        for case in ('ground_zone','air_zone','down_zone'):call('probe_world_lifecycle',case)

if __name__=='__main__':main()
