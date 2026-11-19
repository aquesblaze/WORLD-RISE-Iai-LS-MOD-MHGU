"""Compare the supplied IFRIT encoder with VGAudio using owned PCM inputs.

Both codec outputs are decoded independently and scored against the same PCM.
No game assets are installed, and no existing converted file is overwritten.
"""
import argparse,json,math,struct,subprocess
from pathlib import Path
from animation_port import ROOT,PROJECT,sha
from prepare_world_audio import AUDIO,TOOLS,read_wav,decode

def main():
    ap=argparse.ArgumentParser();ap.add_argument('media',type=int,nargs='+');args=ap.parse_args()
    encoder=ROOT/'.cache/third_party_reviews/hbmk_ifrit/bin/AdpcmEncoder.exe'
    manifest=json.loads((encoder.parent/'manifest.json').read_text())
    for row in manifest:assert sha(encoder.parent/row['file'])==row['sha256']
    out=AUDIO/'encoder_comparison';out.mkdir(exist_ok=True);rows=[]
    for ident in args.media:
        source=AUDIO/'wav'/f'{ident}.wav';rate,pcm=read_wav(source);assert rate==48000
        target=out/f'{ident}_ifrit.adpcm'
        run=subprocess.run([str(encoder),str(source),'-o',str(target)],cwd=encoder.parent,
            capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
        if run.returncode:raise RuntimeError(('IFRIT encoder',run.returncode,run.stdout.decode(errors='replace'),run.stderr.decode(errors='replace')))
        raw=target.read_bytes();samples,dsp_rate,loop=struct.unpack_from('<IxxxxI?xxx',raw)
        coef=struct.unpack_from('<16h',raw,0x1c)
        assert samples==len(pcm)and dsp_rate==rate and not loop
        decoded=decode(raw[0x60:],coef,samples)
        vga=out/f'{ident}_vgaudio.dsp'
        subprocess.run([str(TOOLS/'VGAudioCli-2.2.1.exe'),str(source),str(vga)],capture_output=True,check=True)
        b=vga.read_bytes();assert struct.unpack_from('>I',b)[0]==samples
        other=decode(b[0x60:],struct.unpack_from('>16h',b,0x1c),samples)
        power=sum(v*v for v in pcm)
        def snr(values):
            error=sum((a-b)**2 for a,b in zip(pcm,values));return 10*math.log10(power/error)if error else 999.
        rows.append({'media':ident,'source_sha256':sha(source),'samples':samples,
            'ifrit_snr_db':snr(decoded),'vgaudio_snr_db':snr(other),
            'ifrit_output':str(target),'ifrit_sha256':sha(target),'vgaudio_output':str(vga),
            'same_decoded_pcm':decoded==other})
    report={'status':'ENCODER_QUALITY_COMPARISON_ONLY','rows':rows,'binaries':manifest,
        'limits':'Offline PCM comparison only; no runtime playback or event binding acceptance.'}
    (PROJECT/'research/hbmk_encoder_comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(rows))

if __name__=='__main__':main()
