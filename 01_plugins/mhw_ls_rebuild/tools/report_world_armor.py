"""Validate native incoming KO damage with and without source counter armor."""
import argparse,json
from pathlib import Path

def main():
    ap=argparse.ArgumentParser();ap.add_argument('record',type=Path);a=ap.parse_args()
    d=json.loads(a.record.read_text(encoding='utf8'))
    assert any('world_counter ' in e for e in d['events']),'No real counter contact'
    events=[[int(v,16) for v in e.split()[-3:]] for e in d['events'] if 'world_stun ' in e]
    protected=[e for e in events if e[0]&0x10000]
    ordinary_only=[e for e in events if e[0]&0x30000==0x20000]
    unprotected=[e for e in events if not e[0]&0x30000]
    assert protected and unprotected,'Need both positive and negative controls'
    assert all(e[1]==e[2] for e in protected),protected
    assert all(e[1]==e[2] for e in ordinary_only),ordinary_only
    assert any(e[1]==d['stun_start_fixture'] and e[1]>0 for e in protected),protected
    assert any(e[2]==e[1]+(e[0]&65535) for e in unprotected),unprotected
    active=[r for r in d['rows'] if r['action']==247 and r['motion']==0x5ee]
    assert active and min(r['hp'] for r in active)<d['rows'][0]['hp'],'No real damage after the invulnerability window'
    hp_events=[]
    for e in d['events']:
        if 'world_hp_hit ' not in e:continue
        raw,applied,health=[int(v,16)for v in e.split()[-3:]]
        raw=raw if raw<0x80000000 else raw-0x100000000
        applied=applied if applied<0x80000000 else applied-0x100000000
        assert raw<0 and applied<0,(raw,applied)
        if raw!=applied:assert applied==-max(1,(-raw)//2),(raw,applied)
        hp_events.append({'incoming_delta':raw,'applied_delta':applied,'before':health>>16,'after':health&65535})
    result={'status':'PASS_COUNTER_ARMOR_STUN','plugin_sha256':d['plugin_sha256'],
        'source':str(a.record.resolve()),'protected':protected,'ordinary_only':ordinary_only,'unprotected':unprotected,
        'hp_during_small_iai':[min(r['hp'] for r in active),max(r['hp'] for r in active)],
        'native_hp_deltas':hp_events,'half_damage_observed':any(h['incoming_delta']!=h['applied_delta']for h in hp_events),
        'native_attack_difficulty_fixture':d.get('native_attack_difficulty_fixture'),
        'fixture':'Copied save, real native enemy attack/collision. Explicit initial KO17 and timer6000; second attack windup can be shortened by fixture. Existing buildup is not cleared.',
        'limits':'One physical attack. Other status effects and attacks remain independent coverage.'}
    out=a.record.parent/'armor_stun_report.json';out.write_text(json.dumps(result,indent=2),encoding='utf8')
    print(result['status'],protected,unprotected)

if __name__=='__main__':main()
