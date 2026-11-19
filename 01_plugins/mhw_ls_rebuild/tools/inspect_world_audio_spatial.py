"""Resolve the selected World weapon's rigid sound anchors from local code/data."""
import json,struct
import numpy as np
from capstone import Cs,CS_ARCH_X86,CS_MODE_64
from animation_port import ROOT,PROJECT,sha,read_lmt_file

def main():
    model=__import__('pathlib').Path('D:/MHW_extract/wp/swo/swo001/mod/swo001.mod3')
    motion=model.parents[2]/'mot/wg03_00/wg03_00.lmt'
    raw=model.read_bytes();n=struct.unpack_from('<H',raw,6)[0];at=struct.unpack_from('<Q',raw,48)[0]
    assert raw[:5]==b'MOD\0\xed' and 0<n<255
    mapping=raw[at+152*n:at+152*n+512];bones=[];matrices=[]
    for i in range(n):
        function,parent=struct.unpack_from('<hB',raw,at+24*i)
        m=np.array(struct.unpack_from('<16f',raw,at+24*n+64*i)).reshape(4,4).T
        assert parent==255 or parent<i
        matrices.append(m if parent==255 else matrices[parent]@m)
        bones.append({'index':i,'function':function,'parent':parent})
    anchors={}
    for function in (1,100):
        index=mapping[function];assert bones[index]['function']==function
        chain=[];i=index
        while i!=255:chain.append(bones[i]['function']);i=bones[i]['parent']
        anchors[function]={'chain':chain,'root_position':matrices[index][:3,3].tolist()}
    actions={a.id:a for a in read_lmt_file(motion).actions}
    animated={t.header.bone_id for k in (0,1,2,3)for t in actions[k].tracks}
    assert animated=={2} and all(not animated.intersection(v['chain'])for v in anchors.values())
    assert anchors[1]['root_position']==[0.,0.,0.] and anchors[100]['root_position']==[0.,0.,80.]
    textpath=ROOT/'.cache/mhw_native/text.bin';text=textpath.read_bytes();cs=Cs(CS_ARCH_X86,CS_MODE_64)
    checks={0x2116428:('mov','r12d, 1'),0x21169ac:('mov','r8d, r12d'),
        0x21169af:('mov','rdx, rdi'),0x21169b5:('call','0x14130c8e0'),
        0x130ba6b:('call','0x14130c750'),0x130ba75:('or','dword ptr [rbp + 0x1f], 0x10'),
        0x22ff32f:('mov','rax, qword ptr [rbx + 0x30]'),0x22ff333:('mov','qword ptr [rdi + 0x88], rax'),
        0x230d6b5:('mov','edx, dword ptr [rsi + 0x1c]'),0x230d6d5:('call','qword ptr [rax + 0x120]')}
    for address,expected in checks.items():
        i=next(cs.disasm(text[address-0x1000:address-0x1000+16],0x140000000+address))
        assert (i.mnemonic,i.op_str)==expected,(address,i.mnemonic,i.op_str)
    cues=json.loads((PROJECT/'research/world_motion_audio.json').read_text())['weapon_one_shots']
    assert len(cues)==79 and {c['target_unit']for c in cues}=={1}
    report={'status':'SOURCE_WEAPON_AUDIO_ANCHORS_RESOLVED','model':str(model),'model_sha256':sha(model),
        'motion':str(motion),'motion_sha256':sha(motion),'text_sha256':sha(textpath),'anchors':anchors,
        'native_checks':{hex(a):list(v)for a,v in checks.items()},
        'semantics':['All 79 selected weapon cues target timeline unit1, the registered main weapon.',
            'WWEV bone1/100 are rigid on the selected World weapon, including draw/close motions0..3.',
            'GU retains its weapon model and animation. Use its posed root and source local anchor0/80, not hunter origin or a guessed same-numbered GU bone.'],
        'limits':['This resolves the explicit World model1 baseline, not per-model Wwise material selection.',
            'Iai effect-bound WSPL speakers and World distance/bus curves need separate acceptance.']}
    (PROJECT/'research/world_audio_spatial_source.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(report['status'],anchors)

if __name__=='__main__':main()
