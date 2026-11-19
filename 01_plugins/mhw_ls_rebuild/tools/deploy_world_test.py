"""Stage the matching verified plugin/ARC into the user's independent test entry."""
from datetime import datetime
import argparse,json,re,shutil,subprocess,sys
from pathlib import Path
from launch_world_test import ROOT,DEST,digest,verify_install

PROJECT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--asset-root',type=Path,help='Exact verified run from the regression report, for deployment across worktrees')
    args=ap.parse_args()
    report_path=PROJECT/'research/world_regression.json'
    report=json.loads(report_path.read_text(encoding='utf-8'))
    source=PROJECT/'mhw_ls_rebuild.nro'
    assets_root=(args.asset_root or ROOT/'.cache/mhw_ls_combat').resolve()
    if args.asset_root:
        assert assets_root==Path(report.get('presentation_run',report['run'])).resolve(),'Only the recorded verified run can supply cross-worktree assets'
    arc=assets_root/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/player/quest/w07.arc'
    assert report['status']=='PASS_REQUIRED_FIXTURE_CASES'
    assert digest(source)==report['plugin_sha256'] and digest(arc)==report['arc_sha256']
    assert b'build=world-controller-dev' in source.read_bytes()
    assert b'audio-probe-only=1' not in source.read_bytes(),'Audio probe is not a deployable gameplay build'
    presentation=report.get('presentation')
    if b'world_audio_queued' in source.read_bytes():
        assert presentation in ('world-layers-v102','simple-native-v1') and ('presentation='+presentation).encode() in source.read_bytes(),'Audio requires presentation acceptance'
        assert {'simple_presentation.json','audio_events.json','weapon_audio.json','simple_hit_fx.json','input_feel.json','iai_line.json','reported_fixes.json','feedback3.json','conditional_presentation.json'}<={c['name']for c in report['cases']}
    assert b'fx-probe-only=1' not in source.read_bytes(),'Effect probe is not a deployable gameplay build'
    assert b'world_fx_queued' not in source.read_bytes(),'Effects remain experimental until native visual acceptance'
    subprocess.run([sys.executable,str(ROOT/'06_tools/check_relocations.py'),str(source)],check=True)
    stamp=datetime.now().strftime('%Y%m%d_%H%M%S')
    backup=ROOT/'02_build/history/mhw_ls_rebuild_deploy'/stamp;backup.mkdir(parents=True)
    assert DEST.resolve().is_relative_to((ROOT/'02_build/testing').resolve())
    assert backup.resolve().is_relative_to((ROOT/'02_build/history').resolve())
    entry=ROOT/'启动MHGU_独立太刀测试.cmd'
    for p in [DEST/'manifest.json',entry]:
        if p.exists():shutil.copy2(p,backup/p.name)
    stage=DEST/('stage_'+stamp)
    assert stage.resolve().is_relative_to(DEST.resolve());stage.mkdir(parents=True)
    files={}
    assets=report['asset_sha256'];assert len(assets)==(11 if presentation else 9),'Body,8weapon-group and matching presentation ARCs required'
    pairs=[(source,'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro')]
    for rel,expected in assets.items():
        src=(assets_root/rel).resolve()
        assert src.is_relative_to((assets_root/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc').resolve())
        assert digest(src)==expected,('Asset changed since regression',rel)
        pairs.append((src,rel))
    for src,rel in pairs:
        dst=stage/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
        files[rel]=digest(dst);assert files[rel]==digest(src)
    profile=DEST/'profile';game=ROOT/'Windows-MHGURecomp'
    if not profile.exists():
        profile.mkdir();shutil.copytree(game/'save',profile/'save')
        cfg=(game/'mhgurecomp.ini').read_text(encoding='utf-8-sig')
        cfg=re.sub(r'^SaveLocation\s*=.*$',lambda m:'SaveLocation = '+str(profile/'save'),cfg,flags=re.M)
        (profile/'mhgurecomp.ini').write_text(cfg,encoding='utf8')
        shutil.copytree(game/'cache',profile/'cache',ignore=shutil.ignore_patterns('*.log'))
    if (DEST/'mods').exists():shutil.move(str(DEST/'mods'),str(backup/'mods'))
    shutil.move(str(stage/'mods'),str(DEST/'mods'));stage.rmdir()
    manifest={'build':'world-controller-dev','plugin_sha256':digest(source),'arc_sha256':digest(arc),
        'files':files,'installed_at':datetime.now().astimezone().isoformat(),'previous_install_backup':str(backup),
        'source':str(PROJECT),'regression_report':str(report_path),'normal_install_changed':False,
        'own_save_and_config':True,'complete_port_accepted':False,'remaining':report['remaining']}
    if presentation:manifest.update(presentation=presentation)
    (DEST/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    entry.write_text('@echo off\nsetlocal\npython "%~dp001_plugins\\mhw_ls_rebuild\\tools\\launch_world_test.py" %*\nif errorlevel 1 pause\nendlocal\n',encoding='ascii')
    verify_install();print('Installed matched plugin and ARC with independent save:',DEST)

if __name__=='__main__':main()
