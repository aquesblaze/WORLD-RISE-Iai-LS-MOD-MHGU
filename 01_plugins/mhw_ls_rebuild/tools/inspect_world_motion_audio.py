"""Inventory actual Wwise timeline keys and weapon request routing.

No assumption that similarly numbered EventGroup tracks select a WWEV bank:
they are concurrent timeline channels. WWCT resource indices are recorded
separately until the native dispatcher has been verified.
"""
import argparse,json,struct
from collections import Counter
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
from animation_port import ROOT,PROJECT,sha
from inspect_world_audio_native import wwev

CACHE=ROOT/'.cache/mhw_ls_presentation'
CLIPS=(140,170,171,172,173,174,306,307,308,309,310,311,312)

def wwct(path):
    data=path.read_bytes();magic,version,*counts=struct.unpack_from('<4s9I',data)
    assert (magic,version)==(b'WWCT',6)
    at=40;rows=[]
    # File count fields and serialized list order differ.
    for index,kind in ((2,'wwev'),(0,'wwbk'),(1,'wwpk'),(3,'wwsw'),
                       (4,'wwst'),(5,'wwgp'),(6,'wwenf'),(7,'unknown')):
        for _ in range(counts[index]):
            ident=struct.unpack_from('<I',data,at)[0];at+=4
            end=data.index(0,at);name=data[at:end].decode('ascii');at=end+1
            rows.append({'kind':kind,'index':ident,'path':name.replace('\\','/')})
    assert at==len(data)
    return {'sha256':sha(path),'rows':rows}

def sample(keys,frame,default=None):
    return next((value for t,value in reversed(keys) if t<=frame),default)

def main():
    text=(ROOT/'.cache/mhw_native/text.bin').read_bytes();cs=Cs(CS_ARCH_X86,CS_MODE_64)
    code=list(cs.disasm(text[0x130b500-0x1000:0x130b59d-0x1000],0x14130b500))
    instructions={i.address-0x140000000:(i.mnemonic,i.op_str) for i in code}
    assert instructions[0x130b547]==('test','dword ptr [rdi + rax*4 + 0x28], ebx')
    assert instructions[0x130b54d]==('mov','r8d, dword ptr [rdi + 0x80]')
    assert instructions[0x130b557]==('mov','edx, dword ptr [r14]')
    assert instructions[0x130b562]==('call','0x14130b960')
    assert instructions[0x130b56a]==('rol','ebx, 1')
    combat=json.loads((PROJECT/'research/world_combat_source.json').read_text(encoding='utf8'))
    parser=argparse.ArgumentParser();parser.add_argument('--ground',action='store_true')
    ground=parser.parse_args().ground
    clips=sorted(map(int,combat['clips'])) if ground else CLIPS
    events=[];other=[]
    for source in clips:
        for event in combat['clips'][str(source)]['raw_events']:
            if 'WwiseTimeline::' not in event['type']:continue
            tracks={t['name']:t['keys'] for t in event['tracks']}
            if '::EventGroup' not in event['type']:
                other.append({'source':source,**event});continue
            for frame,mask in tracks.get('mTrigger',[]):
                assert mask<256,'Native EventGroup has8 channels'
                for index in range(8):
                    if not mask&(1<<index):continue
                    key='ReqNo '+chr(65+index)
                    request=sample(tracks.get(key,[]),frame)
                    # Unkeyed native channels retain their object default. Keep
                    # the absent request explicit rather than guessing an event.
                    events.append({'source':source,'track':event['type'],'frame':frame,
                        'channel':index,'request':request,
                        'target_unit':sample(tracks.get('TargetUnitNo',[]),frame)})
    controller={name:wwct(CACHE/'source/sound/pl'/f'{name}.wwct')
                for name in ('hm_cmn_snd_ct','pl_cmn_snd_ct')}
    weapon=wwev(CACHE/'source/sound/pl/hm_wp03_snd_ev.wwev')
    weapon_ids={r['request'] for r in weapon['rows']}
    weapon_events=[e for e in events if e['request'] in weapon_ids]
    used=sorted({e['request'] for e in weapon_events})
    report={'status':'SOURCE_MOTION_AUDIO_TIMELINE_INVENTORY','clips':clips,
        'controller_resources':controller,'one_shots':events,'other_tracks':other,
        'weapon_one_shots':weapon_events,'weapon_requests':used,
        'weapon_rows':[r for r in weapon['rows'] if r['request'] in used],
        'native_dispatch':{'function':'0x130b500','semantics':'Eight trigger bits at+28 select request words+60; target unit+80 and request are passed to130b960. Group tracks share this dispatcher.',
                           'instructions':[f'{i.address-0x140000000:x} {i.mnemonic} {i.op_str}' for i in code]},
        'limits':['Timeline channels verified against native dispatcher. Continuous loop/collision dispatch is separate.',
                  'Weapon model/optional-part switches9..12 select Wwise branches. Common media are not the complete weapon bank.',
                  'Collision footsteps, voice, equipment, loops and game-parameter automation remain distinct from weapon one-shots.']}
    output='world_ground_motion_audio.json' if ground else 'world_motion_audio.json'
    (PROJECT/'research'/output).write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(report['status'],len(events),'one-shots;',len(weapon_events),'weapon cues;',len(used),'weapon requests')
    print('Weapon requests',used)
    for source in clips:
        print(source,[(e['frame'],e['request']) for e in weapon_events if e['source']==source])

if __name__=='__main__':main()
