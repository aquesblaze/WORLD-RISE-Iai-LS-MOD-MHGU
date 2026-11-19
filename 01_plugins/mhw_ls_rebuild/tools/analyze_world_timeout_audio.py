"""Verify timeout sheath's three World source events in actual output PCM."""
import json,re
from pathlib import Path
import numpy as np
from scipy.io import wavfile
from scipy.signal import correlate
from animation_port import ROOT,PROJECT,sha

def main():
    meta=json.loads((ROOT/'.cache/mhw_ls_combat/active_session.json').read_text());run=Path(meta['run'])
    capture=json.loads((run/'reported_motion_audio.json').read_text())
    bank=json.loads((PROJECT/'research/world_audio_bank.json').read_text(encoding='utf8'))
    assert capture['audio_arc_sha256']==bank['arc_sha256']
    with (run/'log.txt').open('rb')as stream:
        stream.seek(capture['recording_log_start']);log=stream.read(capture['recording_log_end']-capture['recording_log_start']).decode(errors='replace')
    cues=list(re.finditer(r'world_weapon_audio_cue [0-9A-F]+ ([0-9A-F]+) ([0-9A-F]+) 00000138',log))
    assert [int(c[1],16)for c in cues]==[5655,5675,5645]
    rate,raw=wavfile.read(run/'reported_loopback.wav');y=raw.astype(float)/32768
    timeout=[s for s in capture['samples'] if s['motion']==0x5f6 and s.get('coherent')]
    rows=[]
    for index,cue in enumerate(cues):
        frame=int(cue[2],16)/1000
        segment=log[cue.start():cues[index+1].start()if index+1<len(cues)else len(log)]
        choice=re.search(r'world_weapon_audio_choice [0-9A-F]+ '+cue[1]+r' ([0-9A-F]+)',segment)
        assert choice
        request=int(choice[1],16);ident=bank['requests'][request]['media']
        source=ROOT/f'.cache/mhw_ls_presentation/audio/wav/{ident}.wav'
        sr,raw=wavfile.read(source);assert sr==rate
        x=raw.astype(float).reshape(-1)/32768;x-=x.mean();power=np.dot(x,x);assert power>0
        near=min(timeout,key=lambda s:abs(s['frame']-frame))['t']
        begin=max(0,int((near-.15)*rate));end=min(len(y),int((near+.75)*rate)+int(len(x)*1.04))
        channels=[]
        for channel in range(y.shape[1]):
            z=y[begin:end,channel];best=None
            def evaluate(cents):
                nonlocal best
                pitched=np.interp(np.arange(0,len(x)-1,2**(cents/1200)),np.arange(len(x)),x)
                energy=float(np.dot(pitched,pitched));corr=correlate(z,pitched,mode='valid',method='fft')
                sums=np.concatenate(([0.],np.cumsum(z*z)));window=sums[len(pitched):]-sums[:-len(pitched)]
                similarities=corr/np.sqrt(np.maximum(energy*window,1e-20))
                # Bound match starts to the cue neighbourhood, even though
                # the recording window also retains the full source tail.
                maximum=min(len(similarities),int(.9*rate))
                i=int(np.argmax(similarities[:maximum]));similarity=float(similarities[i])
                if best is None or similarity>best['correlation']:
                    best={'time':(begin+i)/rate,'correlation':similarity,'gain':float(corr[i]/energy),'pitch_cents':float(cents)}
            request_info=bank['requests'][request]
            for cents in np.arange(request_info['pitch_cents_min'],request_info['pitch_cents_max']+.1,5):evaluate(cents)
            center=best['pitch_cents']
            for cents in np.arange(max(-50,center-2.5),min(50,center+2.5)+.01,.25):evaluate(cents)
            channels.append(best)
        rows.append({'source_request':int(cue[1],16),'source_frame':frame,'native_request':request,
                     'media':ident,'source_wav_sha256':sha(source),'channels':channels})
    report={'status':'PASS_TIMEOUT_WORLD_AUDIO_PCM'if all(max(c['correlation']for c in r['channels'])>.1 for r in rows)else 'FAIL',
        'run':str(run),'plugin_sha256':capture['plugin_sha256'],'recording_sha256':sha(run/'reported_loopback.wav'),'events':rows}
    (run/'timeout_audio.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'],[(r['source_request'],round(max(c['correlation']for c in r['channels']),3))for r in rows])
    assert report['status'].startswith('PASS'),rows

if __name__=='__main__':main()
