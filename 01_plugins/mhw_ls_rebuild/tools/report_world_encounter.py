"""Assert observed HP changes; shell allocation alone cannot pass this check."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[3]
PROJECT=Path(__file__).resolve().parents[1]

def main():
    run=Path(sys.argv[1]).resolve()
    input_name=sys.argv[2] if len(sys.argv)>2 else 'encounter_probe.json'
    d=json.loads((run/input_name).read_text())
    target=d['target'];drops=[];previous=None
    for row in d['rows']:
        enemy=next((e for e in row['enemies'] if e['actor']==target),None)
        if not enemy:continue
        hp=enemy['hp']
        if previous is not None and hp!=previous:
            drops.append({'time':row['time'],'damage':previous-hp,'action':row['action'],
                'frame':row['frame'],'rank':row['rank'],'hp':hp})
        previous=hp
    # A pending helm shell can land after special sheathe begins. Attribution
    # follows the source shell contacts, not the owner's current animation.
    assert d.get('landing_follow') in (None,'sheathe'),'Foresight follow requires separate hit attribution'
    start_down=next(r['time'] for r in d['rows'] if r['action']==244)
    assert set(range(241,246)).issubset(d['phases']),d['phases']
    first_contact={}
    for row in d['shells']:
        if row['contact'][1]==target and row['contact'][2]&255==1:
            first_contact.setdefault(row['shell'],row['time'])
    contacts=set(first_contact)
    assert len(contacts)==7,contacts
    if 'helm_burst_events' in d:
        assert sorted(e[1]for e in d['helm_burst_events'])==list(range(7)),d['helm_burst_events']
    # Inspect native collision packets, including the seventh shell's distinct
    # source part multiplier. This does not infer damage from allocations.
    scales={}
    for row in d['shells']:
        if row['shell'] in contacts and 'element_part_scale' in row:
            scales.setdefault(row['shell'],row['element_part_scale'])
    if scales:
        assert len(scales)==7
        values=sorted(v[1] for v in scales.values())
        assert all(abs(v-.9)<1e-5 for v in values[:6]) and abs(values[6]-3)<1e-5,values
    # Restrict HP attribution to these shells' contact interval. Unrelated
    # monster/status damage many seconds after their expiry is kept in drops.
    first_shell=min(r['time'] for r in d['shells'] if r['shell'] in contacts)
    primary_samples=[r for r in d['rows'] if r['action']==244 and r['motion']==0x5e4 and r['frame']>=30 and r['time']<first_shell]
    if primary_samples and all('hitstop' in r for r in primary_samples):
        assert all(max(r['hitstop'])==0 for r in primary_samples),'Zero-damage primary added native hitstop'
        assert primary_samples[-1]['frame']>primary_samples[0]['frame'],'Downstroke stopped advancing'
    if d.get('primary_limit_fixture'):
        assert 0<len(d['primary_clock'])<7,d['primary_clock']
    last_contact=max(first_contact.values())
    # Collision flags precede the monster's committed HP update. Do not cut
    # off the seventh real loss at an assumed80ms: native queue/long frames
    # can commit it later. Bound attribution by the source contact's0.5s
    # lifetime and still require all seven distinct native shell contacts,
    # plus seven HP losses (or exact uniform merged updates) below.
    delayed=[r for r in drops if max(start_down,first_shell-.08)<=r['time']<=last_contact+.5]
    assert delayed and len(delayed)<=7 and all(r['damage']>0 for r in delayed),drops
    total=sum(r['damage'] for r in delayed)
    # Seven separate native HP updates can differ with native hitzone/affinity
    # and rank changes. Only merged samples need the uniform-damage inference.
    per_contact=total//7 if total%7==0 else None
    if len(delayed)<7:
        assert per_contact and all(r['damage']%per_contact==0 for r in delayed),drops
    plugin=run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'
    report={'status':'PASS_SEVEN_NATIVE_DAMAGE_CONTACTS','run':str(run),'input':input_name,
        'plugin_sha256':hashlib.sha256(plugin.read_bytes()).hexdigest(),
        'actual_hp_changes':drops,'contact_shells':sorted(contacts),'rank_fixture':d.get('rank_fixture',3),
        'observed_hp_update_count':len(delayed),'delayed_total_damage':total,'damage_per_contact':per_contact,
        'damage_attribution':'seven separate HP updates' if len(delayed)==7 else 'merged uniform HP updates',
        'contact_interval':[first_shell,last_contact],'attributed_hp_changes':delayed,
        'last_hp_commit_after_contact_seconds':delayed[-1]['time']-last_contact,
        'post_contact_attribution_bound_seconds':.5,
        'native_element_part_scales':scales,
        'primary_hitstop_zero':bool(primary_samples and all('hitstop' in r and max(r['hitstop'])==0 for r in primary_samples)),
        'primary_clock':d.get('primary_clock',[]),'tail_fallback_exercised':bool(d.get('primary_limit_fixture')),
        'duplicate_attempts_suppressed':d.get('duplicate_attempts_suppressed',[]),
        'helm_burst_events':d.get('helm_burst_events'),
        'max_native_simulation_step':max(r['dt']for r in d['rows']),
        'fixture':'Copied save, native area load; explicit rank/HP/position setup and forced monster action.',
        'limits':['This verifies seven native damage contacts and corresponding total HP loss in this tier/fixture.',
                  'Multiple damage events may share one polling sample; sample count is reported separately.',
                  'It does not certify original trajectory, counter timing, all tiers, or natural combat coverage.']}
    (run/(Path(input_name).stem+'_seven_hit_report.json')).write_text(json.dumps(report,indent=2))
    (PROJECT/'research/world_seven_hit_acceptance.json').write_text(json.dumps(report,indent=2))
    print(report['status'],[r['damage'] for r in delayed])

if __name__=='__main__':main()
