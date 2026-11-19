"""Resolve World action classes through their actual DTI constructors.

Consumes the local, read-only normal-process text snapshot and the matching PE
rdata cache. The table preceding a class-name string is NOT necessarily that
class's DTI table. Follow the constructor's name reference and installed table.
No process writes; reports contain addresses/instructions, not game binaries.
"""
from pathlib import Path
import json
import struct
from capstone import Cs, CS_ARCH_X86, CS_MODE_64

ROOT = Path(__file__).resolve().parents[3]
PROJECT = Path(__file__).resolve().parents[1]
BASE, TEXT, RDATA = 0x140000000, 0x1000, 0x2e13000


def resolve(names):
    text = (ROOT/'.cache/mhw_native/text.bin').read_bytes()
    data = (ROOT/'.cache/mhw_native/rdata.bin').read_bytes()
    cs = Cs(CS_ARCH_X86, CS_MODE_64)
    cs.detail = True
    refs = {}
    p = 0
    while True:
        p = text.find(b'\x48\x8d', p)
        if p < 0:
            break
        if p+7 <= len(text) and text[p+2] & 0xc7 == 5:
            target = TEXT+p+7+struct.unpack_from('<i', text, p+3)[0]
            refs.setdefault(target, []).append(TEXT+p)
        p += 2

    def code(rva, limit=8192):
        for ins in cs.disasm(text[rva-TEXT:rva-TEXT+limit], BASE+rva):
            if ins.mnemonic == 'int3':
                break
            yield ins

    def table_after(rva, limit, factory=False):
        for ins in code(rva, limit):
            if ins.mnemonic == 'lea' and '[rip' in ins.op_str:
                target=ins.address+ins.size+ins.operands[1].mem.disp-BASE
                if ins.op_str.startswith('rax, [rip') or (factory and RDATA <= target < RDATA+len(data)):
                    return target
        raise ValueError(f'No table assignment after {rva:x}')

    result = {}
    for name in names:
        at = data.index(name.encode()+b'\0')+RDATA
        candidates = refs.get(at, [])
        if len(candidates) != 1:
            raise ValueError((name, candidates))
        dti = table_after(candidates[0], 96)
        factory = struct.unpack_from('<Q', data, dti-RDATA+8)[0]-BASE
        vtable = table_after(factory, 160, factory=True)
        count = 13 if name.startswith('nHmAction') else 7
        methods = [x-BASE for x in struct.unpack_from('<'+'Q'*count, data, vtable-RDATA)]
        result[name] = dict(name_rva=at, constructor_ref=candidates[0],
            dti=dti, factory=factory, vtable=vtable, methods=methods)
        if name.startswith('nHmAction'):
            result[name]['handlers'] = {
                role: {'rva':methods[index], 'instructions':[
                    f'{i.address-BASE:08x} {i.mnemonic} {i.op_str}'
                    for i in code(methods[index])]}
                for role,index in [('init',6),('update',7),('exit',8)]}
    return result


if __name__ == '__main__':
    names = ['nHmAction::Wp03::'+s for s in [
        'cIaigiriStart','cIaigiriLoop','cIaigiriV','cIaigiriH',
        'cFinishAttack','cFinishStep','cFinishStepJump','cFinishAirAttack','cFinishLand']]
    names += ['nHmTransition::'+s for s in [
        'cWp03Iaigiri','cWp03SuccessMikiriAtkHit','cWp03RenkiRateMikiri']]
    report = {'method':'DTI constructor name reference -> assigned DTI -> factory -> action vtable',
              'source_snapshot':'.cache/mhw_native/source.json', 'classes':resolve(names)}
    (PROJECT/'research/world_action_native.json').write_text(
        json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    for name, row in report['classes'].items():
        print(name, hex(row['vtable']), [hex(x) for x in row['methods'][6:9]])
