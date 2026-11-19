"""Persist the original Helm sampler/tail evidence, without distributing binaries."""
import json
from capstone import Cs,CS_ARCH_X86,CS_MODE_64,CS_ARCH_ARM,CS_MODE_ARM
from inspect_world_params import ROOT,PROJECT

def main():
    native=ROOT/'.cache/mhw_native'
    text=(native/'text.bin').read_bytes()
    cs=Cs(CS_ARCH_X86,CS_MODE_64)
    spans={
        'collision_lingering_reader':(0x27dbf0,0x27dc22),
        'collision_lingering_use':(0x12d716e,0x12d71db),
        'collision_ledger_frame_clock':(0x12dd59c,0x12dd622),
        'first_shell_regen':(0x21253a6,0x212541e),
        'tail_fallback':(0x2125425,0x2125682),
        'contact_remaining_timer':(0x212265b,0x212274d),
        'genuine_last_shell':(0x212221f,0x21222a9),
        'first_shake_shell':(0x21256df,0x2125720),
    }
    code={name:[f'{i.address-0x140000000:x} {i.mnemonic} {i.op_str}'
                for i in cs.disasm(text[a-4096:z-4096],0x140000000+a)] for name,(a,z) in spans.items()}
    gu=(ROOT/'.cache/mhw_ls_combat/gu_text.bin').read_bytes();arm=Cs(CS_ARCH_ARM,CS_MODE_ARM)
    evidence=[f'{i.address:x} {i.mnemonic} {i.op_str}' for i in arm.disasm(gu[0x171350:0x1713b8],0x171350)]
    report={'source_snapshot':json.loads((native/'source.json').read_text()),'evidence':code,
        'rules':{
            'primary':'COL82 attack40: MV/element/status/stun/part/hitlag all zero. The real blade contacts only record targets and points.',
            'cooldown':'Lingering_Hurtbox=1, Frame_Delay=1.5; native ledger subtracts simulation frame delta (global system+94).',
            'slots':'Up to seven real primary contacts. First delay0.4 seconds; later timers copy the preceding remaining timer+0.05. Timers stop decrementing after crossing zero, so a late recontact cannot use an old absolute deadline.',
            'fallback':'When the last genuine contact emits, all still-empty tail slots copy its target/bone/local point, each with delay0.05 seconds.',
            'point':'Resolve inverse-bone-local contact against the current target bone at emission. Shell position then remains fixed.',
            'regen':'First emitted shell starts10 seconds (white/yellow) or15 seconds (red) of regeneration, independently from Iai.',
            'lifetime':'Every emitted source shell lives0.5 seconds.',
            'last_shell':'Ordinal6 selects last SHLP for genuine and fallback contacts. The normal and last files differ only in COL selection; source last part multiplier3.0 versus normal0.9. Both have zero source hitlag.',
            'shake_shell':'wp03_param serialized1544/runtimea6c is0: ordinal0 selects the shake SHLP. Its COL differs from normal by camera-shake selector Unk23=11; native meaning still to verify.'},
        'clock_read_only_observation':{'process':'MonsterHunterWorld.exe','version':'421810',
            'pointer_rva':'0x51c4148','frame_delta_offset':'0x94','seconds_delta_offset':'0xa0',
            'sample_frame_delta':1.000002,'sample_seconds_delta':0.0166667,
            'note':'Observed from the existing training-area process on2026-11-11; live values are not immutable source constants.'},
        'gu_sampler':{'native_type42_path':evidence,
            'hook':'170968 only for this controller-owned Helm primary; dispatch171350 type42 after native intersection filtering.',
            'purpose':'Record real contact without GU minimum damage/hitstop/sharpness effects.'},
        'limits':['Source shell VFX/audio and first-shell camera shake remain unported.',
                  'Seven-hit fixture acceptance is distinct from multi-target and complete terrain acceptance.']}
    (PROJECT/'research/world_helm_native.json').write_text(json.dumps(report,indent=2))
    print('Recorded original Helm cooldown, tail fallback, regeneration and GU marker-contact evidence')

if __name__=='__main__':main()
