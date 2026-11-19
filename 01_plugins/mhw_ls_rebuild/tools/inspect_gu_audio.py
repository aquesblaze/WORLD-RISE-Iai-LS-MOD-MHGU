"""Record native GU sound parameter consumers from the user's executable."""
import json,struct
from capstone import Cs,CS_ARCH_ARM,CS_MODE_ARM
from animation_port import ROOT,PROJECT,sha

def main():
    path=ROOT/'.cache/mhw_ls_combat/gu_text.bin';data=path.read_bytes();cs=Cs(CS_ARCH_ARM,CS_MODE_ARM)
    checks={0xbe5ae8:('ldrsh','r1, [r6, #0x14]'),0xbe5af0:('tst','r0, #4'),
        0xbe5b00:('ldrsh','r0, [r6, #0x16]'),0xbe5b04:('ldrsh','r1, [r6, #0x18]'),
        0xbe5b24:('bl','#0x7cc110'),0xbe5b6c:('ldrsh','r0, [fp, #6]'),
        0xbf3958:('ldr','r0, [r5, #0x2c]'),0xbf395c:('str','r0, [fp, #0x80]')}
    for address,expected in checks.items():
        i=next(cs.disasm(data[address:address+4],address))
        assert (i.mnemonic,i.op_str)==expected,(address,i.mnemonic,i.op_str)
    assert struct.unpack_from('<f',data,0xbe5c6c)[0]==2**-32
    spans={'bank_note_and_level':(0xbe57cc,0xbe5ae8),'bank_random_pitch_and_group':(0xbe5ae8,0xbe5b9c),
        'request_parameters':(0xbf394c,0xbf3b30),'native_delayed_start':(0xbe6450,0xbe67b0),
        'pitch_to_ratio':(0xbe23dc,0xbe260c),'gain_to_mix':(0xbe260c,0xbe2768)}
    result={'status':'VERIFIED_NATIVE_GU_AUDIO_PARAMETERS','text_sha256':sha(path),
        'code':{name:[f'{i.address:x} {i.mnemonic} {i.op_str}'for i in cs.disasm(data[a:z],a)]for name,(a,z)in spans.items()},
        'fields':{
            'SBKR_parameters':'Runtime voice fields start eight bytes before the serialized76-byte parameter block.',
            'SBKR_flags':'Serialized+1/runtime+9: bit0 fixed note, bit1 random level, bit2 random pitch, bit3 random pan, bit4 amplitude envelope, bit5 pitch envelope.',
            'SBKR_pitch':'Serialized+12 signed16 base; +14/+16 signed16 random min/max. Runtime BE598C adds base+min+(max-min)*U32/2^32.',
            'SBKR_group':'Final8-byte group: float linear volume at0, group ID byte4, signed16 pitch at6. Original LS group attenuates by4dB; private group must be unity.',
            'SRQR_pitch':'Row+44 signed32 constant cents -> native voice+128.',
            'SRQR_delay':'Row+48 unsigned32 + bank runtime+26 -> native voice+220. BE6450 gates actual voice start against the native elapsed timer.',
            'SRQR_gains':'Row+36/+40 dB converted separately to voice+120/+140. BE260C applies bank group/level and routes them separately to speaker matrix and auxiliary gain; they are not a random range.',
            'native_pitch':'BE23DC exp2((voice+128 + voice+2616 + Doppler cents)/1200).'},
        'runtime_acceptance':'probe_world_audio.py checks actual bank gain, dry gain, zero native delay, range, repeated-play variation and exact DSP transport.',
        'limits':['Native GU environmental auxiliary sends/distance curves are not evidence of World dynamic bus/RTPC equivalence.']}
    (PROJECT/'research/gu_audio_native.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf8')
    print(result['status'])

if __name__=='__main__':main()
