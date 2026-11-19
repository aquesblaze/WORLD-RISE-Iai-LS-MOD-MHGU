"""Record a bounded subset actually run from the installed independent entry."""
import argparse,json
from pathlib import Path
from launch_world_test import ROOT,DEST,verify_install,digest


def main():
    ap=argparse.ArgumentParser();ap.add_argument('reports',nargs='+');args=ap.parse_args()
    active=json.loads((ROOT/'.cache/mhw_ls_combat/active_session.json').read_text())
    assert active['installed_entry'] and Path(active['installed_entry']).resolve()==DEST.resolve()
    run=Path(active['run']);manifest=verify_install();evidence=[]
    for rel,expected in manifest['files'].items():assert digest(run/rel)==expected,(rel,'Run differs from installed assets')
    for name in args.reports:
        path=(run/name).resolve();assert path.is_relative_to(run.resolve())
        d=json.loads(path.read_text(encoding='utf8'))
        assert d['status'].startswith('PASS') and d['plugin_sha256']==manifest['plugin_sha256'],(name,d['status'])
        evidence.append({'report':name,'status':d['status'],'sha256':digest(path)})
    result={'status':'PASS_INSTALLED_ENTRY_SUBSET','installed_entry':str(ROOT/'启动MHGU_独立太刀测试.cmd'),
            'run':str(run),'plugin_sha256':manifest['plugin_sha256'],'files':manifest['files'],'evidence':evidence,
            'own_save_and_config':True,'full_visual_acceptance':False,'complete_port_accepted':False,
            'limits':'Only the listed assertions ran from these installed assets. Development regression and remaining work are separate evidence.'}
    out=Path(__file__).resolve().parents[1]/'research/world_entry_validation.json'
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    (run/'entry_validation.json').write_text(out.read_text(encoding='utf8'),encoding='utf8')
    print(result['status'],manifest['plugin_sha256'],len(evidence),'cases')


if __name__=='__main__':main()
