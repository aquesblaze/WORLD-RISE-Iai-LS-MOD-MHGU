"""Assert counter outcomes from actual geometry/body/HP and action observations."""
import argparse,json,re
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('record',type=Path)
    ap.add_argument('--expect',choices=['success','failure','round_sheathe'],required=True)
    args=ap.parse_args();d=json.loads(args.record.read_text());rows=d['rows']
    move={'foresight':240,'small':247,'big':248}[d['move']]
    active=[r for r in rows if r['state']==16 and r['action']==move and r['motion']>=0x5e0]
    assert active,'The requested action never bound; setup is not a test result'
    counters=[e for e in d['events'] if 'world_counter ' in e]
    geometry=[e for e in d['events'] if 'world_detector_contact ' in e]
    body=[e for e in d['events'] if 'world_detector_body ' in e]
    separate=any(re.search(r'world_detector_body \w+ 00000000 00000000 ',e) for e in body)
    incoming=[e for e in d['events'] if 'world_incoming ' in e]
    body_before_counter=False
    if counters:
        cf=int(counters[0].split()[-2],16)
        body_before_counter=any(int(e.split()[-2],16)<cf for e in incoming)
    assert incoming or geometry,'No incoming attack; cannot certify a counter outcome'
    if args.expect=='failure':
        assert not counters and not geometry,d['events']
        if d['move']=='big':assert any(r['rank']==d['rank_fixture']-1 for r in rows)
        else:assert min(r['hp'] for r in rows)<rows[0]['hp']
    else:
        assert len(counters)==1 and len(geometry)==1,d['events']
        if d['move']=='big':assert all(r['rank']==d['rank_fixture'] for r in active)
        if args.expect=='round_sheathe':
            round_rows=[r for r in rows if r['state']==16 and r['action']==30]
            after=[r for r in rows if r['state']==16 and r['action']==246 and r['motion']==0x5e6]
            assert round_rows and after
            assert any(r['gauge']==100 for r in active)
            assert any(r['rank']==d['rank_fixture']+1 for r in after)
    result={'status':'PASS_COUNTER_'+args.expect.upper(),'source':str(args.record.resolve()),
        'plugin_sha256':d['plugin_sha256'],'move':d['move'],'events':d['events'],
        'counter_detected_without_body_packet':separate,
        'counter_after_an_earlier_body_packet':body_before_counter,
        'active_rank_values':sorted({r['rank'] for r in active}),
        'active_hp_range':[min(r['hp'] for r in active),max(r['hp'] for r in active)],
        'fixture':'Copied save; native enemy attack and pad-driven moves, explicit station/rank/gauge/HP setup.',
        'limits':['One attack/timing/position fixture; other shapes, status types and natural combat remain separate checks.',
            'Small Iai can lose HP to later hits after its five animation-frame invulnerability; its counter armor suppresses stagger, not all damage.']}
    out=args.record.with_name(args.record.stem+'_report.json');out.write_text(json.dumps(result,indent=2))
    print(result['status'],d['move'],'outside body:',separate)

if __name__=='__main__':main()
