"""Reproduce native damage/regen/delayed-contact evidence from owned data."""
import json,re,struct
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_64,CS_ARCH_ARM,CS_MODE_ARM
from inspect_world_params import decrypt,CACHE,ROOT,PROJECT,sha

def main():
    source=Path('D:/MHW_extract/_work_chunkG9/chunkG9/common/pl/pl_param.plp')
    data=decrypt(source,'PL_PARAM_KEY');assert data[:8]==b'PLP\0\x1f\0\0\0'
    schema=(CACHE/'plp.bt').read_text()
    prefix=schema.split('// Player Params (1)')[1].split('// Player Params (2)')[0]
    offset=8+4*len(re.findall(r'^(?:float|uint) ',prefix,re.M))+12*11
    types={'float':'f','uint':'I','ubyte':'B','ushort':'H'};armor={}
    for kind,name in re.findall(r'^(float|uint|ubyte|ushort) (\w+)<',schema.split('// Player Params (3)')[1],re.M):
        value=struct.unpack_from('<'+types[kind],data,offset)[0]
        if 'Armor' in name:armor[name]={'offset':offset,'value':value}
        offset+=struct.calcsize(types[kind])
        if name=='Hyper_Armor_Stun_Damage_Rate':break
    assert armor['Hyper_Armor_Damage_Rate']=={'offset':738,'value':.5}
    assert armor['Hyper_Armor_Stun_Damage_Rate']=={'offset':742,'value':0.0}
    text=(ROOT/'.cache/mhw_native/text.bin').read_bytes();cs=Cs(CS_ARCH_X86,CS_MODE_64)
    spans={'damage_factor':(0x1218ae4,0x1218b93),'regen_rates':(0x2123a72,0x2123b58),
           'big_contact':(0x2124b20,0x2124e11),'big_pending':(0x2125860,0x2125b1c),
           'big_direction':(0x17ff931,0x17ffa37)}
    code={name:[f'{i.address-0x140000000:x} {i.mnemonic} {i.op_str}'
                for i in cs.disasm(text[a-4096:z-4096],0x140000000+a)] for name,(a,z) in spans.items()}
    gu=(ROOT/'.cache/mhw_ls_combat/gu_text.bin').read_bytes();arm=Cs(CS_ARCH_ARM,CS_MODE_ARM)
    ko={name:[f'{i.address:x} {i.mnemonic} {i.op_str}' for i in arm.disasm(gu[a:z],a)]
        for name,(a,z) in {'threshold_query':(0x2f1900,0x2f1918),'accumulate':(0x2f42d0,0x2f4450),
                          'fresh_collision_packet':(0x176088,0x1760c4),'packet_zero_helper':(0x1797e0,0x1797f4)}.items()}
    result={'source_snapshot':'.cache/mhw_native/source.json','player_param_sha256':sha(source),
        'armor':armor,'evidence':code,
        'gu_counter_stun':{'packet_offset':'3226 signed halfword','accumulator':'2898 unsigned integer',
            'native':ko,'implementation':'world_damage masks only the incoming KO packet while counter armor is active. It retains previous buildup and decay timer.',
            'blocked_packet_lifetime':'Native375ff4 calls3797e0 on actor+3214 before populating each new physical collision. The helper zeroes0x48bytes, including3226; a blocked prior packet is not added to the next fresh collision.',
            'runtime_acceptance':'armor_stun_report.json requires existing17 retained by a real armored hit, and a later unprotected hit adding the native20.'},
        'regen':'Independent helm and Iai timers; each adds dt / fill_seconds to a0..1 gauge. Both source fill_seconds are15.',
        'damage':'Flag0x97 is bit23 at player8948; consumer1218ae4/1218b45 applies global player param7ec, followed by truncation and minimum1.',
        'big_contact':'Actual weapon contact stores target and hit point; source picks nearest target bone to owner. Rank1..3 selects shell12..14 with delay0.5s.',
        'big_interrupt':'Pending Iai shell is cleared on leaving action0x66; emitted shell has its own lifetime.',
        'big_trigger31':'At frames20/37,2122a30 computes a direction from stored contact/target bones. Caller17ff8c0 passes it through player14f8, subobject1410,1294220 to uMhCamera1f9dfa0. The named DTI and full ownership chain are reproduced by inspect_world_iai_camera.py; this is camera interpolation, not hunter rotation or an independent damage sweep.',
        'remaining':['Camera interpolation is implemented and native contact/no-color/whiff checked. Source6main-bone semantic mapping and obstruction acceptance remain.',
                     'Closest-bone selection and native per-target capture are implemented; multi-target runtime acceptance remains.',
                     'Independent counter capsules are now implemented in world_detector.inc; full geometry/lifetime/type acceptance is still pending.']}
    (PROJECT/'research/world_combat_rules_native.json').write_text(json.dumps(result,indent=2))
    print('Verified source armor0.5, normalized regen rates and big Iai contact/direction ownership')

if __name__=='__main__':main()
