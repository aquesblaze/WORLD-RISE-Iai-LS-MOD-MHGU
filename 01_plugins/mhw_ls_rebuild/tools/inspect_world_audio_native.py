"""Resolve WWEV speaker fields and source Iai event timing from local assets/code."""
import json,struct,xml.etree.ElementTree as ET
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
from animation_port import ROOT,PROJECT,sha
from inspect_world_actions import BASE,TEXT,RDATA

CACHE=ROOT/'.cache/mhw_ls_presentation'

def wwev(path):
    data=path.read_bytes();magic,version,count,reserved=struct.unpack_from('<4s3I',data)
    assert (magic,version,reserved)==(b'WWEV',19,0)
    at=16;deps=[]
    for _ in range(4):
        end=data.index(0,at);deps.append(data[at:end].decode('ascii'));at=end+1
    rows=[]
    for i in range(count):
        start=at;raw=data[at:at+128];assert len(raw)==128;at+=128
        end=data.index(0,at);dep=data[at:end].decode('ascii');at=end+1
        rows.append({'index':i,'offset':start,'request':struct.unpack_from('<H',raw)[0],
            'bone':struct.unpack_from('<h',raw,2)[0],'event':struct.unpack_from('<I',raw,4)[0],
            'speaker_id':struct.unpack_from('<h',raw,18)[0],
            'switch_mask':list(raw[20:48]),'rtpc_mask':list(raw[48:68]),
            'switch_count':raw[68],'rtpc_count':raw[69],'extra_resource':dep})
    assert at==len(data),(path,at,len(data))
    return {'dependencies':deps,'rows':rows,'sha256':sha(path)}

def main():
    raw=(ROOT/'.cache/mhw_native/text.bin').read_bytes();cs=Cs(CS_ARCH_X86,CS_MODE_64);cs.detail=True
    def code(a,z):return [f'{i.address-BASE:x} {i.mnemonic} {i.op_str}' for i in cs.disasm(raw[a-TEXT:z-TEXT],BASE+a)]
    def require(at,mnemonic,operand):
        i=next(cs.disasm(raw[at-TEXT:at-TEXT+16],BASE+at));assert i.mnemonic==mnemonic and i.op_str==operand,(at,i.op_str)
    require(0x22ff086,'movzx','eax, word ptr [rsi + 0x12]')
    require(0x22ff08a,'mov','word ptr [rdi + 0x70], ax')
    require(0xf7a7c0,'mov','rax, qword ptr [rcx + 0xc0]')
    require(0x230d3e8,'movzx','r12d, word ptr [rsi + 0x70]')
    require(0x230d657,'call',hex(BASE+0x2582510))
    require(0x230d687,'call',hex(BASE+0x2582550))
    require(0x22fe725,'cmp','ecx, r14d')
    require(0x22fe750,'inc','ebx')
    assert struct.unpack_from('<I',raw,0x2583bd0-TEXT+3*4)[0]==0x25828c0
    lists={name:wwev(CACHE/'source/sound/pl'/f'{name}.wwev') for name in
           ('hm_wp03_epvsp_snd_ev','hm_wp_cmn_epvsp_snd_ev','hm_wp03_snd_ev')}
    speakers_path=CACHE/'source/sound/pl/wwspl/pl_speker_set.wwspl';sp=speakers_path.read_bytes()
    assert struct.unpack_from('<4s3I',sp)==(b'WSPL',3,16,0) and len(sp)==16+96*16
    speakers=[]
    for i in range(16):
        at=16+96*i;ident,kind,a,b=struct.unpack_from('<4I',sp,at)
        speakers.append({'id':ident,'kind':kind,'position':struct.unpack_from('<3f',sp,at+16),
                         'direction':struct.unpack_from('<3f',sp,at+32)})
    selected=[r for r in lists['hm_wp03_epvsp_snd_ev']['rows'] if 25601<=r['request']<=25603]
    assert [r['speaker_id'] for r in selected]==list(range(6))
    assert all(r['switch_count']==r['rtpc_count']==0 for r in selected)
    assert all(s['kind']==3 for s in speakers[:6])
    source_audio=json.loads((PROJECT/'research/world_audio_source.json').read_text(encoding='utf8'))
    roots=ET.fromstring('<banks>'+(CACHE/'audio/banks.xml').read_text(encoding='utf8')+'</banks>');nodes={}
    for root in roots:
        for node in root.iter('object'):
            ident=next((f for f in node.findall('field') if f.get('name')=='ulID'),None)
            if ident is not None:nodes[root.get('filename'),int(ident.get('value'))]=node
    def field(node,name):
        return next((int(f.get('value')) for f in node.iter('field') if f.get('name')==name),0)
    def props(node):
        result={}
        for obj in node.iter('object'):
            if obj.get('name')!='AkPropBundle':continue
            values={f.get('name'):f.get('value') for f in obj.findall('field')}
            if 'pID' in values and 'pValue' in values:result[int(values['pID'])]=float(values['pValue'])
        return result
    stems=[]
    conditional=[r for r in source_audio['links'] if r['request'] in (25515,25606)]
    for row in source_audio['selected_iai']+conditional:
        event=row['graph'];assert len(event['children'])==1
        action=event['children'][0];assert action['class']=='CAkActionPlay' and len(action['children'])==1
        container=action['children'][0];assert len(container['children'])==1
        sound=container['children'][0];assert sound['class']=='CAkSound' and len(sound['media'])==1
        ident=sound['id'];chain=[];gain=0;delay=0;bus=0
        while ident:
            node=nodes['wp03_swo_epvsp.nbnk',ident];p=props(node)
            assert p.get(2,0)==0,'Source pitch must be explicitly handled'
            chain.append({'id':ident,'class':node.get('name'),'properties':p})
            gain+=p.get(0,0);delay+=p.get(59,0)
            if not bus:bus=field(node,'OverrideBusId')
            ident=field(node,'DirectParentID')
        buses=[]
        while bus:
            node=nodes['Init.nbnk',bus];p=props(node)
            buses.append({'id':bus,'properties':p});gain+=p.get(0,0)+p.get(5,0)
            bus=field(node,'OverrideBusId')
        speaker=row['selector18_raw']
        stems.append({'source_request':row['request'],'event':row['event'],'media':sound['media'][0],
            'speaker_id':speaker,'speaker_position':speakers[speaker]['position'],'static_gain_db':gain,
            'delay_seconds':delay,'pitch':1,'node_chain':chain,'bus_chain':buses})
    assert [s['static_gain_db'] for s in stems[:6]]==[-4,-4,-5,-5,-3,-3]
    assert len(stems)==10
    presentation=json.loads((PROJECT/'research/world_presentation_map.json').read_text(encoding='utf8'))
    cues=[]
    for e in presentation['events']:
        for frame,on in e['enable_keys']:
            if not on:continue
            work=next((v for f,v in reversed(e['work_keys']) if f<=frame),None)
            if work not in (3014,3015,3016,3017):continue
            record=presentation['work_records'][str(work)];assert len(record)==1
            requests=record[0]['sound']['requests'];assert len(requests)==1
            cues.append({'source':e['source'],'channel':e['channel'],'frame':frame,'work':work,'request':requests[0]['request']})
    assert len(cues)==5
    report={'status':'SOURCE_IAI_AUDIO_SPEAKERS_AND_TIMELINE_RESOLVED','wwev':lists,
        'speakers_sha256':sha(speakers_path),'speakers':speakers,'iai_cues':cues,'iai_stems':stems[:6],
        'conditional_stems':stems[6:],
        'semantics':[
            'WWEV+0x12 is a WSPL speaker ID, not a material/variant selector. Loader24bde30 reads128-byte records plus a trailing resource string.',
            '22fe640 enumerates every matching request row and dispatches each; the two rows per Iai request play together.',
            '22ff086 copies speaker ID to runtime request70.230d3d7 resolves event-list+c0 to WSPL;2582510 resolves the speaker ID.',
            'WSPL kind3 uses25828c0: horizontal camera-to-owner bearing, rotated speaker offset, owner translation. It creates paired spatial sources.',
            'Iai selected rows have no WWEV switch/RTPC conditions. Wwise inherited bus/RTPC processing is a separate layer.'
        ],'evidence':{n:code(a,z) for n,(a,z) in {
            'loader_header':(0x24bde5d,0x24bde8b),'loader_row':(0x24be030,0x24be099),
            'all_matching_rows':(0x22fe713,0x22fe75b),'speaker_copy':(0x22ff07e,0x22ff092),
            'speaker_resource':(0xf7a7c0,0xf7a7c8),'speaker_lookup':(0x230d3ce,0x230d3f8),
            'speaker_evaluation':(0x230d650,0x230d68c),'speaker_index':(0x2582510,0x258254b),
            'kind3_position':(0x25828c0,0x2582a26)}.items()},
        'limits':'Typed source rules; native GU transport verified separately. Full Wwise spatial attenuation, dynamic RTPC/bus states and reverb are not yet reproduced.'}
    (PROJECT/'research/world_audio_native.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(report['status'],len(cues),'cues; six paired spatial stems')

if __name__=='__main__':main()
