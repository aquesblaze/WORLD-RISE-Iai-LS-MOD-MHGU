"""Evaluate ordinary ground hits, failed big-Iai cost, and small-Iai regeneration."""
import argparse,hashlib,json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('record',type=Path);args=ap.parse_args()
    d=json.loads(args.record.read_text());action={'foresight':240,'small':247,'big':248}[d['move']]
    plugin=args.record.parent/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'
    sha=hashlib.sha256(plugin.read_bytes()).hexdigest()
    assert d.get('plugin_sha256',sha)==sha,'Recorded build does not match fixture build'
    active=[r for r in d['rows'] if r['state']==16 and r['action']==action]
    assert active,'No actual move'
    changes=[];previous=None
    for row in d['rows']:
        hp=next(e['hp'] for e in row['enemies'] if e['actor']==d['target'])
        if previous is not None and hp<previous and row['time']<=active[-1]['time']+.6:
            changes.append({'damage':previous-hp,'action':row['action'],'frame':row['frame']})
        previous=hp
    expected=1 if d['move']=='foresight' else 2
    assert len(changes)==expected,(d['move'],changes)
    assert all(r['damage']>1 for r in changes),changes
    if d['move']=='small':
        assert d['status']=='PASS_REGEN_RATE_ONLY',d.get('regen_result')
    if d['move']=='big':assert active[0]['rank']==3 and d['rows'][-1]['rank']==2
    if d['move']=='foresight':assert d['rows'][-1]['gauge']==0
    report={'status':'PASS_GROUND_'+d['move'].upper(),'source':str(args.record.resolve()),
        'plugin_sha256':sha,'actual_hp_changes':changes,
        'rank_before':active[0]['rank'],'rank_after':d['rows'][-1]['rank'],'regen':d.get('regen_result'),
        'limits':'Stationary native monster, pad inputs, explicit position/HP/rank setup in copied save; not a counter test.'}
    args.record.with_name(args.record.stem+'_report.json').write_text(json.dumps(report,indent=2))
    print(report['status'],changes)

if __name__=='__main__':main()
