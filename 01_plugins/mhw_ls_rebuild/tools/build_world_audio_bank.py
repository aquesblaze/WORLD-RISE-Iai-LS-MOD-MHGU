"""Build the private GU bank from codec-checked World media and source gain.

Native overlap groups are separate per request so paired Iai and weapon cues
can coexist. Source event selection/delays are emitted into the runtime header;
the native GU mixer, distance curves and voice lifecycle remain in use.
"""
import argparse,json,struct,sys,zlib
from animation_port import ROOT,PROJECT,sha
from prepare_world_audio import AUDIO

BANK='sound/se/pl/wp/swo/world/snd_world'
ARC='arc/forge/world_audio'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--weapon',action='store_true')
    ap.add_argument('--conditional',action='store_true')
    ap.add_argument('--iai-gain-db',type=float,default=0,help='Explicit GU mixer compensation for the six Iai stems; source gain is retained separately')
    ap.add_argument('--sheathe-gain-db',type=float,default=9,help='GU mixer trim for the three special-sheathe stems together')
    ap.add_argument('--private-gain-db',type=float,default=6.0,help='Final gain in dB for this private bank only')
    ap.add_argument('--ground',action='store_true',help='Build expanded World ground weapon and EPV requests')
    args=ap.parse_args()
    if args.ground:
        args.weapon=args.conditional=True
    assert 0<=args.private_gain_db<=6
    assert 0<=args.iai_gain_db<=12
    assert 0<=args.sheathe_gain_db<=12
    report=json.loads((PROJECT/'research/world_audio_conversion.json').read_text(encoding='utf8'))
    source=json.loads((PROJECT/'research/world_audio_native.json').read_text(encoding='utf8'))
    stems={r['media']:r for r in source['iai_stems']}
    template=ROOT/'Windows-MHGURecomp/data/romfs/nativeNX/arc/weapon/w07/snd/mat.arc'
    sys.path.insert(0,str(ROOT/'06_tools'))
    from arc_tool import read_entries,unpack_one
    data,_,table=read_entries(template)
    def resource(kind):
        return unpack_one(data,next(e for e in table if e['hash']==kind and e['name'].replace('\\','/').endswith('/snd_wp_swo_com')))[0]
    bank=resource(0x15d782fb);request=resource(0x1bcc4966)
    assert struct.unpack_from('<4s4I',bank)==(b'SBKR',4,1,8,1)
    assert struct.unpack_from('<HHII',bank,20)==(0,0x810,0,0)
    p=32;end=bank.index(0,p)
    assert bank[p:end].endswith(b'swo_grd_imp')
    assert struct.unpack_from('<I',bank,end+1)[0]==0x79c47b59
    params=bank[end+5:end+81]
    assert params[71:75]==bytes([61,61,61,0])
    request_template=bytearray(request[52+132*3:52+132*4])
    assert request_template[:4]==bytes([61,0,61,127]) and struct.unpack_from('<I',request_template,84)[0]==0
    media=report['media'];requests=[];groups=[];choices=[]
    for i,m in enumerate(media):
        s=stems[m['media']]
        m.update(request_id=i,native_probe_key=61+i,source_event=s)
        requests.append({'request_id':i,'media':m['media'],'source_request':s['source_request'],
            'source_gain_db':s['static_gain_db'],'mixer_compensation_db':args.iai_gain_db,
            'gain_db':s['static_gain_db']+args.iai_gain_db,'pitch_cents_min':0,'pitch_cents_max':0,'delay':s['delay_seconds']})
    if args.weapon:
        weapon=json.loads((PROJECT/'research'/('world_ground_weapon_audio.json' if args.ground else 'world_weapon_audio.json')).read_text(encoding='utf8'))
        spatial=json.loads((PROJECT/'research/world_audio_spatial_source.json').read_text(encoding='utf8'))
        assert spatial['status']=='SOURCE_WEAPON_AUDIO_ANCHORS_RESOLVED'
        converted=json.loads((PROJECT/'research'/('world_ground_weapon_audio_conversion.json' if args.ground else 'world_weapon_audio_conversion.json')).read_text(encoding='utf8'))
        assert not weapon['missing_media'] and weapon['baseline']=={'model':1,'parts':0}
        assert converted['source_report_sha256']==sha(PROJECT/'research'/('world_ground_weapon_audio.json' if args.ground else 'world_weapon_audio.json'))
        nonzero={m['media']:m for m in converted['media'] if not m['silent']}
        media+=list(nonzero.values());leaf_requests={}
        for leaf in weapon['leaves'].values():
            assert len(leaf['media'])==1
            ident=leaf['media'][0]
            if ident not in nonzero:continue # proven digital-silence optional-part branch
            chain=leaf['node_chain'];buses=leaf['bus_chain']
            gain=sum(n['properties'].get('0',0) for n in chain+buses)+sum(n['properties'].get('5',0) for n in buses)
            delay=sum(n['properties'].get('59',0) for n in chain)
            pitch=sum(n['properties'].get('2',0) for n in chain)
            ranges=[n['ranges']['2'] for n in chain if '2' in n['ranges']]
            assert len(ranges)==1 and ranges[0]==[-50,50] and pitch==0
            assert all(set(n['ranges'])<={'2'} for n in chain)
            ident_request=len(requests);leaf_requests[leaf['id']]=ident_request
            requests.append({'request_id':ident_request,'media':ident,'source_leaf':leaf['id'],
                'gain_db':gain,'pitch_cents_min':-50,'pitch_cents_max':50,'delay':delay})
        for row in weapon['rows']:
            graph=row['graph']
            while graph['class']!='CAkRanSeqCntr':
                assert len(graph['children'])==1
                graph=graph['children'][0]
            assert all(c['class']=='CAkSound' for c in graph['children'])
            cfg=graph['random']
            assert cfg=={'eMode':0,'eRandomMode':0,'bIsGlobal':1,'bIsContinuous':0,'sLoopCount':1,'wAvoidRepeatCount':1,'_bIsUsingWeight':0}
            selected=[leaf_requests[c['id']] for c in graph['children'] if c['id'] in leaf_requests]
            if not selected:continue
            assert len(selected)==len(graph['children']) # no silent choice removed from a mixed random group
            delays={requests[i]['delay'] for i in selected};assert len(delays)==1
            groups.append({'source_request':row['request'],'container':graph['id'],'offset':len(choices),
                'count':len(selected),'bone':row['bone'],'delay':delays.pop(),'requests':selected,
                'root_position':spatial['anchors'][str(row['bone'])]['root_position']})
            choices+=selected
    conditional_first=len(requests)
    extra_stems=[]
    wave_paths={}
    if args.ground:
        wave_paths.update({m['media']:AUDIO/'gu_ground'/f"{m['media']}.wave" for m in nonzero.values()})
        converted=json.loads((PROJECT/'research/world_full_audio_conversion.json').read_text())
        full=json.loads((PROJECT/'research/world_full_audio_native.json').read_text())
        # Claw-only requests are outside the Guild ground moveset.
        extra=[s for s in full['stems'] if s['source_request'] not in (25601,25602,25603,25611,25612)]
        known={m['media'] for m in media}
        for m in converted['media']:
            if m['media'] not in known and any(s['media']==m['media'] for s in extra):
                media.append(m)
                wave_paths[m['media']]=AUDIO/'gu_full'/f"{m['media']}.wave"
        for stem in extra:
            ident=len(requests)
            pitch=[r['ranges']['2'] for r in stem['dynamic_ranges']]
            lo,hi=pitch[0] if pitch else (0,0)
            # These private EPV layers compete with the monster's close attack
            # in the GU mix. Keep both stereo stems and their offsets together.
            trim={25505:17,25510:21,25604:args.sheathe_gain_db,25605:16,25606:15}.get(stem['source_request'],0)
            requests.append(dict(request_id=ident,media=stem['media'],source_request=stem['source_request'],
                gain_db=stem['static_gain_db']+trim,source_gain_db=stem['static_gain_db'],mixer_compensation_db=trim,
                pitch_cents=int(stem['pitch_cents']),delay=stem['delay_seconds'],
                pitch_cents_min=int(lo),pitch_cents_max=int(hi)))
            extra_stems.append(dict(stem,request_id=ident))
    elif args.conditional:
        converted=json.loads((PROJECT/'research/world_conditional_audio_conversion.json').read_text(encoding='utf8'))
        extra=source['conditional_stems'];known={m['media'] for m in media}
        media += [m for m in converted['media'] if m['media'] not in known]
        for s in extra:
            ident=len(requests)
            requests.append({'request_id':ident,'media':s['media'],'source_request':s['source_request'],
                'source_gain_db':s['static_gain_db'],'mixer_compensation_db':0,
                'gain_db':s['static_gain_db'],'pitch_cents_min':0,'pitch_cents_max':0,'delay':s['delay_seconds']})
            extra_stems.append(dict(s,request_id=ident))
    count=len(media);entries=[];bank_parts=[];request_rows=[]
    assert count<=67 and len({m['media'] for m in media})==count
    keys={m['media']:61+i for i,m in enumerate(media)}
    for i,m in enumerate(media):
        path=m['resource_path'].replace('/','\\');wave=wave_paths.get(m['media'],AUDIO/'gu'/f"{m['media']}.wave")
        assert sha(wave)==m['wave_sha256']
        entries.append((path,0x79c47b59,wave.read_bytes()))
        param=bytearray(params);param[71:74]=bytes([61+i]*3)
        ranges={(r['pitch_cents_min'],r['pitch_cents_max']) for r in requests if r['media']==m['media']}
        assert len(ranges)==1
        lo,hi=ranges.pop()
        # SBKR runtime voice is the serialized76-byte parameter block+8.
        # BE598C reads flags+9 bit2 and signed halfwords+20/+22/+24:
        # base + min + (max-min)*U32/2^32. SRQR+48 is a start delay!
        param[1]=1|(4 if lo!=hi else 0) # fixed note; no inherited GU ADSR/pan/volume randomizers
        param[5]=127 # full bank voice level; request owns source static gain
        struct.pack_into('<3hH',param,12,lo if lo==hi else 0,lo,hi,0)
        bank_parts.append(path.encode()+b'\0'+struct.pack('<I',0x79c47b59)+param)
        m['native_probe_key']=61+i
    helm_weapon=set(next(g['requests'] for g in groups if g['source_request']==5790)) if args.ground else set()
    for request_info in requests:
        helm_hit=request_info.get('source_request')==25530 or request_info['request_id'] in helm_weapon
        if args.ground and helm_hit:
            # One sustained onset covers all seven delayed hits. Apply the
            # combat mix trim only to this cue, including its weapon layer.
            request_info['source_gain_db']=request_info['gain_db']
            trim=23 if request_info.get('source_request')==25530 else 15
            request_info['mixer_compensation_db']=trim
            request_info['gain_db']+=trim
        request_info['gain_db']+=args.private_gain_db
        r=bytearray(request_template);struct.pack_into('<H',r,0,request_info['request_id']);r[2]=keys[request_info['media']]
        # SRQR+44 is constant pitch; +48 is start delay (BE6450), not a
        # random range. Source delay is already scheduled on simulation time.
        struct.pack_into('<2i',r,44,request_info.get('pitch_cents',0),0)
        struct.pack_into('<2f',r,36,request_info['gain_db'],request_info['gain_db'])
        # BF3050 counts voices with BF3F18 using SRQR+14/+16/+18 and
        # owner/bank, NOT the request ID. The copied impact row caps this
        # group at2 voices (+24); sharing it across all32 requests drops
        # paired Iai stems whenever the preceding weapon cues are active.
        # Give every request its own group; preserve the native per-request
        # overlap cap, priority, distance curves and source gain/timing.
        struct.pack_into('<h',r,14,0x300+request_info['request_id'])
        if args.ground and helm_hit:
            r[20]=120  # GU sword-bank priority for the delayed Helm cue.
        request_info['voice_limit']=r[24]
        request_rows.append(r)
    # The native LS bank's final group contributes another -4dB. Use unity
    # here so the request applies the World hierarchy's dry gain exactly once.
    bank_group=struct.pack('<f',1.0)+bank[-4:]
    assert struct.unpack_from('<h',bank_group,6)[0]==0
    bank_new=struct.pack('<4s4IHHII',b'SBKR',4,1,count,1,0,0x800+2*count,0,0)+b''.join(bank_parts)+bank_group
    stab=52+132*len(requests);name=BANK.replace('/','\\').encode()+b'\0'
    end=(stab+4+len(name)+15)&~15
    req=struct.pack('<4s7I5I',b'SRQR',5,len(requests),0,0,0,0,0x0291df77,stab,end,end,end,end)
    req+=b''.join(request_rows)+struct.pack('<I',stab+4)+name;req+=bytes(end-len(req))
    entries += [(BANK.replace('/','\\'),0x15d782fb,bank_new),(BANK.replace('/','\\'),0x1bcc4966,req)]
    header=struct.pack('<4sHHI',b'ARC\0',17,len(entries),0);table=[];payload=[];offset=12+80*len(entries)
    for path,kind,raw in entries:
        assert len(path.encode())<64
        blob=zlib.compress(raw,9);table.append(struct.pack('<64s4I',path.encode(),kind,len(blob),len(raw)|0x40000000,offset))
        payload.append(blob);offset+=len(blob)
    target=ROOT/'.cache/mhw_ls_combat/mods/MHW_WORLD_DEV/romfs/nativeNX'/f'{ARC}.arc'
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(header+b''.join(table)+b''.join(payload))
    packed,version,parsed=read_entries(target)
    assert version==17 and len(parsed)==len(entries)
    for actual,expected in zip(parsed,entries):assert unpack_one(packed,actual)[0]==expected[2]
    result={'status':'PRIVATE_GU_AUDIO_BANK_BUILT','arc':str(target),'arc_sha256':sha(target),
            'private_gain_db':args.private_gain_db,'bank':BANK,'media':media,'requests':requests,'weapon_groups':groups,'iai_mixer_compensation_db':args.iai_gain_db,
            'weapon_baseline':{'model':1,'parts':0} if args.weapon else None,
            'sheathe_mixer_compensation_db':args.sheathe_gain_db if args.ground else 0,
            'probe_settings':'SBKR carries pitch variation. SRQR carries static pitch and gain. Stem delays use the simulation clock. Iai and special-sheathe gain trims are recorded per request.',
            'installed':False,'runtime_playback_verified':False}
    (PROJECT/'research/world_audio_bank.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    def cfloat(n):return f'{float(n):.9f}f'
    generated=['/* Generated by build_world_audio_bank.py from local source evidence. */',
        f'#define WORLD_AUDIO_RESOURCE_COUNT {len(entries)}u',f'#define WORLD_AUDIO_REQUEST_COUNT {len(requests)}u',
        f'#define WORLD_AUDIO_WEAPON {int(args.weapon)}',
        f'#define WORLD_AUDIO_GROUND {int(args.ground)}',
        f'#define WORLD_AUDIO_CONDITIONAL_FIRST {conditional_first}u',
        'typedef struct {unsigned request,source_request;float delay,x,y,z;} WAudioStem;',
        'static const WAudioStem world_audio_stems[]={']
    for m in media[:6]:
        s=stems[m['media']]
        generated.append('{%d,%d,%s,%s},'%(m['request_id'],s['source_request'],cfloat(s['delay_seconds']),','.join(map(cfloat,s['speaker_position']))))
    if args.conditional:
        for s in extra_stems:
            generated.append('{%d,%d,%s,%s},'%(s['request_id'],s['source_request'],cfloat(s['delay_seconds']),','.join(map(cfloat,s['speaker_position']))))
    generated+=['};','typedef struct {unsigned source;float frame;unsigned request,work;} WAudioCue;',
        'static const WAudioCue world_audio_cues[]={']
    for c in source['iai_cues']:generated.append('{%d,%s,%d,%d},'%(c['source'],cfloat(c['frame']),c['request'],c['work']))
    if args.conditional:
        # BackStepAttack init owns2007. PlMotionVisual trigger bit3 at84
        # calls2123cd0->ae0f30->group2005/record0 for white+ FinishStep.
        generated+=['{140,0.0f,25606,2007},','{170,84.0f,25515,2005},']
    if args.ground:
        generated+=['{306,74.0f,25604,3000},','{170,10.0f,25525,2010},']
    if args.weapon:
        cues=json.loads((PROJECT/'research'/('world_ground_motion_audio.json' if args.ground else 'world_motion_audio.json')).read_text(encoding='utf8'))['weapon_one_shots']
        if args.ground:
            cues=[c for c in cues if c['target_unit']==1]
        assert sum(c['source']==312 for c in cues)==3
        for c in sorted(cues,key=lambda c:(c['source'],c['frame'],c['track'],c['channel'])):
            generated.append('{%d,%s,%d,0},'%(c['source'],cfloat(c['frame']),c['request']))
    generated+=['};','#define WORLD_AUDIO_CUE_COUNT (sizeof(world_audio_cues)/sizeof(*world_audio_cues))','']
    if args.weapon:
        generated+=['typedef struct {unsigned source_request,offset,count;int bone;float delay;} WAudioWeaponGroup;',
                    'static const WAudioWeaponGroup world_audio_weapon_groups[]={']
        for g in groups:generated.append('{%d,%d,%d,%d,%s},'%(g['source_request'],g['offset'],g['count'],g['bone'],cfloat(g['delay'])))
        generated+=['};','static const unsigned world_audio_weapon_choices[]={'+','.join(map(str,choices))+'};',
            '#define WORLD_AUDIO_WEAPON_GROUP_COUNT (sizeof(world_audio_weapon_groups)/sizeof(*world_audio_weapon_groups))','']
        if args.ground:
            helm=next(g for g in groups if g['source_request']==5790)
            assert helm['count']==1
            generated.append('#define WORLD_AUDIO_HELM_WAVE %du' % helm['requests'][0])
        positions={}
        for g in groups:
            for request_id in g['requests']:
                assert request_id not in positions or positions[request_id]==g['root_position']
                positions[request_id]=g['root_position']
        generated+=['static const float world_audio_weapon_points[WORLD_AUDIO_REQUEST_COUNT][3]={']
        for request_info in requests:
            generated.append('{'+','.join(map(cfloat,positions.get(request_info['request_id'],[0,0,0])))+'},')
        generated+=['};','']
    (PROJECT/'c/world_audio_events.h').write_text('\n'.join(generated),encoding='ascii')
    print(result['status'],len(entries),'resources',sha(target))

if __name__=='__main__':main()
