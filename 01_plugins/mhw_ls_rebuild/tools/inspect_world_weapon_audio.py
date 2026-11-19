"""Resolve selected weapon-model Wwise branches, preserving random containers.

Model1/parts0 is the explicit World baseline for the conversion experiment;
it is not an asserted mapping for every GU weapon model.
"""
import argparse,json,struct,xml.etree.ElementTree as ET
from collections import Counter
from animation_port import ROOT,PROJECT,sha
from inspect_world_audio import fields,chunks
from inspect_world_audio_native import wwev

CACHE=ROOT/'.cache/mhw_ls_presentation'
AUDIO=CACHE/'audio'

def field(node,name,default=0):
    found=fields(node,name)
    return int(found[0].get('value')) if found else default

def properties(node):
    values={};ranges={}
    for obj in node.iter('object'):
        if obj.get('name')!='AkPropBundle':continue
        p={f.get('name'):f.get('value') for f in obj.findall('field')}
        if 'pID' not in p:continue
        ident=int(p['pID'])
        if 'pValue' in p:values[ident]=float(p['pValue'])
        elif 'min' in p:ranges[ident]=[float(p['min']),float(p['max'])]
        else:raise ValueError(p)
    return values,ranges

def switch(path):
    data=path.read_bytes();magic,version,count,*rest=struct.unpack_from('<4s6I',data)
    assert (magic,version)==(b'WWSW',3) and len(data)==28+8*count
    rows=dict(struct.unpack_from('<2I',data,28+8*i) for i in range(count))
    return {'group':rest[-1],'rows':rows,'sha256':sha(path)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--model',type=int,default=1);ap.add_argument('--parts',type=int,default=0)
    ap.add_argument('--ground',action='store_true')
    args=ap.parse_args()
    roots=ET.fromstring('<banks>'+(AUDIO/'banks.xml').read_text(encoding='utf8')+'</banks>')
    roots.append(ET.parse(AUDIO/'weapon_structure.xml').getroot())
    nodes={};bank_ids={}
    for root in roots:
        bank=root.get('filename');assert not list(root.iter('error'))
        bank_ids[bank]=field(root,'dwSoundBankID')
        for node in root.iter('object'):
            ident=next((f for f in node.findall('field') if f.get('name')=='ulID'),None)
            if ident is not None:nodes[bank,int(ident.get('value'))]=node
    media={}
    for name in (f'wp_swo_{args.model:03d}','wp_swo_cmn'):
        path=CACHE/'source/sound/wwise/Windows'/f'{name}.nbnk';data=chunks(path.read_bytes())
        for at in range(0,len(data.get(b'DIDX',b'')),12):
            ident,offset,size=struct.unpack_from('<3I',data[b'DIDX'],at);raw=data[b'DATA'][offset:offset+size]
            assert len(raw)==size
            out=AUDIO/'wem'/f'{ident}.wem';out.write_bytes(raw)
            media[ident]={'bank':path.name,'bytes':size,'sha256':sha(out)}
    switches={};switch_sources={}
    for part,selected in (('model',args.model),('op_parts',args.parts)):
        for owner in ('hm','wp'):
            name=f'pl_weapon_{part}_type_{owner}'
            s=switch(CACHE/'source/sound/pl/wwsw'/f'{name}.wwsw')
            assert selected in s['rows'];s['selected_index']=selected;s['selected_value']=s['rows'][selected]
            assert s['group'] not in switches or switches[s['group']]==s['selected_value']
            switches[s['group']]=s['selected_value'];switch_sources[name]=s
    def resolve(ident,bank=None):
        if (bank,ident) in nodes:return bank,nodes[bank,ident]
        matches=[(b,n) for (b,i),n in nodes.items() if i==ident]
        assert len(matches)==1,(ident,[b for b,n in matches])
        return matches[0]
    def walk(ident,bank=None,seen=()):
        assert ident not in seen
        bank,node=resolve(ident,bank);kind=node.get('name');prop,ranges=properties(node)
        result={'id':ident,'bank':bank,'class':kind,'properties':prop,'ranges':ranges}
        refs=[]
        if kind=='CAkEvent':refs=[int(f.get('value')) for f in fields(node,'ulActionID')]
        elif kind=='CAkActionPlay':refs=[field(node,'idExt')]
        elif kind=='CAkSwitchCntr':
            group=field(node,'ulGroupID');selected=switches[group]
            result.update(group=group,selected=selected)
            packages=[n for n in node.iter('object') if n.get('name')=='CAkSwitchPackage' and field(n,'ulSwitchID')==selected]
            if not packages:
                selected=field(node,'ulDefaultSwitch');result['fallback']=selected
                packages=[n for n in node.iter('object') if n.get('name')=='CAkSwitchPackage' and field(n,'ulSwitchID')==selected]
            assert len(packages)<=1
            refs=[int(f.get('value')) for p in packages for f in fields(p,'NodeID')]
        elif kind=='CAkRanSeqCntr':
            refs=[int(f.get('value')) for f in fields(node,'ulChildID')]
            result['random']={name:field(node,name) for name in ('eMode','eRandomMode','bIsGlobal','bIsContinuous',
                'sLoopCount','wAvoidRepeatCount','_bIsUsingWeight')}
            result['playlist']=[{name:field(p,name) for name in ('ulPlayID','weight')}
                for p in node.iter('object') if p.get('name')=='AkPlaylistItem']
        elif kind=='CAkSound':
            result['media']=[int(f.get('value')) for f in fields(node,'sourceID')]
            return result
        else:raise ValueError((ident,kind))
        result['children']=[walk(i,bank,(*seen,ident)) for i in refs]
        result['media']=sorted({m for c in result['children'] for m in c['media']})
        return result
    def ancestry(sound,bank):
        ident=sound;chain=[];bus=0;seen=set()
        while ident:
            assert ident not in seen;seen.add(ident);bank,node=resolve(ident,bank);p,r=properties(node)
            chain.append({'id':ident,'bank':bank,'class':node.get('name'),'properties':p,'ranges':r,
                'rtpcs':[[{f.get('name'):f.get('value') for f in o.findall('field')} for o in n.iter('object')]
                    for n in node.iter('object') if n.get('name')=='InitialRTPC' and field(n,'ulNumRTPC')],
                'attenuation':field(node,'uAttenuationID')})
            if not bus:bus=field(node,'OverrideBusId')
            ident=field(node,'DirectParentID')
        buses=[]
        while bus:
            b,node=resolve(bus,'Init.nbnk');p,r=properties(node)
            buses.append({'id':bus,'properties':p,'ranges':r});bus=field(node,'OverrideBusId')
        return {'node_chain':chain,'bus_chain':buses}
    inventory=json.loads((PROJECT/'research'/('world_ground_motion_audio.json' if args.ground else 'world_motion_audio.json')).read_text(encoding='utf8'))
    rows=[];leaves={}
    def gather(graph):
        if graph['class']=='CAkSound':leaves[graph['id']]=graph
        for c in graph.get('children',[]):gather(c)
    bindings=inventory['weapon_rows']
    if args.ground:
        bindings=wwev(CACHE/'source/sound/pl/hm_wp03_snd_ev.wwev')['rows']
    for row in bindings:
        graph=walk(row['event'])
        if row not in inventory['weapon_rows'] and not {28799224,664717410}.intersection(graph['media']):
            continue
        rows.append({**row,'graph':graph});gather(graph)
    for leaf in leaves.values():leaf.update(ancestry(leaf['id'],leaf['bank']))
    used=sorted({m for row in rows for m in row['graph']['media']});missing=[m for m in used if m not in media]
    result={'status':'SOURCE_WEAPON_AUDIO_BRANCHES_RESOLVED','baseline':{'model':args.model,'parts':args.parts},
        'switches':switch_sources,'rows':rows,'leaves':leaves,'media':{m:media.get(m) for m in used},'missing_media':missing,
        'source_banks':{b:sha(CACHE/'source/sound/wwise/Windows'/b) for b in bank_ids},
        'limits':'Typed source branch selection; native trigger dispatch, GU weapon mapping, random-container playback and dynamic processing pending.'}
    (PROJECT/'research'/('world_ground_weapon_audio.json' if args.ground else 'world_weapon_audio.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(result['status'],len(rows),'event rows;',len(leaves),'sound leaves;',len(used),'media; missing',missing)
    for row in rows:print(row['request'],row['event'],row['graph']['media'])

if __name__=='__main__':main()
