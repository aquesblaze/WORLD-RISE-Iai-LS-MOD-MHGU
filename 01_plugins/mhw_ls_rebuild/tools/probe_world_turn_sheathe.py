"""Real pad chord/solo regressions against GU's directional roll requests."""
import json,time,hashlib
from pc_fixture import Fixture
from probe_guild_ownership import draw,wait


def main():
    f=Fixture();cases=[];status='FAIL'
    try:
        matrix=[(direction,mode) for direction in ('LEFT','RIGHT','UP','DOWN')
                for mode in ('together','r_first','b_only','b_first')]
        matrix+=[(direction,'foresight') for direction in ('LEFT','RIGHT')]
        matrix+=[('NONE','together'),('NONE','b_only')]
        for direction,mode in matrix:
            f.camp_station();draw(f)
            f.command('A 8');wait(f,lambda s:s['motion']==0x569 and s['frame']>=40)
            if mode=='foresight':
                f.command('R 18\nA 18')
                wait(f,lambda s:s['motion']==0x5e0 and s['frame']>=26)
            command='B 8' if mode=='b_only' else 'B 8\nR 8 2' if mode=='b_first' else \
                    'R 8\nB 8 2' if mode=='r_first' else 'R 8\nB 8'
            f.command(('' if direction=='NONE' else f'STICK_{direction} 22\n')+command)
            rows=[];end=time.monotonic()+2
            while time.monotonic()<end:
                rows.append(f.state());time.sleep(.005)
            sheath=any(s['action']==246 and s['motion']==0x5e6 for s in rows)
            rolls=[s for s in rows if s['state']==1 and s['action'] in (6,13,14)]
            expected_sheath=mode not in ('b_only','b_first')
            cases.append(dict(direction=direction,mode=mode,sheath=sheath,
                              roll_actions=sorted({s['action'] for s in rolls}),rows=rows))
            assert sheath==expected_sheath,(direction,mode,sheath,cases[-1]['roll_actions'])
            assert not rolls if expected_sheath else rolls,(direction,mode,cases[-1]['roll_actions'])
            print('PASS',direction,mode,'sheath' if sheath else 'native roll',flush=True)
        status='PASS_TURN_SHEATHE_AND_SOLO_ROLL'
    finally:
        report=dict(status=status,plugin_sha256=hashlib.sha256((f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro').read_bytes()).hexdigest(),
                    fixture='Copied-save camp station; actions/clocks driven by pad only',cases=cases)
        (f.run/'turn_sheathe.json').write_text(json.dumps(report,indent=2));f.close()


if __name__=='__main__':main()
