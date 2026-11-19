"""Reproduce request -> Wwise event/action/container -> actual embedded media.

Use the external wwiser XML dump for typed bank fields. WWEV v19 links are
conservatively matched against known event IDs and its declared record count;
unknown condition fields are retained as evidence, not guessed as playback rules.
"""
import argparse,hashlib,json,re,struct,subprocess,sys,xml.etree.ElementTree as ET
from pathlib import Path
from animation_port import ROOT,PROJECT,sha

CACHE=ROOT/'.cache/mhw_ls_presentation'
AUDIO=CACHE/'audio'
TOOL=ROOT/'.cache/mhw_audio_tools'
BANKS=['Init','wp03_swo_epvsp','wp_swo_cmn']

def fields(node,name):return [f for f in node.iter('field') if f.get('name')==name]
def chunks(raw):
    pos=0;result={}
    while pos<len(raw):
        tag=raw[pos:pos+4];n=struct.unpack_from('<I',raw,pos+4)[0];assert tag not in result
        result[tag]=raw[pos+8:pos+8+n];assert len(result[tag])==n;pos+=8+n
    assert pos==len(raw);return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--decode',action='store_true');args=ap.parse_args()
    archive=TOOL/'wwiser-master.zip'
    assert sha(archive)=='3eacf61a5ad38111718c83bbf95a3e278e124f42bc14fb57e737ccd6086fe217'
    bank_paths=[CACHE/'source/sound/wwise/Windows'/(b+'.nbnk') for b in BANKS]
    AUDIO.mkdir(exist_ok=True)
    subprocess.run([sys.executable,str(TOOL/'wwiser-master/wwiser.py'),*map(str,bank_paths),
                    '-d','xml','-dn',str(AUDIO/'banks')],check=True)
    roots=ET.fromstring('<banks>'+(AUDIO/'banks.xml').read_text(encoding='utf8')+'</banks>')
    nodes={};media={}
    for root in roots:
        assert root.get('version')=='120'
        assert not list(root.iter('error')),'Bank reader errors'
        for obj in root.iter('object'):
            ident=next((f for f in obj.findall('field') if f.get('name')=='ulID'),None)
            if ident is not None:
                # Shared actor mixers legitimately have different child lists
                # in different banks. Preserve each bank's own namespace.
                key=(root.get('filename'),int(ident.get('value')));assert key not in nodes
                nodes[key]=obj
    wem=AUDIO/'wem';wav=AUDIO/'wav';wem.mkdir(exist_ok=True);wav.mkdir(exist_ok=True)
    for path in bank_paths:
        data=chunks(path.read_bytes())
        if b'DIDX' not in data:continue
        assert len(data[b'DIDX'])%12==0
        for offset in range(0,len(data[b'DIDX']),12):
            ident,at,n=struct.unpack_from('<3I',data[b'DIDX'],offset);raw=data[b'DATA'][at:at+n]
            assert len(raw)==n and raw[:4]==b'RIFF';p=wem/(str(ident)+'.wem')
            if ident in media:assert p.read_bytes()==raw
            p.write_bytes(raw);media[ident]={'bank':path.name,'bytes':n,'sha256':sha(p)}
    bank='wp03_swo_epvsp.nbnk'
    def walk(ident,seen=()):
        assert ident not in seen;node=nodes[bank,ident];kind=node.get('name');refs=[]
        if kind=='CAkEvent':refs=fields(node,'ulActionID')
        elif kind=='CAkActionPlay':refs=fields(node,'idExt')
        elif kind in ('CAkRanSeqCntr','CAkActorMixer'):refs=fields(node,'ulChildID')
        elif kind=='CAkSound':
            ids=[int(f.get('value')) for f in fields(node,'sourceID')]
            assert ids and all(i in media for i in ids),(ident,ids)
            return {'id':ident,'class':kind,'media':ids}
        elif kind.startswith('CAkAction'):
            return {'id':ident,'class':kind,'media':[],'play':False}
        else:raise ValueError(('Unimplemented audio node',ident,kind))
        assert refs or kind=='CAkEvent',(ident,kind,'missing typed child')
        children=[walk(int(f.get('value')),(*seen,ident)) for f in refs]
        props=[]
        for obj in node.iter('object'):
            if obj.get('name')!='AkPropBundle':continue
            props.append({f.get('name'):f.get('valuefmt',f.get('value')) for f in obj.findall('field')})
        return {'id':ident,'class':kind,'properties':props,'children':children,
                'media':sorted({m for c in children for m in c['media']})}
    event_ids={i for (b,i),o in nodes.items() if b==bank and o.get('name')=='CAkEvent'}
    path=CACHE/'source/sound/pl/hm_wp03_epvsp_snd_ev.wwev';raw=path.read_bytes()
    assert raw[:8]==b'WWEV\x13\0\0\0';count=struct.unpack_from('<I',raw,8)[0];links=[]
    for at in range(4,len(raw)-4):
        ident=struct.unpack_from('<I',raw,at)[0]
        if ident not in event_ids:continue
        start=at-4;request,unknown=struct.unpack_from('<HH',raw,start)
        assert unknown==65535,(start,request,unknown)
        graph=walk(ident)
        links.append({'offset':start,'request':request,'event':ident,
                      'selector18_raw':struct.unpack_from('<H',raw,start+18)[0],
                      'prefix24':raw[start:start+24].hex(),'graph':graph})
    assert len(links)==count,(len(links),count)
    assert links[0]['offset']==77
    assert all(b['offset']-a['offset'] in (129,153) for a,b in zip(links,links[1:]))
    if args.decode:
        decoder=TOOL/'vgmstream-r2168/vgmstream-cli.exe'
        for ident in media:
            subprocess.run([str(decoder),'-i','-o',str(wav/(str(ident)+'.wav')),str(wem/(str(ident)+'.wem'))],
                           capture_output=True,check=True)
    report={'status':'SOURCE_AUDIO_REQUEST_MEDIA_LINKS','source':{'banks':{p.name:sha(p) for p in bank_paths},'wwev':sha(path)},
            'tools':{'wwiser_archive_sha256':sha(archive),'wwiser':'https://github.com/bnnm/wwiser',
                     'vgmstream':'https://github.com/vgmstream/vgmstream/releases/tag/r2168'},
            'links':links,'media':media,'selected_iai':[r for r in links if r['request'] in (25601,25602,25603)],
            'converted_for_gu':False,'installed':False,
            'limits':['WWEV selector18_raw is a WSPL speaker ID, verified by world_audio_native.json; the historical field name is retained for compatibility.',
                      'Typed action delay/volume data are retained; raw decoded WEMs are not a mixed or normalized playback acceptance.',
                      'Motion-group and collision audio events are distinct from these EPV events and still require their own mapping.']}
    (PROJECT/'research/world_audio_source.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(report['status'],len(links),'links;',len(media),'media;',[(r['request'],r['selector18_raw'],r['graph']['media']) for r in report['selected_iai']])

if __name__=='__main__':main()
