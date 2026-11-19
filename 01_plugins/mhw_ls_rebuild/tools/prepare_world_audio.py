"""Encode selected owned World Iai media as genuine GU DSP-ADPCM resources.

This prepares assets only. Source event selection, mixing/volume and runtime
sound registration are separate requirements; nothing is installed here.
"""
import argparse,array,json,math,struct,subprocess,sys,wave
from pathlib import Path
from animation_port import ROOT,PROJECT,sha

AUDIO=ROOT/'.cache/mhw_ls_presentation/audio'
TOOLS=ROOT/'.cache/mhw_audio_tools'

def decode(data,coef,count,h1=0,h2=0):
    result=array.array('h')
    for base in range(0,len(data),8):
        ps=data[base];scale=1<<(ps&15);predictor=ps>>4
        assert predictor<8
        c1,c2=coef[2*predictor:2*predictor+2]
        for j in range(14):
            if len(result)==count:return result
            byte=data[base+1+j//2];n=(byte>>(0 if j&1 else 4))&15
            if n>=8:n-=16
            value=(((n*scale)<<11)+1024+c1*h1+c2*h2)>>11
            value=max(-32768,min(32767,value));result.append(value);h2,h1=h1,value
    assert len(result)==count;return result

def read_wav(path):
    with wave.open(str(path)) as w:
        assert w.getnchannels()==1 and w.getsampwidth()==2 and w.getcomptype()=='NONE'
        rate=w.getframerate();pcm=array.array('h',w.readframes(w.getnframes()))
    assert sys.byteorder=='little';return rate,pcm

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--weapon',action='store_true');ap.add_argument('--conditional',action='store_true')
    ap.add_argument('--full',action='store_true',help='All original EPV-bank media; separate staged report, no runtime installation')
    ap.add_argument('--ground',action='store_true',help='Use expanded ground motion weapon bank')
    args=ap.parse_args();assert not args.ground or args.weapon
    assert sum((args.weapon,args.conditional,args.full))<=1
    source_report=PROJECT/'research'/('world_full_audio_native.json'if args.full else ('world_ground_weapon_audio.json' if args.ground else 'world_weapon_audio.json') if args.weapon else 'world_audio_source.json')
    report=json.loads(source_report.read_text(encoding='utf8'))
    references={}
    if args.full:
        comparison=json.loads((PROJECT/'research/hbmk_encoder_comparison.json').read_text())
        references={r['media']:r for r in comparison['rows']}
        assert set(report['media'])==set(references),'Compare every full-bank clip against IFRIT first'
    if args.full:selected=report['media']
    elif args.weapon:
        assert not report['missing_media']
        selected=sorted(map(int,report['media']))
    else:selected=sorted({m for r in (report['links'] if args.conditional else report['selected_iai'])
        if not args.conditional or r['request'] in (25515,25606) for m in r['graph']['media']})
    encoder=TOOLS/'VGAudioCli-2.2.1.exe'
    assert sha(encoder)=='0f3bda1bf2dc2421756a16c05769430e4881876deb4eab40ca47b31009173e2b'
    decoder=TOOLS/'vgmstream-r2168/vgmstream-cli.exe'
    out=AUDIO/('gu_full' if args.full else 'gu_ground' if args.ground else 'gu');out.mkdir(exist_ok=True);rows=[]
    # Use GU's actual wave header stamp and fixed-format flags as a guard.
    sys.path.insert(0,str(ROOT/'06_tools'));from arc_tool import read_entries,unpack_one
    template=ROOT/'Windows-MHGURecomp/data/romfs/nativeNX/arc/weapon/w07/snd/mat.arc'
    native,_,entries=read_entries(template)
    original=unpack_one(native,next(e for e in entries if e['hash']==0x79c47b59))[0]
    assert original[:8]==b'\2\0\0\0\1\0\0\1'
    stamp=original[0x10:0x18]
    for ident in selected:
        source=AUDIO/'wav'/(str(ident)+'.wav')
        if args.weapon or args.conditional or args.full:
            subprocess.run([str(decoder),'-i','-o',str(source),str(AUDIO/'wem'/f'{ident}.wem')],capture_output=True,check=True)
        rate,pcm=read_wav(source)
        dsp=out/(str(ident)+'.dsp')
        subprocess.run([str(encoder),str(source),str(dsp)],capture_output=True,check=True)
        raw=dsp.read_bytes();samples,nibbles,dsp_rate=struct.unpack_from('>3I',raw)
        loop,fmt=struct.unpack_from('>2H',raw,12);assert samples==len(pcm) and rate==dsp_rate and (loop,fmt)==(0,0)
        coef=struct.unpack_from('>16h',raw,0x1c)
        assert struct.unpack_from('>2h',raw,0x40)==(0,0)
        byte_count=(nibbles+1)//2;payload=raw[0x60:0x60+byte_count]
        assert len(payload)==byte_count
        header=bytearray(0x78);header[:8]=original[:8]
        struct.pack_into('<If',header,8,byte_count,samples/rate);header[0x10:0x18]=stamp
        struct.pack_into('<16h',header,0x18,*coef)
        struct.pack_into('<6I',header,0x60,samples,rate,0,0,samples-1,0)
        target=out/(str(ident)+'.wave');target.write_bytes(header+payload+bytes(-byte_count%256))
        # Independent decoder checks the rewrapped coefficients/data, then
        # compare with vgmstream's standalone DSP decode exactly, sample-wise.
        guard=target.read_bytes();decoded=decode(guard[0x78:0x78+byte_count],struct.unpack_from('<16h',guard,0x18),samples)
        decoded_path=out/(str(ident)+'_check.wav')
        silent=not any(pcm)
        if silent:
            # vgmstream deliberately rejects all-zero DSP coefficient tables
            # in its format heuristic. This source is exact digital silence;
            # our independent DSP decoder must also produce exact zeros.
            assert not any(decoded) and not any(coef)
        else:
            subprocess.run([str(decoder),'-i','-o',str(decoded_path),str(dsp)],capture_output=True,check=True)
            decoded_rate,other=read_wav(decoded_path);assert decoded_rate==rate and decoded==other
        power=sum(x*x for x in pcm);error=sum((a-b)**2 for a,b in zip(pcm,decoded))
        snr=10*math.log10(power/error) if error else 999.
        reference_equal=False
        if args.full:
            reference=references[ident];assert reference['source_sha256']==sha(source)
            path=Path(reference['ifrit_output']);assert sha(path)==reference['ifrit_sha256']
            body=path.read_bytes();assert struct.unpack_from('<I',body)[0]==samples
            reference_equal=decoded==decode(body[0x60:],struct.unpack_from('<16h',body,0x1c),samples)
            assert reference_equal,'Full-bank output differs from the independently wrapped IFRIT reference'
        else:assert snr>25,(ident,snr)
        rows.append({'media':ident,'source_sha256':sha(source),'wave_sha256':sha(target),
                     'samples':samples,'rate':rate,'channels':1,'bytes':target.stat().st_size,
                     'encoded_snr_db':snr,'independent_decode_equal':True,'silent':silent,
                     'ifrit_reference_pcm_equal':reference_equal if args.full else None,
                     'vgmstream_dsp_equal':not silent,
                     'resource_path':f'sound/se/pl/wp/swo/world/wav/w{ident}','resource_type':'0x79c47b59'})
    result={'status':'GU_AUDIO_RESOURCES_ENCODED_AND_DECODE_CHECKED','media':rows,
            'output_directory':str(out),
            'source_report_sha256':sha(source_report),
            'template_arc_sha256':sha(template),'native_wave_stamp':stamp.hex(),
            'encoder_sha256':sha(encoder),'encoder':'https://github.com/Thealexbarney/VGAudio/releases/tag/v2.2.1',
            'quality_check':'Every decoded sample equals the supplied IFRIT encoder reference; per-clip lossy DSP SNR retained.'if args.full else'Encoded SNR above25dB.',
            'installed':False,'runtime_playback_verified':False,
            'limits':'All EPV-bank media; event/provider/stop/RTPC bindings and native runtime playback remain pending.'if args.full else
                     'Selected weapon-model media only; verifies container/codec data, not event selection, mixing or runtime playback.' if args.weapon else
                     'Six Iai EPV media only; this verifies GU container/codec data, not request conditions, event mixing, runtime audio loading or playback.'}
    target=PROJECT/'research'/('world_full_audio_conversion.json'if args.full else 'world_conditional_audio_conversion.json' if args.conditional else ('world_ground_weapon_audio_conversion.json' if args.ground else 'world_weapon_audio_conversion.json') if args.weapon else 'world_audio_conversion.json')
    target.write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(result['status'],len(rows),'media; minimum SNR',min(r['encoded_snr_db'] for r in rows))

if __name__=='__main__':main()
