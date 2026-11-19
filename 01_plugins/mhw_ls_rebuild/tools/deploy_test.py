"""Install a smoke-verified build into the existing isolated test entry only."""
from datetime import datetime
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT.parents[1]
DEST = ROOT / '02_build/testing/mhw_ls_rebuild'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = PROJECT / 'mhw_ls_rebuild.nro'
    if b'build=rebuild-b4' not in source.read_bytes() or b'body-preview-1' in source.read_bytes():
        raise SystemExit('This installer only accepts the normal b4 baseline, never a preview build.')
    report = json.loads((PROJECT / 'research/game_smoke_result.json').read_text())
    if report.get('result') != 'PASS' or report['build_sha256'] != digest(source):
        raise SystemExit('Refusing installation: this NRO has no matching PASS report.')
    subprocess.run(['python', str(ROOT / '06_tools/check_relocations.py'), str(source)], check=True)
    target = DEST / 'mods/MHW_LS_REBUILD/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'
    manifest_path = DEST / 'manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    if target.exists() and digest(target) == digest(source):
        print('Already installed:', digest(source))
        return
    backup = ROOT / '02_build/history/mhw_ls_rebuild_deploy' / datetime.now().strftime('%Y%m%d_%H%M%S')
    backup.mkdir(parents=True, exist_ok=False)
    shutil.copy2(target, backup / target.name)
    shutil.copy2(manifest_path, backup / manifest_path.name)
    stage = target.with_suffix('.nro.pending')
    shutil.copy2(source, stage)
    if digest(stage) != report['build_sha256']:
        raise RuntimeError('Staged copy failed hash verification')
    stage.replace(target)
    manifest.update(build='rebuild-b4', plugin_sha256=digest(target),
                    installed_at=datetime.now().astimezone().isoformat(),
                    previous_install_backup=str(backup), smoke_report=str(PROJECT / 'research/game_smoke_result.json'),
                    scope='Native thrust/fade baseline; six World moves not integrated yet')
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({'installed': str(target), 'sha256': digest(target), 'backup': str(backup)}, indent=2))


if __name__ == '__main__':
    main()
