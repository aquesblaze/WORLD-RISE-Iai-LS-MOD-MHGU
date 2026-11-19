"""Reproduce local source evidence for Iai turn adjustment and Quick Sheathe."""
import json,struct
from capstone import Cs,CS_ARCH_X86,CS_MODE_64,CS_ARCH_ARM,CS_MODE_ARM
from inspect_world_params import decrypt,SOURCE,ROOT,PROJECT,sha

def main():
    source=SOURCE/'wp03_param.w03p';b=decrypt(source,'PL_PARAM_KEY')
    turn=struct.unpack_from('<fffBf',b,8+19*17)
    assert turn[:4]==(20.,-1.,60.,1)
    assert abs(struct.unpack_from('<f',b,1340)[0]-.4)<1e-6
    text=(ROOT/'.cache/mhw_native/text.bin').read_bytes()
    cs=Cs(CS_ARCH_X86,CS_MODE_64)
    def code(a,z):return [f'{i.address-0x140000000:x} {i.mnemonic} {i.op_str}' for i in cs.disasm(text[a-4096:z-4096],0x140000000+a)]
    gu=(ROOT/'.cache/mhw_ls_combat/gu_text.bin').read_bytes();arm=Cs(CS_ARCH_ARM,CS_MODE_ARM)
    result={'source_sha256':sha(source),'snapshot':'.cache/mhw_native/source.json',
      'iai_group19':{'serialized_offset':8+19*17,'minimum_angle':turn[0],'backward_limit':turn[1],
          'maximum_angle':turn[2],'clamp_not_fixed_step':turn[3],'seconds':turn[4]},
      'native_selection':code(0x118e405,0x118e44e),
      'native_adjustment':code(0x118b929,0x118ba5c),
      'turn_groups':{str(n):list(struct.unpack_from('<fffBf',b,8+n*17)) for n in (1,4,6,19)},
      'turn_easing':{'formula':'quadratic ease out: t*(2-t)',
          'selection':'1f755c0 passes mode2 to2174cb0; table34df1b0 index2 points to2174bc0',
          'native':code(0x2174bc0,0x2174bdf),
          'implementation':'world_core.c:w_rotation, once per source trigger11; entry heading retained'},
      'continuous_turn':{'field':'PlMotionCommon+7c mTurnSpeed',
          'native_common_update':code(0x1f6be8f,0x1f6bf0b),
          'native_wrapper':code(0x1f780b0,0x1f780e7),
          'degree_to_radian_consumer':code(0x1c0370c,0x1c0373c),
          'units':'degrees per simulation second; source common172 frames0..20=80, then0',
          'implementation':'world_core.c:w_rotation, with fractional GU-heading carry'},
      'air_entry_turn':{'maximum_degrees':struct.unpack_from('<f',b,1472)[0],
          'native':code(0x17fe08f,0x17fe0f2),
          'implementation':'world_core.c:enter(W_AIR) limits the initial correction to60deg'},
      'sheathe_bonus':{'world_formula':'1 + (ordinary skill factor - 1) *0.4 (native); this build overrides to 1.40',
          'world_native':code(0x17ffbb9,0x17ffc3e),'gu_skill_ids':[0x5d,0x13a,0x117,0x129],
          'gu_ordinary_factor':1.4,'ported_special_factor':1.40,
          'gu_native':[f'{i.address:x} {i.mnemonic} {i.op_str}' for i in arm.disasm(gu[0x2cde38:0x2cde98],0x2cde38)]},
      'source_training_small_R':{'sequence':'tools/world_inputs/small_spirit_follow.json',
          'observed_history':'Thrust -> Special Sheathe -> Iai Slash -> Spirit Slash I',
          'screenshot':str(ROOT/'.cache/mhw_game_input/capture_1794389377478288100/step_07.png'),
          'fsm':'node64 condition240(R only) -> link82 motion363 -> node1 action1001',
          'limits':'Normal input and on-screen move names verified. Capture delays do not establish earliest input frames.'},
      'remaining':['More weapon/equipment and terrain runtime comparisons are still required.']}
    (PROJECT/'research/world_motion_rules_native.json').write_text(json.dumps(result,indent=2))
    print('Verified Iai group19 field roles, source sheathe bonus formula and GU skill factor')

if __name__=='__main__':main()
