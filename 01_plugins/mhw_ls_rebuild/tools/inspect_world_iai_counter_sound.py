"""Verify the original Iai detector's contact-only EPV call and its embedded sounds."""
import hashlib
import json
import struct
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_64
from animation_port import PROJECT, ROOT, sha
from inspect_world_audio import chunks
from inspect_world_audio_native import wwev
from inspect_world_presentation import epv, epvsp

def main(output):
    native=ROOT/'.cache/mhw_native'
    source=ROOT/'.cache/mhw_ls_presentation/source'
    raw=(native/'text.bin').read_bytes()
    meta=json.loads((native/'source.json').read_text())
    cs=Cs(CS_ARCH_X86,CS_MODE_64)
    evidence={}
    def check(rva,expected):
        at=rva-meta['text_rva']
        op=next(cs.disasm(raw[at:at+16],meta['base']+rva))
        actual=op.mnemonic+' '+op.op_str
        assert actual==expected,(hex(rva),actual)
        evidence[hex(rva)]=actual
    for rva,op in {
        0x17fe22e:'call 0x142123050',0x21230e9:'mov edx, 0xb',
        0x2123108:'mov byte ptr [rax + 0x3168], 1',
        0x21038ce:'cmp eax, 8',0x21038d1:'jne 0x1421039d8',
        0x210397e:'je 0x1421039d8',0x21039a4:'movzx edx, byte ptr [rbx + 0x3168]',
        0x21039af:'cmp edx, 1',0x21039b4:'call 0x142124f70',
        0x2124f87:'cmp eax, 3',0x2124f9e:'add eax, -0x65',0x2124fa1:'cmp eax, 1',
        0x2124fa4:'ja 0x142125053',0x2124fb1:'xor r8d, r8d',
        0x2124fb4:'mov byte ptr [rbx + 0x2ced], 1',0x2124fbb:'mov edx, 0x7d4',
        0x2124fcc:'call 0x140ae0d70',
        0x21250ae:'xor r8d, r8d',0x21250b8:'mov edx, 0x7d4',
        0x21250c4:'call 0x140ae0d70',0xae0d70:'jmp 0x140add670',
        0xadd685:'mov ebx, r8d',0xadd68d:'mov edi, edx',0xadd6e7:'mov r9d, edi',
        0xadd72b:'mov dword ptr [rsp + 0x20], ebx',0xadd72f:'call qword ptr [rax + 0x108]'
    }.items():check(rva,op)
    ep=source/'wp/swo/epv/hm_wp03.epv3'
    sp=source/'wp/swo/sound/hm_wp03.epvsp'
    ev=source/'sound/pl/hm_wp03_epvsp_snd_ev.wwev'
    bank=source/'sound/wwise/Windows/wp03_swo_epvsp.nbnk'
    provider=epv(ep)
    group=next(g for g in provider['groups'] if g['group_id']==2004)
    record=next(r for r in group['records'] if r['record_id']==0)
    assert record['paths'][0].endswith('wp03_040')
    bindings=[r for r in epvsp(sp)['requests'] if (r['group_id'],r['record_id'])==(2004,0)]
    assert len(bindings)==1 and bindings[0]['request']==25510
    links=json.loads((PROJECT/'research/world_audio_source.json').read_text(encoding='utf8'))
    assert sha(bank)==links['source']['banks'][bank.name] and sha(ev)==links['source']['wwev']
    embedded=chunks(bank.read_bytes())
    media={i:embedded[b'DATA'][p:p+n] for i,p,n in struct.iter_unpack('<3I',embedded[b'DIDX'])}
    stems=[]
    for r in wwev(ev)['rows']:
        if r['request']!=25510:continue
        node=next(graph['graph'] for graph in links['links'] if graph['event']==r['event'])
        chain=[]
        for kind in ('CAkEvent','CAkActionPlay','CAkRanSeqCntr','CAkSound'):
            assert node['class']==kind
            chain.append([kind,node['id']])
            if kind!='CAkSound':node,=node['children']
        ident,=node['media']
        assert media[ident][:4]==b'RIFF'
        stems.append(dict(event=r['event'],speaker=r['speaker_id'],media=ident,chain=chain,
                          wem_sha256=hashlib.sha256(media[ident]).hexdigest()))
    assert [(r['speaker'],r['media']) for r in stems]==[(2,367971202),(3,387684418)]
    report=dict(exe_sha256=meta['exe_sha256'],instructions=evidence,resources={p.name:sha(p) for p in (ep,sp,ev,bank)},
                group=2004,record=0,effect=record['paths'][0],binding=bindings[0],stems=stems,
                scope='Detector shell 11, mode 1, accepted collision event 8; action set 3, actions 0x65 and 0x66. The EPV call takes group and record, not TIML WorkNo.')
    output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('Verified original Iai success request 25510 and both embedded WEMs')
if __name__=='__main__':main(Path(sys.argv[1]))
