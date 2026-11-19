"""Resolve every EPV sound stem; retain stop actions and inherited controls.

No source request is assumed to be a runtime cue just because it is present in
the bank. Activation conditions, EPV provider selection and stop handles need
their own runtime binding. Game bytes remain in the private cache.
"""
import json,xml.etree.ElementTree as ET
from animation_port import ROOT,PROJECT,sha
from inspect_world_weapon_audio import field,properties

def main():
    source=json.loads((PROJECT/'research/world_audio_source.json').read_text(encoding='utf8'))
    native=json.loads((PROJECT/'research/world_audio_native.json').read_text(encoding='utf8'))
    cache=ROOT/'.cache/mhw_ls_presentation';nodes={}
    roots=ET.fromstring('<banks>'+(cache/'audio/banks.xml').read_text(encoding='utf8')+'</banks>')
    for root in roots:
        assert not list(root.iter('error'))
        for node in root.iter('object'):
            ident=next((f for f in node.findall('field')if f.get('name')=='ulID'),None)
            if ident is not None:nodes[root.get('filename'),int(ident.get('value'))]=node
    requests=native['wwev']['hm_wp03_epvsp_snd_ev']['rows'];speakers={s['id']:s for s in native['speakers']}
    stems=[];stops=[]
    for row in source['links']:
        bindings=[r for r in requests if r['event']==row['event']and r['request']==row['request']]
        assert len(bindings)==1;binding=bindings[0]
        assert binding['switch_count']==binding['rtpc_count']==0
        event=row['graph'];assert len(event['children'])==1;action=event['children'][0]
        if action['class']!='CAkActionPlay':
            assert action.get('play')is False
            stop=nodes['wp03_swo_epvsp.nbnk',action['id']]
            prop,_=properties(stop)
            stops.append({'request':row['request'],'event':row['event'],'action':action,
                'target_node':field(stop,'idExt'),'action_type':field(stop,'ulActionType'),
                'transition_ms':prop.get(16,0),'fade_curve':field(stop,'eFadeCurve'),'binding':binding})
            continue
        assert len(action['children'])==1;container=action['children'][0]
        assert len(container['children'])==1;leaf=container['children'][0]
        assert leaf['class']=='CAkSound'and len(leaf['media'])==1
        ident=leaf['id'];chain=[];gain=delay=pitch=0;bus=0;dynamic=[]
        while ident:
            node=nodes['wp03_swo_epvsp.nbnk',ident];p,ranges=properties(node)
            chain.append({'id':ident,'class':node.get('name'),'properties':p,'ranges':ranges})
            gain+=p.get(0,0);delay+=p.get(59,0);pitch+=p.get(2,0)
            if ranges:dynamic.append({'node':ident,'ranges':ranges})
            if not bus:bus=field(node,'OverrideBusId')
            ident=field(node,'DirectParentID')
        buses=[]
        while bus:
            node=nodes['Init.nbnk',bus];p,ranges=properties(node)
            buses.append({'id':bus,'properties':p,'ranges':ranges});gain+=p.get(0,0)+p.get(5,0)
            bus=field(node,'OverrideBusId')
        speaker=binding['speaker_id']
        assert speaker==-1 or speakers[speaker]['kind']==3
        stems.append({'source_request':row['request'],'event':row['event'],'media':leaf['media'][0],
            'speaker_id':speaker,'speaker_position':speakers[speaker]['position']if speaker>=0 else[0,0,0],
            'speaker_kind':3 if speaker>=0 else'no_override','static_gain_db':gain,'delay_seconds':delay,
            'pitch_cents':pitch,'dynamic_ranges':dynamic,'node_chain':chain,'bus_chain':buses,
            'binding':binding})
    result={'status':'FULL_EPV_SOURCE_STEMS_RESOLVED_RUNTIME_BINDINGS_PENDING',
        'source_report_sha256':sha(PROJECT/'research/world_audio_source.json'),
        'stems':stems,'stop_requests':stops,'media':sorted({s['media']for s in stems}),
        'limits':['Bank presence does not establish move trigger conditions.',
            'Preserve different EPV providers with overlapping WorkNo IDs.',
            'Wwise dynamic RTPC, attenuation and bus state remain pending.'],
        'runtime_verified':False,'installed':False}
    (PROJECT/'research/world_full_audio_native.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'stems':len(stems),'media':len(result['media']),
        'stop_requests':[r['request']for r in stops],
        'static_rows':[{'request':s['source_request'],'media':s['media'],'speaker':s['speaker_id'],
            'gain_db':s['static_gain_db'],'delay':s['delay_seconds'],'ranges':s['dynamic_ranges']}for s in stems]}))

if __name__=='__main__':main()
