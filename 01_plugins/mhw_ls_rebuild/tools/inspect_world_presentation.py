"""Resolve source TIML WorkNo through the EPV closing index, with sound links.

Layout references (not bundled third-party implementation):
https://github.com/UNOWEN-OwO/MHW-EFX-Template/blob/master/EPV3.bt
https://github.com/Silvris/RingingBloom/blob/master/RingingBloom/WWiseTypes/EPVSPFile.cs
Only metadata is written to the project; original assets stay in the local cache.
"""
import hashlib,json,struct
from pathlib import Path
from animation_port import ROOT,PROJECT

CACHE=ROOT/'.cache/mhw_ls_presentation/source'

class Reader:
    def __init__(self,path):self.data=path.read_bytes();self.pos=0
    def read(self,fmt):
        v=struct.unpack_from('<'+fmt,self.data,self.pos);self.pos+=struct.calcsize('<'+fmt)
        return v[0] if len(v)==1 else v
    def string(self):
        end=self.data.index(0,self.pos);v=self.data[self.pos:end].decode('utf8');self.pos=end+1;return v

def epv(path):
    r=Reader(path);assert r.read('4s')==b'epv\0';version=r.read('I');assert version==51
    groups=[]
    for _ in range(r.read('I')):
        count,group=r.read('Ih');records=[]
        for i in range(count):
            paths=[r.string() for _ in range(4)];p=r.pos
            def at(fmt,offset):return struct.unpack_from('<'+fmt,r.data,p+offset)
            records.append({'paths':paths,'unknown_id':at('i',4)[0],'record_id':at('h',8)[0],
                'position':at('3f',58),'rotation':at('3f',82),'bone':at('i',114)[0],
                'colors':[dict(zip(('slot','rgba','saturation','size_bits','frequency'),at('iIfIf',130+20*j))) for j in range(8)]})
            r.pos+=338
        groups.append({'group_id':group,'records':records})
    assert r.read('Q')==0
    index=[]
    for _ in range(r.read('I')):
        work,group,record=r.read('3I');assert group<len(groups) and record<len(groups[group]['records'])
        index.append({'work':work,'group_index':group,'record_index':record})
    assert len(index)==sum(len(g['records']) for g in groups)
    tail={'path':r.string()}
    # Common-player EPV has additional trailing data absent in weapon EPV.
    # Do not mistake the template's example NULL for a universal terminator.
    suffix=r.data[r.pos:]
    tail.update(bytes=len(suffix),sha256=hashlib.sha256(suffix).hexdigest(),prefix=suffix[:16].hex())
    assert suffix and suffix[0]==1
    return {'version':version,'groups':groups,'work_index':index,'tail':tail}

def epvsp(path):
    r=Reader(path);assert r.read('I')==0x18091001;assert r.read('4s')==b'ESP\0';assert r.read('I')==8
    assert r.read('I')==0x45185bed;wwct=r.string();requests=[];triggers=[]
    for _ in range(r.read('I')):
        requests.append(dict(zip(('element_no','request','kill_request','group_id','record_id'),r.read('iiiII'))))
    for _ in range(r.read('I')):
        triggers.append(dict(zip(('element_no','request','call_state','option','group_id','record_id'),r.read('iiIIII'))))
    assert r.pos==len(r.data),(r.pos,len(r.data))
    return {'wwct':wwct,'requests':requests,'triggers':triggers}

def main():
    providers={name:epv(CACHE/path) for name,path in {
        'weapon':'wp/swo/epv/hm_wp03.epv3','common':'hm/common/epv/hm_cm00.epv3'}.items()}
    sound=epvsp(CACHE/'wp/swo/sound/hm_wp03.epvsp')
    combat=json.loads((PROJECT/'research/world_combat_source.json').read_text(encoding='utf8'))
    events=[];used=set()
    for clip,c in combat['clips'].items():
        for e in c['raw_events']:
            if not e['type'].startswith('EffectParameter'):continue
            tracks={t['name']:t['keys'] for t in e['tracks']}
            for name,keys in tracks.items():
                if not name.startswith('WorkNo'):continue
                used.update(v for _,v in keys)
                events.append({'source':int(clip),'parameter':e['type'],'channel':int(name[6:]),
                               'work_keys':keys,'enable_keys':tracks.get('KeyFrame'+name[6:],[])})
    resolved={}
    for work in sorted(used):
        hits=[]
        for provider,data in providers.items():
            for link in data['work_index']:
                if link['work']!=work:continue
                gi,ri=link['group_index'],link['record_index'];g=data['groups'][gi];r=g['records'][ri]
                hit={'provider':provider,**link,'group_id':g['group_id'],**r}
                if provider=='weapon':
                    hit['sound']={k:[x for x in sound[k] if (x['group_id'],x['record_id'])==(g['group_id'],r['record_id'])] for k in ('requests','triggers')}
                hits.append(hit)
        resolved[str(work)]=hits
    report={'status':'SOURCE_EFFECT_INDEX_RESOLVED','events':events,'work_records':resolved,'sound':sound,
        'unresolved':[k for k,v in resolved.items() if not v],
        'sources':{str(p.relative_to(CACHE)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in [CACHE/'wp/swo/epv/hm_wp03.epv3',CACHE/'hm/common/epv/hm_cm00.epv3',CACHE/'wp/swo/sound/hm_wp03.epvsp']},
        'layout_references':[__doc__.splitlines()[3],__doc__.splitlines()[4]],
        'limits':'EPV closing-index metadata matches TIML WorkNo values. Runtime bank selection, visual conversion, sound event decoding and playback remain to verify.',
        'port_complete':False}
    out=PROJECT/'research/world_presentation_map.json';out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    paths=sorted({p for rs in resolved.values() for r in rs for p in r['paths'] if p})
    (ROOT/'.cache/mhw_ls_presentation/effect_dependencies.json').write_text(json.dumps(paths,indent=2),encoding='utf8')
    print(report['status'],len(used),'work IDs;',len(paths),'resource paths; unresolved',report['unresolved'])
    for k in ('3010','3011','3012','3013','3014','3015','3016','3017'):
        print(k,[(r['group_id'],r['record_id'],r['paths'][0],r.get('sound')) for r in resolved.get(k,[])])

if __name__=='__main__':main()
