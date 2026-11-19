"""Capture actual WASAPI output and high-rate clocks for reported Iai defects.

Run with the local mhw_audio_capture venv against an existing isolated fixture.
Only pad commands and copied-save rank fixtures are used.
"""
import argparse, ctypes, json, re, struct, threading, time, wave
import numpy as np
import pyaudiowpatch as pa
from pc_fixture import Fixture
from animation_port import sha

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--burst',action='store_true')
    ap.add_argument('--skip-voices',action='store_true',help='Omit full voice-manager diagnostics; PCM and animation acceptance remain unchanged')
    args=ap.parse_args()
    f=Fixture(); a=f.actor; rows=[]; marks=[]; chunks=[]; done=threading.Event()
    f.camp_station();origin=f.state()['position']
    with (f.run/'log.txt').open('rb') as file:log=file.read(16000000).decode('utf8',errors='replace')
    resource=int(re.search(r'world_audio_ready [0-9A-F]+ ([0-9A-F]+)',log)[1],16)
    manager=f.read(0x2326d8c);count=f.read(manager+202864)
    voice_buffer=ctypes.create_string_buffer(2784*count)
    audio=pa.PyAudio(); device=audio.get_default_wasapi_loopback()
    rate=int(device['defaultSampleRate']); channels=device['maxInputChannels']
    stream=audio.open(format=pa.paInt16, channels=channels, rate=rate,input=True,
                      input_device_index=device['index'],frames_per_buffer=480)
    log_start=(f.run/'log.txt').stat().st_size
    start=time.perf_counter()
    def capture():
        while not done.is_set(): chunks.append(stream.read(480,exception_on_overflow=False))
    thread=threading.Thread(target=capture);thread.start()
    def sample():
        row={'t':time.perf_counter()-start,'motion':f.read(a+0x4b4,'<H'),
             'frame':f.read(a+0x500,'<f'),'speed':f.read(a+0x50c,'<f'),
             'dt':f.read(a+0x1c,'<f'),'state':f.read(a+0x2506,'<H'),
             'action':f.read(a+0x250a,'<H'),'position':f.read(a+0x40,'<3f'),
             'blend_remaining':f.read(a+0x4f4,'<f'),'clock_raw':f.read(a+0x4fc,'<f'),
             'motion_flags':f.read(a+0x4bc)}
        if row['motion'] in (0x5ef,0x5f5,0x5f6):
            records=f.read(a+0x494); mapping=f.read(a+0x498)
            row['bones']={str(fn):f.read(records+160*f.read(mapping+fn,'<B')+16,'<16f') for fn in (0,8,12)}
            w=f.read(a+0x23a0)
            row['weapon']={'joint':f.read(w+0x13cc),'pose':f.read(w+0x40,'<12f'),
                           'motion':f.read(w+0x4b4,'<H'),'frame':f.read(w+0x500,'<f')}
            row['coherent']=row['frame']==f.read(a+0x500,'<f') and row['motion']==f.read(a+0x4b4,'<H')
            if not args.skip_voices and rows and rows[-1]['frame']!=row['frame'] and row['frame']<100:
                assert f.k.ReadProcessMemory(f.h,0x10000000000+manager+64,voice_buffer,len(voice_buffer),None)
                raw=voice_buffer.raw;row['voices']=[]
                for index in range(count):
                    at=2784*index;res,request=struct.unpack_from('<2I',raw,at+12)
                    if res==resource and request<6:
                        row['voices'].append({'request':request,'serial':struct.unpack_from('<I',raw,at+52)[0],
                            'point':struct.unpack_from('<3f',raw,at+64),
                            'gain':struct.unpack_from('<f',raw,at+120)[0],
                            'mix':struct.unpack_from('<8f',raw,at+436)})
        rows.append(row);return row
    def wait(test,seconds=12):
        end=time.perf_counter()+seconds
        while time.perf_counter()<end:
            row=sample()
            if test(row):return row
            time.sleep(.004)
        raise TimeoutError(row)
    def idle():return wait(lambda s:s['state']==1 and s['action']<=5)
    def mark(name):marks.append({'name':name,'t':time.perf_counter()-start})
    def sheath():
        idle()
        if not f.read(a+0x2749,'<B')&1:f.command('X 8');time.sleep(2);idle()
        f.command('A 8');wait(lambda s:s['action']==4 and s['frame']>=22)
        f.command('R 24\nB 24');wait(lambda s:s['motion']==0x5e6 and s['frame']>=90)
    try:
        idle();mark('baseline');end=time.perf_counter()+1
        wait(lambda s:time.perf_counter()>=end)
        for rank in (0,3):
            for offset,value in zip((0x40,0x44,0x48),origin):f.fixture_bytes(a+offset,value,'<f')
            time.sleep(.2)
            f.fixture_values([(a+0x332c,6000.,'<f'),(a+0x3330,rank,'<I')])
            mark('big_setup_'+str(rank));sheath();mark('big_'+str(rank));f.command('R 10')
            if rank==3 and args.burst:f.command('burst 50 reported_big')
            wait(lambda s:s['motion'] in (0x5ef,0x5f5));idle()
        mark('timeout_setup');sheath();mark('timeout_hold')
        wait(lambda s:s['motion']==0x5f6);mark('timeout_exit');idle()
        mark('end')
    finally:
        done.set();thread.join(3);stream.close();audio.terminate();f.close()
        pcm=b''.join(chunks)
        with wave.open(str(f.run/'reported_loopback.wav'),'wb') as out:
            out.setnchannels(channels);out.setsampwidth(2);out.setframerate(rate);out.writeframes(pcm)
        arr=np.frombuffer(pcm,dtype='<i2').astype(float)/32768
        report={'run':str(f.run),'device':device,'marks':marks,'samples':rows,'recording_log_start':log_start,
                'recording_log_end':(f.run/'log.txt').stat().st_size,
                'plugin_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/plugins/mhw_ls_rebuild.nro'),
                'audio_arc_sha256':sha(f.run/'mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_audio.arc'),
                'voice_manager_diagnostics':not args.skip_voices,
                'audio_peak':float(np.max(np.abs(arr))) if arr.size else 0,
                'audio_rms':float(np.sqrt(np.mean(arr*arr))) if arr.size else 0}
        (f.run/'reported_motion_audio.json').write_text(json.dumps(report,indent=2),encoding='utf8')
        print(json.dumps({k:v for k,v in report.items() if k!='samples'},ensure_ascii=True))

if __name__=='__main__':main()
