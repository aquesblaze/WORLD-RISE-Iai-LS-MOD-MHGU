"""Regression checks for the private EFX-to-EFL geometry and effect selection."""
import struct
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from animation_port import ROOT, PROJECT, WORLD_MODEL, BODY_MAP, read_skeleton
from build_world_simple_fx import entries
from world_helm_iai_fx import EFL, attributes, emitter, single_parts
from world_thrust_foresight_fx import source_selection
from prepare_world_effect_textures import mtgu_tex
import numpy as np


def main():
    source_selection()
    bones=read_skeleton(WORLD_MODEL,True)
    inverse={world:gu for gu,world in BODY_MAP.items()}
    assert inverse[bones.functions[2]]==1
    assert inverse[bones.functions[1]]==0
    shells=json.loads((PROJECT/'research/world_shell_parameters.json').read_text())
    for name in ('finish_delay_hit_red','iaikijin_delay_hit_red'):
        fields=shells[name]['fields']
        assert fields['Projectile_Body_EPV_Index']['value']==2006
        assert fields['Obj_Hit_EPV_Index']['value']==2006
    arc=ROOT/'.cache/mhw_ls_combat/mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_simple_fx.arc'
    catalog=entries(arc.read_bytes())
    poly=catalog['effect/world/iai_line',EFL][1]
    for name in ('e11_0','e10_0','e10_rank3'):
        _,blocks=single_parts(catalog['effect/world/iai_line_'+name,EFL][1])
        unit,life=blocks[1:3]
        assert struct.unpack_from('<4I',life)==(0,70,40,0)
        curve=struct.unpack_from('<H',unit,66)[0]
        count=struct.unpack_from('<I',unit,curve)[0]&255
        keys=[struct.unpack_from('<3I',unit,curve+4+12*i) for i in range(count)]
        assert keys[-1]==(110,0,0)
        tail=[key[1]>>24 for key in keys if key[0]>=70]
        assert tail[-1]==0 and all(x>=y for x,y in zip(tail,tail[1:]))
    for name in ('tf_3d17','tf_3d1c','tf_3d16'):
        _,blocks=single_parts(catalog['effect/world/'+name,EFL][1])
        assert struct.unpack_from('<f',blocks[1],32)[0]==2
        texture=bytes(blocks[1][0x70:0xb0]).split(b'\0')[0].decode()
        tex=mtgu_tex.parse_tex(catalog[texture,0x241f5deb][1])
        pixels=mtgu_tex.deswizzle_mip(tex.mips[0][2],tex.width,tex.height,1,1,4).reshape(tex.height,tex.width,4)
        assert np.all(pixels[:,:,:3]==255) and pixels[:,:,3].min()==0
    # Billboard template is unused by these ribbon-only regression cases.
    for clip,index in [('wp03_004',9),('wp03_004',21),('wp03_060',2)]:
        _,blocks=emitter(catalog,poly,poly,clip,index)
        unit=blocks[1]
        shape=attributes(clip,index)['RIBBON']
        a=struct.unpack_from('<3f',unit,544)
        b=struct.unpack_from('<3f',unit,560)
        length=sum((y-x)**2 for x,y in zip(a,b))**.5
        expected=shape['length']*shape['scale']
        if shape['ribbonMode']==0:
            speed=attributes(clip,index)['VELOCITY3D']['speed']
            expected=abs(speed)*(shape['subdivisionCount']-1)*shape['scale']
        assert abs(length-expected)<.001,(clip,index,length,expected)
    print('PASS: source EPV selections, rigid span and moving-trail span')


if __name__=='__main__':main()
