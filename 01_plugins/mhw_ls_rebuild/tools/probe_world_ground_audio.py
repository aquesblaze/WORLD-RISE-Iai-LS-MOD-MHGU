"""Record the copied GU test session and check audible stems against owned World PCM."""
import argparse, json, re, struct, subprocess, sys, threading, time, wave
from pathlib import Path

import numpy as np
import pyaudiowpatch as pa
from scipy.io import wavfile
from scipy.signal import correlate, resample_poly
from animation_port import ROOT, PROJECT, sha
from pc_fixture import Fixture

CASES = {
    'combo': (['probe_world_links.py'], [77872984,858105059,890770792,12607224,83129473]),
    'helm': (['probe_world_encounter.py', '--auto-down'], [35004545, 280637586, 664717410]),
}

def match(output, rate, media, pitches):
    sample_rate, signal = wavfile.read(ROOT / f'.cache/mhw_ls_presentation/audio/wav/{media}.wav')
    signal = signal.astype(float)
    if sample_rate != rate:
        signal = resample_poly(signal, rate, sample_rate)
    # GU's native voice can randomise pitch by fifty cents on weapon sounds.
    best = (0.0,0,0.0)
    envelopes=[np.r_[0,np.cumsum(channel*channel)] for channel in output.T]
    def evaluate(cents,begin,end):
        nonlocal best
        length = round(len(signal) * 2**(-cents / 1200))
        ref = np.interp(np.arange(length) * len(signal) / length, np.arange(len(signal)), signal)
        ref -= ref.mean()
        for channel,energy in zip(output.T,envelopes):
            if end-begin < length:
                continue
            corr = correlate(channel[begin:end], ref, mode='valid', method='fft')
            denom=np.linalg.norm(ref)*np.sqrt(np.maximum(energy[begin+length:end+1]-energy[begin:end-length+1],1))
            scores=np.abs(corr)/denom
            at=int(np.argmax(scores))
            best=max(best,(float(scores[at]),begin+at,cents))
    for cents in pitches:evaluate(cents,0,len(output))
    if len(pitches)>1:
        _,center,coarse=best
        begin=center+rate//3
        end=min(len(output),center+rate//20+round(len(signal)*2**(-min(pitches)/1200)))
        for cents in np.arange(max(min(pitches),coarse-2),min(max(pitches),coarse+2)+.01,.1):
            evaluate(cents,begin,end)
    return best[:2]

def mixer_voices(text, wanted, bank):
    """Match actual audren buffers against packed DSP data; equal lengths may be stereo pairs."""
    fixture=Fixture()
    buffers={}
    matches={str(media):[] for media in wanted}
    try:
        for row in bank['media']:
            media=row['media']
            if media not in wanted:continue
            for subdir in ('gu_full','gu_ground','gu'):
                path=ROOT/f'.cache/mhw_ls_presentation/audio/{subdir}/{media}.wave'
                if path.is_file() and sha(path)==row['wave_sha256']:break
            else:raise ValueError(f'No matching encoded resource for {media}')
            wave_bytes=path.read_bytes()
            count=struct.unpack_from('<I',wave_bytes,8)[0]
            buffers[media]=(row['samples'],wave_bytes[0x78:0x78+count],struct.unpack_from('<16h',wave_bytes,24))
        pattern=r'\[audren\] f(\d+) v(\d+) wb\d+ fmt 6 rate 48000 ch 1 pitch ([\d.]+).*? addr ([0-9a-f]+) size [0-9a-f]+ \[0,(\d+)\).*? ds ([0-9a-f]+)'
        for frame,voice,pitch,addr,samples,ds in re.findall(pattern,text):
            for media,(length,body,coef) in buffers.items():
                if length!=int(samples) or not int(ds,16):continue
                if fixture.read(int(ds,16),'<16h')!=coef:continue
                if bytes(fixture.read(int(addr,16),f'<{len(body)}B'))!=body:continue
                matches[str(media)].append(dict(frame=int(frame),voice=int(voice),pitch=float(pitch)))
    finally:fixture.close()
    return matches

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('case', choices=CASES)
    case=parser.parse_args().case
    command, media=CASES[case]
    run=Path(json.loads((ROOT/'.cache/mhw_ls_combat/active_session.json').read_text())['run'])
    log=run/'log.txt'
    offset=log.stat().st_size
    bank=json.loads((PROJECT/'research/world_audio_bank.json').read_text())
    assert bank['arc_sha256']==sha(run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_audio.arc')
    prefix=run/f'ground_audio_{case}_{time.time_ns()}'
    result={'case':case,'status':'FAIL','bank_sha256':bank['arc_sha256'],
            'plugin_sha256':sha(run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro')}
    audio=pa.PyAudio()
    device=audio.get_default_wasapi_loopback()
    rate=int(device['defaultSampleRate'])
    channels=device['maxInputChannels']
    stream=audio.open(format=pa.paInt16,channels=channels,rate=rate,input=True,
                      input_device_index=device['index'],frames_per_buffer=960)
    stop=threading.Event()
    chunks=[]
    def record():
        while not stop.is_set():
            chunks.append(stream.read(960,exception_on_overflow=False))
    thread=threading.Thread(target=record)
    thread.start()
    try:
        subprocess.run([sys.executable,str(PROJECT/'tools'/command[0]),*command[1:]],check=True)
        time.sleep(.6)
    except Exception as exc:
        result['drive_error']=str(exc)
    finally:
        stop.set();thread.join();stream.close();audio.terminate()
    raw=b''.join(chunks)
    with wave.open(str(prefix.with_suffix('.wav')),'wb') as out:
        out.setparams((channels,2,rate,0,'NONE','not compressed'));out.writeframes(raw)
    with log.open('rb') as trace:
        trace.seek(offset)
        text=trace.read().decode(errors='replace')
    plays=[int(x,16) for x in re.findall(r'world_audio_play \w+ (\w+)',text)]
    events=[int(x,16) for x in re.findall(r'world_audio_cue \w+ (\w+)',text)]
    result.update(requests=events,private_plays=plays)
    if '[audren]' in text:
        result['mixer_voices']=mixer_voices(text,media,bank)
    signal=np.frombuffer(raw,dtype='<i2').reshape(-1,channels).astype(float)
    # The two EPV hit stems also play on the ascent. Match the sustained
    # weapon cue first, then search for the separate landing tail.
    matches={}
    starts={}
    order=list(reversed(media)) if case=='helm' else media
    for m in order:
        row=next(r for r in bank['requests'] if r['media']==m)
        base=row.get('pitch_cents',0)
        pitches=range(base+row['pitch_cents_min'],base+row['pitch_cents_max']+1,2)
        begin,end=0,len(signal)
        if case=='helm' and starts:
            center=starts[str(media[-1])]
            begin=center+rate//3
            duration=next(r['samples']/r['rate'] for r in bank['media'] if r['media']==m)
            end=min(end,center+2*rate+round(duration*rate))
        score,at=match(signal[begin:end],rate,m,pitches)
        matches[str(m)]=score
        starts[str(m)]=at+begin
    result['source_matches']=matches
    result['source_onsets_seconds']={m:at/rate for m,at in starts.items()}
    if case=='helm':
        ordinals=[int(x,16) for x in re.findall(r'world_burst \w+ \w+ (\w+)',text)]
        common=next(r['request_id']for r in bank['requests'] if r['media']==664717410)
        result['ordinals']=ordinals
        hit_stems=[r['request_id'] for r in bank['requests'] if r.get('source_request')==25530]
        valid=(sorted(ordinals)==list(range(7)) and events.count(25530)==1
               and all(plays.count(i)==1 for i in [common,*hit_stems]))
    else:
        valid=events.count(25604)==9 and events.count(25601)==7
    result['event_counts_match']=valid
    if valid and 'drive_error' not in result and min(result['source_matches'].values())>.10:
        result['status']='PASS_CASE_REQUESTS_AND_OUTPUT_PCM'
    prefix.with_suffix('.json').write_text(json.dumps(result,indent=2))
    print(prefix,result['status'],result['source_matches'],flush=True)
    return int(result['status']=='FAIL')

if __name__=='__main__':
    raise SystemExit(main())
