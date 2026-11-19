"""Map the user's listening notes onto original DIDX media identities.

Descriptions remain user annotations. Bank order is accepted only after every
listed clip's independently decoded duration agrees with the note.
"""
import json,re,struct,wave
from pathlib import Path
from animation_port import ROOT,PROJECT,sha
from inspect_world_audio import chunks

def main():
    source=Path(r'D:\AAAGPT\MHGU-MOD\太刀音效.txt');raw=source.read_bytes()
    try:text=raw.decode('utf-8-sig');encoding='utf-8-sig'
    except UnicodeDecodeError:text=raw.decode('gb18030');encoding='gb18030'
    notes={};bank=None
    for line in text.splitlines():
        line=line.strip()
        if line.startswith('wp'):
            bank=line if line.endswith('.nbnk')else line+'.nbnk';notes[bank]=[];continue
        if not line:continue
        match=re.match(r'^(\d+)\s*(.*?)\s*(\d+)\.(\d{2})\.(\d{2})$',line)
        if not match:
            match=re.match(r'^(\d+)\s*(.*?)\s*(\d+)\.(\d{2})(\d{2})$',line)
        if not match or not bank:raise ValueError(('Unparsed note',line))
        ordinal,label,minutes,seconds,centiseconds=match.groups()
        notes[bank].append({'ordinal':int(ordinal),'description':label.strip(),
            'noted_seconds':60*int(minutes)+int(seconds)+int(centiseconds)/100})
    audio=ROOT/'.cache/mhw_ls_presentation/audio';base=ROOT/'.cache/mhw_ls_presentation/source/sound/wwise/Windows'
    links=json.loads((PROJECT/'research/world_audio_source.json').read_text(encoding='utf8'))
    gu=json.loads((PROJECT/'research/world_audio_bank.json').read_text(encoding='utf8'))
    requests={}
    for r in links['links']:
        for media in r['graph']['media']:requests.setdefault(media,[]).append(r['request'])
    rows=[];bad=[]
    for bank,entries in notes.items():
        data=chunks((base/bank).read_bytes());index=data[b'DIDX']
        assert len(index)//12==len(entries),(bank,'Ordinal count differs')
        for n,note in enumerate(entries):
            assert note['ordinal']==n+1
            media,offset,size=struct.unpack_from('<3I',index,n*12)
            path=audio/'wav'/f'{media}.wav'
            with wave.open(str(path))as w:duration=w.getnframes()/w.getframerate();rate=w.getframerate();channels=w.getnchannels()
            row={**note,'bank':bank,'media':media,'decoded_seconds':duration,'rate':rate,'channels':channels,
                'difference_seconds':duration-note['noted_seconds'],'source_requests':sorted(set(requests.get(media,[]))),
                'gu_requests':[r['request_id']for r in gu['requests']if r['media']==media],
                'source_wem_sha256':sha(audio/'wem'/f'{media}.wem')}
            rows.append(row)
            if abs(row['difference_seconds'])>.025:bad.append(row)
    result={'status':'ORDINAL_DURATION_MATCH'if not bad else'ORDINAL_ORDER_NOT_VERIFIED',
        'notes':str(source),'notes_sha256':sha(source),'encoding':encoding,
        'count':len(rows),'duration_mismatch_count':len(bad),'rows':rows,
        'description_provenance':'User listening annotations; not proof of source event/condition bindings.',
        'limits':'Current GU bank membership is a development asset check, not runtime playback or user acceptance.'}
    target=PROJECT/'research/world_user_audio_notes_audit.json';target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in result.items()if k!='rows'},ensure_ascii=True))
    for r in rows:
        print(json.dumps({k:r[k]for k in('bank','ordinal','description','media','decoded_seconds','difference_seconds','source_requests','gu_requests')},ensure_ascii=True))

if __name__=='__main__':main()
