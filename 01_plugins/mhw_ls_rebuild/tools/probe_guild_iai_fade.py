"""Compare each post-Iai fade's actual travel against camera-centered stick movement."""
import argparse
import json
import math
import time
import wave
from pc_fixture import Fixture
from probe_guild_ownership import draw, neutral, wait


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--record',action='store_true',help='Save the game output and mark both native handoffs')
    args=parser.parse_args()
    f = Fixture()
    cases = []
    audio=stream=None
    chunks=[]
    def mark():
        return dict(log=(f.run/'log.txt').stat().st_size,samples=sum(map(len,chunks))//(2*channels))
    try:
        if args.record:
            import pyaudiowpatch as pa
            audio=pa.PyAudio()
            device=audio.get_default_wasapi_loopback()
            rate=int(device['defaultSampleRate'])
            channels=device['maxInputChannels']
            def capture(data,frames,clock,status):
                chunks.append(data)
                return None,pa.paContinue
            stream=audio.open(format=pa.paInt16,channels=channels,rate=rate,input=True,
                input_device_index=device['index'],frames_per_buffer=480,stream_callback=capture)
        for side in ('LEFT', 'RIGHT'):
            def setup():
                f.camp_station()
                draw(f)
                f.command('L 5')
                time.sleep(.7)
            setup()
            origin = f.state()['position']
            f.command(f'STICK_{side} 25')
            time.sleep(.7)
            walked = f.state()['position']
            direction = [walked[k] - origin[k] for k in (0, 2)]
            length = math.hypot(*direction)
            assert length > 15, direction
            setup()
            f.command('A 6')
            wait(f, lambda s: s['motion'] == 0x569 and s['frame'] >= 22)
            f.command('R 24\nB 24')
            wait(f, lambda s: s['motion'] == 0x5e6 and s['frame'] >= 82)
            f.command('X 6')
            wait(f, lambda s: s['motion'] == 0x5ee and s['frame'] >= 25)
            f.command(f'STICK_{side} 35')
            before = wait(f, lambda s: s['motion'] == 0x5ee and s['frame'] >= 32)
            if stream:begin=mark()
            f.command('X 5\nA 5')
            slots = {8:0x567, 28:0x581, 29:0x580}
            start = wait(f, lambda s: s['state'] == 16 and slots.get(s['action']) == s['motion'])
            end = wait(f, lambda s: s['action'] == start['action'] and s['frame'] >= 48)
            delta = [end['position'][k] - start['position'][k] for k in (0, 2)]
            along = sum(a*b for a,b in zip(delta,direction))/length
            cases.append(dict(side=side, stick_reference=direction, pressed=before['frame'],
                              action=start['action'], motion=end['motion'], travel=delta,
                              along_stick=along, heading=before['heading']))
            neutral(f)
            if stream:cases[-1].update(audio_start=begin,audio_end=mark())
            print(cases[-1],flush=True)
        assert {c['action'] for c in cases} == {28,29} and all(c['along_stick']>10 for c in cases),cases
    finally:
        if stream:
            stream.stop_stream()
            stream.close()
            with wave.open(str(f.run/'iai_side_fades.wav'),'wb') as out:
                out.setparams((channels,2,rate,0,'NONE','not compressed'))
                out.writeframes(b''.join(chunks))
        if audio:audio.terminate()
        name='iai_side_fades_recorded' if args.record else 'iai_side_fades'
        (f.run/(name+'.json')).write_text(json.dumps(cases,indent=2))
        f.close()


if __name__ == '__main__':
    main()
