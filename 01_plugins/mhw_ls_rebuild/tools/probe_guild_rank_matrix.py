"""Record each rank/outcome in its own WAV. Only the copied-save fixture is driven."""
import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pyaudiowpatch as pa
from scipy.io import wavfile
from scipy.signal import butter, correlate, resample_poly, sosfilt

from animation_port import PROJECT, ROOT, sha
from pc_fixture import Fixture
from probe_guild_ownership import draw


def whiff(move, rank):
    f = Fixture()
    rows = []
    try:
        f.camp_station()
        draw(f)
        f.fixture_values([(f.actor+0x3330,rank,'<I'),(f.actor+0x332c,6000.,'<f'),(f.actor+0x2780,100,'<I')])
        time.sleep(.2)
        def until(predicate):
            limit=time.monotonic()+10
            while time.monotonic()<limit:
                s=f.state()
                rows.append(dict(time=time.monotonic(),**s))
                if predicate(s):return
                time.sleep(.008)
            raise TimeoutError(str(rows[-1]))
        f.command('A 6')
        until(lambda s:s['motion']==0x569 and s['frame']>=24)
        if move=='big':
            f.command('R 18\nB 18')
            until(lambda s:s['motion']==0x5e6 and s['frame']>=82)
            f.command('R 8')
            until(lambda s:s['action']==248 and s['motion']==BIG_MOTIONS[rank] and s['frame']>=70)
            f.command('R 8\nX 8')
            until(lambda s:s['action']==241 and s['motion']==0x5e1)
        else:
            f.command('R 18\nA 18')
            until(lambda s:s['motion']==0x5e0 and s['frame']>=85)
            f.command('R 3')
            until(lambda s:s['motion']==0x5e0 and s['frame']>=103)
            f.command('A 6')
            until(lambda s:s['action']==4 and s['motion']==0x569)
        until(lambda s:s['state']==1 and s['action']<=5)
        return rows
    finally:
        f.close()


BIG_MOTIONS=(0x5ef,0x5f0,0x5f1,0x5f5)

def paired_output(clip, rate, reqs):
    """Two source channels must occur at the same sample in the game recording."""
    band=butter(3,[1500,10000],fs=rate,btype='bandpass',output='sos')
    mix=sosfilt(band,clip.astype(float),axis=0)
    energy=np.cumsum(np.vstack((np.zeros((1,mix.shape[1])),mix**2)),axis=0)
    scores=[]
    for req in reqs:
        hz,ref=wavfile.read(ROOT/f".cache/mhw_ls_presentation/audio/wav/{req['media']}.wav")
        ref=resample_poly(ref.astype(float),rate,hz)
        factor=2**(req.get('pitch_cents',0)/1200)
        ref=np.interp(np.arange(0,len(ref),factor),np.arange(len(ref)),ref)
        ref=sosfilt(band,ref)[:rate]
        n=len(ref)
        denom=np.linalg.norm(ref)*np.sqrt(np.maximum(energy[n:]-energy[:-n],1))
        dots=np.stack([correlate(ch,ref,'valid',method='fft') for ch in mix.T],axis=1)
        scores.append(np.max(abs(dots)/denom,axis=1))
    assert len(scores)==2
    # Clips begin 350ms before the move. Exclude the follow-up attack and
    # require both stems' matching onsets during the first part of the move.
    stop=min(round(1.45*rate),*(len(s) for s in scores))
    start=round(.22*rate)
    joint=np.minimum(scores[0][start:stop],scores[1][start:stop])
    at=start+int(np.argmax(joint))
    return dict(media=[q['media'] for q in reqs],onset=round(at/rate,4),
                correlation=[round(float(s[at]),4) for s in scores])


def run_case(run, move, rank, outcome, encounter_whiff=False, monster_frame=60, film_lines=False):
    case=f'matrix_{move}_{rank}_{outcome}'
    audio=pa.PyAudio()
    device=audio.get_default_wasapi_loopback()
    rate=int(device['defaultSampleRate'])
    channels=device['maxInputChannels']
    chunks=[]
    def capture(data, frames, clock, status):
        chunks.append(data)
        return None,pa.paContinue
    offset=(run/'log.txt').stat().st_size
    stream=audio.open(format=pa.paInt16,channels=channels,rate=rate,input=True,
                      input_device_index=device['index'],frames_per_buffer=480,stream_callback=capture)
    started=time.monotonic()
    try:
        if outcome=='whiff' and not encounter_whiff:
            rows=whiff(move,rank)
        else:
            options=['--round'] if move=='foresight' else ['--at-frame',str(monster_frame)]
            if move=='foresight':options+=['--delay','.15']
            if outcome=='whiff':options.append('--encounter-whiff')
            if film_lines:options.append('--film-lines')
            subprocess.run([sys.executable,str(PROJECT/'tools/probe_world_counter.py'),move,
                            '--attack','14','--contact-fixture','--rank',str(rank),'--rank-matrix',*options],
                           check=True,stdout=subprocess.DEVNULL)
            rows=json.loads((run/(case+'.json')).read_text())['rows']
    finally:
        stream.stop_stream()
        stream.close()
        audio.terminate()
    with (run/'log.txt').open('rb') as f:
        f.seek(offset)
        events=f.read().decode(errors='replace')
        log_end=f.tell()
    initial=0x5e0 if move=='foresight' else BIG_MOTIONS[rank]
    bound=[r for r in rows if r['motion']==initial and r['action']==(240 if move=='foresight' else 248)]
    if not bound:raise ValueError('Move did not bind')
    t0=bound[0]['time']-started
    pcm=np.frombuffer(b''.join(chunks),dtype='<i2').reshape(-1,channels)
    begin=max(0,int((t0-.35)*rate))
    clip=pcm[begin:int((bound[-1]['time']-started+2.7)*rate)]
    wavfile.write(run/(case+'.wav'),rate,clip)
    phases=[]
    for r in rows:
        if r['time']<bound[0]['time']:continue
        item=(r['state'],r['action'],r['motion'])
        if not phases or item!=phases[-1]:phases.append(item)
    success=outcome=='counter'
    # Rise ISS: a counter opens one level, a whiff keeps the level, and a
    # rank increase never clears the gauge. Foresight itself owns no rank.
    expected_rank=min(rank+1,3) if move=='big' and success else rank
    settled=[r for r in bound if r['frame']>=45]
    cues=[int(x,16) for x in re.findall(r'world_audio_cue \w+ (\w+)',events)]
    count=len(re.findall(r'world_counter ',events))
    contacts=len(re.findall(r'world_detector_contact ',events))
    follow_action=241 if move=='big' else 30 if success else 4
    follow_motion=0x5e1 if move=='big' else 0x57f if success else 0x569
    follow=(16,follow_action,follow_motion) in phases
    follow_rows=[r for r in rows if r['action']==follow_action and r['motion']==follow_motion and r['time']>bound[-1]['time']]
    conditions=dict(rank_entry=bound[0]['rank']==rank,
        rank_settlement=bool(settled) and all(r['rank']==expected_rank for r in settled),
        geometry=contacts==int(success) and count==int(success), follow=follow)
    if move=='foresight':
        conditions.update(round_gate=((16,30,0x57f) in phases)==success,
                          filled_on_contact=any(r['gauge']==100 for r in bound)==success,
                          counter_cue=cues.count(25510)==int(success))
        if success:
            conditions['round_color']=any(r['rank']==min(rank+1,3) for r in follow_rows)
    else:
        conditions['color_cue']=(25605 in cues)==bool(rank)
        conditions['counter_cue']=cues.count(25510)==int(success)
        conditions['gauge_kept']=all(r['gauge']>0 for r in bound)
    bank=json.loads((PROJECT/'research/world_audio_bank.json').read_text())
    main=(25601,25602,25603,25603)[rank] if move=='big' else 25606
    required=[main]
    if move=='foresight':
        required.append(25505)
    elif rank:required.append(25605)
    if success:required.append(25510)
    matches={}
    for cue in required:
        matches[cue]=paired_output(clip,rate,[r for r in bank['requests'] if r.get('source_request')==cue])
    conditions['output_pcm']=all(min(m['correlation'])>=(.10 if cue==25510 else .065) for cue,m in matches.items())
    if not success:
        control=paired_output(clip,rate,[r for r in bank['requests'] if r.get('source_request')==25510])
        conditions['no_counter_pcm']=min(control['correlation'])<.10
        matches['25510_negative_control']=control
    actual_bank=sha(run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_audio.arc')
    assert actual_bank==bank['arc_sha256']
    report=dict(case=case,conditions=conditions,phases=phases,cues=cues,contacts=contacts,
                counter_count=count,entry_rank=bound[0]['rank'],settled_ranks=sorted({r['rank'] for r in settled}),
                matches=matches,follow_action=follow_action,device=device['name'],wav=case+'.wav',
                plugin=sha(run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
                log_start=offset,log_end=log_end,clip_start_monotonic=started+begin/rate,
                follow_onset=(follow_rows[0]['time']-started-begin/rate) if follow_rows else None,
                ranks_during_follow=sorted({r['rank'] for r in follow_rows}),
                gauge_during_move=sorted({r['gauge'] for r in bound}),
                bank=actual_bank)
    (run/(case+'_result.json')).write_text(json.dumps(report,indent=2))
    print(case,conditions,matches,flush=True)
    return all(conditions.values())


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--move',choices=['big','foresight'],action='append')
    parser.add_argument('--rank',type=int,choices=range(4),action='append')
    parser.add_argument('--outcome',choices=['counter','whiff'],action='append')
    parser.add_argument('--encounter-whiff',action='store_true',help='Keep big Iai success and whiff in the monster encounter')
    parser.add_argument('--monster-frame',type=int,default=60,help='Monster animation frame at which to submit big Iai')
    parser.add_argument('--film-lines',action='store_true',help='Capture consecutive GU frames alongside the two encounter recordings')
    args=parser.parse_args()
    if args.encounter_whiff and args.move!=['big']:
        parser.error('--encounter-whiff requires --move big')
    if args.film_lines and not args.encounter_whiff:
        parser.error('--film-lines requires --encounter-whiff')
    run=Path(json.loads((ROOT/'.cache/mhw_ls_combat/active_session.json').read_text())['run'])
    ok=True
    for outcome in args.outcome or ('whiff','counter'):
        for move in args.move or ('big','foresight'):
            for rank in args.rank or range(4):
                try:ok=run_case(run,move,rank,outcome,args.encounter_whiff,args.monster_frame,args.film_lines) and ok
                except Exception as exc:
                    print(move,rank,outcome,repr(exc),flush=True)
                    ok=False
    return int(not ok)


if __name__=='__main__':
    raise SystemExit(main())
