"""Find the owned source Iai stems in the recorded system output."""
import json
import numpy as np
from scipy.io import wavfile
from scipy.signal import correlate
from pathlib import Path
from animation_port import ROOT

def main():
    meta=json.loads((ROOT/'.cache/mhw_ls_combat/active_session.json').read_text())
    run=Path(meta['run']);rate,pcm=wavfile.read(run/'reported_loopback.wav')
    y=pcm.astype(float)/32768
    report=json.loads((run/'reported_motion_audio.json').read_text())
    results=[]
    for ident in (12607224,83129473,196974904,1045293969):
        sr,raw=wavfile.read(ROOT/f'.cache/mhw_ls_presentation/audio/wav/{ident}.wav')
        assert sr==rate
        x=raw.astype(float)/32768;x=x.reshape(-1); x-=x.mean()
        row={'media':ident,'source_rms':float(np.sqrt(np.mean(x*x))),'channels':[]}
        slot=0x5ef if ident in (12607224,83129473) else 0x5f5
        observed=[r['t'] for r in report['samples'] if r['motion']==slot]
        # Bound the match START, while retaining the entire source stem.
        # Red Iai media lasts1.55s; truncating the recording at start+2.5s
        # otherwise excludes a legitimate start after start+.95s.
        begin=max(0,int((min(observed)-.1)*rate))
        end=min(len(y),int((min(observed)+2.5)*rate)+len(x))
        for ch in range(y.shape[1]):
            z=y[begin:end,ch];corr=correlate(z,x,mode='valid',method='fft')
            i=int(np.argmax(np.abs(corr)));part=z[i:i+len(x)];gain=float(corr[i]/np.dot(x,x))
            similarity=float(corr[i]/np.sqrt(np.dot(x,x)*np.dot(part,part)))
            row['channels'].append({'time':(i+begin)/rate,'correlation':similarity,'gain':gain})
        results.append(row)
    (run/'reported_audio_correlation.json').write_text(json.dumps(results,indent=2))
    print(json.dumps(results,indent=2))

if __name__=='__main__':main()
