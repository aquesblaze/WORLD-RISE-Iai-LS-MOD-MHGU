#include <assert.h>
#include "../c/world_damage_compat.h"

int main(void)
{
    uint32_t player[]={0xe92d4ff0u,0xe28db01cu};
    uint32_t cb_jump[]={0xe51ff004u,4};
    uint32_t cb[]={0xe92d48f0u,0xe28db010u,0xe24dd030u,0xe59f6164u,
        0xe1a04000u,0xe08f6006u,0xe5965024u,0xeb00244bu};
    assert(world_player_damage_entry_matches(player,0));
    assert(world_player_damage_entry_matches(cb_jump,cb));
    assert(!world_player_damage_entry_matches(cb_jump,0));
    for(unsigned i=0;i<8;++i){cb[i]^=1;assert(!world_player_damage_entry_matches(cb_jump,cb));cb[i]^=1;}
    player[1]^=1;assert(!world_player_damage_entry_matches(player,0));
    uint32_t escape[]={0xe92d4ff0u,0xe28db01cu,0xe24dd00cu,0xe59f51dcu,
        0xe1a04003u,0xe1a09002u,0xe1a0a001u,0xe08f5005u,0xe1a07000u,0xe595803cu,
        0xeb000ef4u,0xe5950020u};
    assert(world_player_damage_entry_matches(cb_jump,escape));
    for(unsigned i=0;i<12;++i){escape[i]^=1;assert(!world_player_damage_entry_matches(cb_jump,escape));escape[i]^=1;}
    uint32_t floor[]={0xe92d4df0u,0xe28db018u};
    uint32_t drink[]={0xe92d4ff0u,0xe24dd004u,0xed2d8b06u,0xe24dd010u,
        0xe1a08003u,0xe1a06002u,0xe1a07001u,0xe1a04000u,0xebfff54bu,0xe3500000u,
        0x0a00000au,0xe59fc57cu};
    assert(world_floor_entry_matches(floor,0));
    assert(world_floor_entry_matches(cb_jump,drink));
    assert(!world_floor_entry_matches(cb_jump,0));
    assert(!world_floor_entry_matches(cb_jump,escape));
    for(unsigned i=0;i<12;++i){drink[i]^=1;assert(!world_floor_entry_matches(cb_jump,drink));drink[i]^=1;}
    floor[1]^=1;assert(!world_floor_entry_matches(floor,0));
    uint32_t native[] = {0xe92d41f0u, 0xe24dd010u};
    uint32_t jump[] = {0xe51ff004u, 1};
    uint32_t damage_display[] = {
        0xe92d4ff0u, 0xe28db01cu, 0xe24dd044u,
        0xe58d001cu, 0xe1a06002u, 0xe59f0268u
    };
    assert(world_damage_entry_matches(native, 0));
    assert(world_damage_entry_matches(jump, damage_display));
    uint32_t ff14[]={0xe92d4ff0u,0xe28db01cu,0xe24dd01cu,0xe1a06000u,
        0xe59f0108u,0xe1a07003u,0xe1a04002u,0xe08f0000u,0xe1a05001u,0xe5900030u,
        0xe58d0018u,0xeb0019f7u};
    assert(world_damage_entry_matches(jump,ff14));
    for(unsigned i=0;i<12;++i){ff14[i]^=1;assert(!world_damage_entry_matches(jump,ff14));ff14[i]^=1;}
    assert(!world_damage_entry_matches(jump,escape));
    assert(!world_damage_entry_matches(jump, 0));
    damage_display[5] ^= 1;
    assert(!world_damage_entry_matches(jump, damage_display));
    native[1] ^= 1;
    assert(!world_damage_entry_matches(native, 0));
    return 0;
}
