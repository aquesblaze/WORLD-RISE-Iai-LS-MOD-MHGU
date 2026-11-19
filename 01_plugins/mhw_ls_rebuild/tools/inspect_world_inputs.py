"""Follow source FSM names through native command construction to TIML bits.

The three layers use different IDs. In particular the instruction preparing
the NEXT map key precedes the assignment to the CURRENT command object.
Read-only: consumes the owned executable and its matching text snapshot.
"""
from pathlib import Path
import hashlib,json,struct
from capstone import Cs,CS_ARCH_X86,CS_MODE_64

ROOT=Path(__file__).resolve().parents[3]
PROJECT=Path(__file__).resolve().parents[1]
BASE=0x140000000
EXE=Path(r'D:\APP\steam\steamapps\common\Monster Hunter World\MonsterHunterWorld.exe')

def main():
    text=(ROOT/'.cache/mhw_native/text.bin').read_bytes()
    data=(ROOT/'.cache/mhw_native/rdata.bin').read_bytes()
    source=json.loads((ROOT/'.cache/mhw_native/source.json').read_text())
    if hashlib.sha256(EXE.read_bytes()).hexdigest()!=source['exe_sha256']:
        raise ValueError('Executable does not match the inspected snapshot')
    cs=Cs(CS_ARCH_X86,CS_MODE_64);cs.detail=True
    def code(start,end):return list(cs.disasm(text[start-0x1000:end-0x1000],BASE+start))
    instructions=code(0xb2e4e0,0xb2fd2c)
    wanted={'△':'X','○':'A','△+○':'FADE','△+○+←':'FADE_LEFT',
            '△+○+→':'FADE_RIGHT','R+△':'THRUST','R+○':'FORESIGHT','回避':'ROLL'}
    names={}
    for j,i in enumerate(instructions):
        if i.mnemonic!='lea' or '[rip' not in i.op_str:continue
        p=i.address+i.size+i.operands[1].mem.disp-BASE-0x2e13000
        if not 0<=p<len(data):continue
        name=data[p:data.index(0,p)].decode('utf8',errors='replace')
        if name not in wanted:continue
        ret=next(v for v in instructions[j+1:] if v.mnemonic=='mov' and
                 v.op_str.startswith('eax, 0x'))
        names[wanted[name]]={'name':name,'property':int(ret.op_str.split(', ')[1],0),
                            'name_ref_rva':i.address-BASE,'property_return_rva':ret.address-BASE}
    names['R']={'name':'R','property':38,'property_return_rva':0xb2f0e2}
    assert any(i.address==BASE+0xb2f0e2 and i.op_str=='eax, 0x26' for i in instructions)
    mapping={};key=obj=None
    for i in code(0x17c5de0,0x17c8a70):
        if i.mnemonic=='mov' and i.op_str.startswith('dword ptr [rbp + 0x5bc],'):
            key=int(i.op_str.split(', ')[1],0)
        if i.mnemonic=='call' and i.op_str=='0x14026b550':obj=key
        if i.mnemonic=='mov' and i.op_str.startswith('dword ptr [rax + 0x28], 0x'):
            mapping[obj]=(int(i.op_str.split(', ')[1],0),i.address-BASE)
    with EXE.open('rb') as f:
        h=f.read(4096);pe=struct.unpack_from('<I',h,60)[0]
        count=struct.unpack_from('<H',h,pe+6)[0];size=struct.unpack_from('<H',h,pe+20)[0]
        for j in range(count):
            off=pe+24+size+j*40
            vs,va,rs,raw=struct.unpack_from('<4I',h,off+8)
            if va<=0x3eeabf0<va+rs:
                f.seek(raw+0x3eeabf0-va);bits=struct.unpack('<137i',f.read(548));break
        else:raise ValueError('Command permission table missing')
    for row in names.values():
        cmd,at=mapping[row['property']];bit=bits[cmd]
        row.update(command=cmd,command_assignment_rva=at,execute_bit=bit,
                   word=bit//32,shift=bit%32-1)
        assert bit%2==1
    ctor=code(0xef8c18,0xef8c37)
    assert any(i.op_str=='dword ptr [rbx + 0x28], 0x18' for i in ctor)
    names['SHEATHE']={'name':'居合斬り','property':0x276,'command':24,
        'command_assignment_rva':0xef8c1f,'execute_bit':bits[24],
        'word':bits[24]//32,'shift':bits[24]%32-1,
        'class':'nHmTransition::cWp03Iaigiri','edge_mode_assignment_rva':0x177a8ed}
    report={'exe_sha256':source['exe_sha256'],'command_table_rva':0x3eeabf0,
        'command_permission_reader_rva':0x1230070,'inputs':names,
        'verification':'Static native name lookup, instance initialization, command permission lookup; runtime timing comparison pending'}
    (PROJECT/'research/world_input_native.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    header='/* Generated from native FSM -> command -> permission-bit evidence. */\n#pragma once\n'
    header+='typedef struct {unsigned word,shift;} WInput;\n'
    for key,row in names.items():header+=f'static const WInput WI_{key}={{{row["word"]}u,{row["shift"]}u}};\n'
    (PROJECT/'c/world_inputs.h').write_text(header,encoding='utf8')
    print(json.dumps(names,ensure_ascii=True))

if __name__=='__main__':main()
