"""Compile the two source EPV cues and the Foresight effect into private GU resources."""
import hashlib
import json
import math
import struct
import sys

import numpy as np
from PIL import Image

from animation_port import ROOT
from prepare_world_effect_textures import native_ean, mtgu_tex

SOURCE = ROOT / '.cache/mhw_ls_presentation/source'
FULL = ROOT / '.cache/mhw_ls_ground_rebuild/full_presentation'
EFL, EAN, TEX = 0x6d5ae854, 0x4e397417, 0x241f5deb
DYNAMICS=[]
SELECTION = {'wp03_005': (2, 3, 4, 5, 6), 'wp03_050': (7, 11, 12, 18, 6)}


def block_offsets(blob):
    assert blob[:4] == b'EFL\0' and struct.unpack_from('<2H', blob, 16) == (1, 1)
    return tuple(48 + (x >> 8) for x in struct.unpack_from('<4I', blob, 48))


def pair(value, jitter):
    assert 0 <= value <= 65535 and 0 <= jitter <= 65535
    return int(value) | (int(jitter) << 16)


def patch_spawn_curve(blob, attrs, *, include_scale=False):
    """Single GU generator. Per-particle scale/colour is applied in the posed update."""
    if include_scale:
        raise ValueError('Use the native particle update for source floating-point tracks')
    out = bytearray(blob)
    emitter, _, life, _ = block_offsets(out)
    tail = 48 + struct.unpack_from('<I', out, 64)[0]
    sp, lp = attrs['SPAWN'], attrs['LIFE']
    batches = sp['loopNum'] + sp['emitterRepeatCount'] - 1
    if not (sp['loopNum'] and sp['emitterRepeatCount'] and 0 < batches <= 65535):
        raise ValueError('This exporter supports finite source bursts only')
    # A5C464: active ticks per burst. A5C7DC: empty ticks BETWEEN bursts.
    gap = max(0, sp['intervalFrame'] - 1)
    struct.pack_into('<H', out, emitter+12, min(65535, max(1, sp['maxParticles'])))
    struct.pack_into('<4I', out, emitter+72, pair(sp['spawnNum'], sp['spawnNumJitter']),
                     pair(batches, sp['loopNumJitter']), 1, pair(gap, sp['intervalFrameJitter']))
    struct.pack_into('<I', out, tail+100, pair(sp['emitterDelayFrame'], sp['emitterDelayFrameJitter']))
    for index, name in enumerate(('fadeInDuration', 'duration', 'fadeOutDuration')):
        struct.pack_into('<I', out, life+4*index, pair(lp[name], lp[name+'Jitter']))
    return bytes(out)


def image_from_world(path):
    raw = path.read_bytes()
    assert raw[:4] == b'TEX\0'
    w, h, depth, fmt = struct.unpack_from('<4I', raw, 24)
    assert depth == 1 and fmt in (26, 31), (path, depth, fmt)
    offset = struct.unpack_from('<Q', raw, 0xb8)[0]
    length = ((w+3)//4)*((h+3)//4)*16
    assert offset+length <= len(raw)
    return Image.frombytes('RGB' if fmt == 26 else 'RGBA', (w,h),
                           raw[offset:offset+length], 'bcn', 5 if fmt == 26 else 7)


def asset(catalog, name, kind, data):
    key = name, kind
    if key in catalog:
        assert catalog[key][1] == data, name
    else:
        catalog[key] = (0x40000000 | len(data), data)


def world_atlas(catalog, attrs, cache, *, additive_alpha=False):
    from efx_format.uvs import UVSFile
    from types import SimpleNamespace
    uv = attrs['UVSEQUENCE']
    source = uv['path'].rstrip(chr(0)).replace(chr(92), '/')
    seq = uv['sequenceNo']
    shape=attrs.get('BILLBOARD3D') or attrs.get('RIBBON')
    refract='REFRACTION' in attrs
    fire=attrs.get('RGBFIRE')
    key = (source, seq, refract, shape.get('flowmapStrength',0), shape.get('path',shape.get('path1','')),repr(fire))
    if additive_alpha:key+=('additive-alpha',)
    if key in cache:
        return cache[key]
    uvfile = UVSFile.parse((SOURCE/(source+'.uvs')).read_bytes())
    group = uvfile.groups[seq]
    assert len(group.path_indices) == 1
    path = uvfile.strings[group.path_indices[0]].path.replace(chr(92), '/')
    im = image_from_world(SOURCE/(path+'.tex')).convert('RGBA')
    order = group._frame_indices or range(len(group.frames))
    frames = [group.frames[i] for i in order]
    name = 'effect/world/tf_' + hashlib.sha256(repr(key).encode()).hexdigest()[:12]
    w, h = im.size
    px = np.asarray(im)
    if fire:
        channels=px.astype(float)/255.
        hot=channels[:,:,1]
        smoke=channels[:,:,0]*((1-fire['lerpAlphaToBlue'])*channels[:,:,3]+fire['lerpAlphaToBlue']*channels[:,:,2])
        rgb=(hot[:,:,None]*np.asarray(fire['fireColor'][:3])*fire['fireFactor']+
             smoke[:,:,None]*np.asarray(fire['smokeColor'][:3])*fire['redChFactor'])*fire['colorRate']
        result=np.zeros_like(px)
        result[:,:,:3]=np.rint(np.clip(rgb,0,255)).astype(np.uint8)
        result[:,:,3]=np.rint(np.clip(np.maximum(hot,smoke)*fire['alphaFactor'],0,1)*255).astype(np.uint8)
        px=result
    if additive_alpha:
        # World adds this RGB light mask; GU's alpha pass needs its intensity
        # in alpha, otherwise opaque black texels become dark rectangles.
        px=px.copy()
        intensity=px[:,:,:3].max(axis=2).astype(float)/255.
        px[:,:,3]=np.rint(px[:,:,3]*intensity).astype(np.uint8)
        px[:,:,:3]=255
    if key[2]:
        # The ordinary GU destination-colour blend multiplies the scene by
        # (1 - sourceAlpha + sourceRGB). Encode a neutral border and the signed
        # source flow gradient. No scene-sampling shader is assumed here.
        bill = shape
        normal_path = bill.get('path',bill.get('path1','')).rstrip(chr(0)).replace(chr(92), '/')
        flow = image_from_world(SOURCE/(normal_path+'.tex')).resize(im.size, Image.Resampling.BILINEAR)
        normals = (np.asarray(flow, dtype=float)[:,:,:2] - 127.5) / 127.5
        mask = px[:,:,3].astype(float)/255.
        signed = (normals[:,:,0] + normals[:,:,1])*.5*bill['flowmapStrength']*mask
        weight = np.rint(72*mask)
        color = np.rint(weight + 128*signed).clip(0,255)
        px = np.stack((color,color,color,weight),axis=-1).astype(np.uint8)
    elif 'RIBBON' in attrs:
        # GU strips use horizontal UVs; World electrical filaments are
        # vertical cells. Keep every authored pattern in the converted atlas.
        if all((f.uv1[1]-f.uv0[1])*h > 1.5*(f.uv1[0]-f.uv0[0])*w for f in frames):
            px = np.ascontiguousarray(np.rot90(px))
            frames = [SimpleNamespace(uv0=(f.uv0[1],1-f.uv1[0]),
                                      uv1=(f.uv1[1],1-f.uv0[0])) for f in frames]
            w,h = h,w
    packed = mtgu_tex.swizzle_mip(np.ascontiguousarray(px),w,h,1,1,4)
    tex = mtgu_tex._pack_tex(w,h,1,7,[0],packed,8,0,2,1,1)
    assert np.array_equal(mtgu_tex.deswizzle_mip(mtgu_tex.parse_tex(tex).mips[0][2],w,h,1,1,4).reshape(h,w,4),px)
    asset(catalog,name,TEX,tex)
    asset(catalog,name,EAN,native_ean(frames,w,h))
    cache[key] = (name,w,h)
    return cache[key]


def source_selection():
    from epv_format.epv import EPVFile
    epv = EPVFile.parse((SOURCE/'wp/swo/epv/hm_wp03.epv3').read_bytes())
    group = next(g for g in epv.groups if g.groupID == 2005)
    masks = [next(r for r in group.records if r.recordID == n).parameterBlock1.EFXSubIndex[0] for n in (2,0)]
    assert masks == [4,1]
    full = json.loads((FULL/'wp03_050.json').read_text())['full_efx']
    lists = {row['tableType']:row['entries'] for row in full['subselect']}
    assert lists[4] == [0] and lists[1] == [11,12,18,6]
    action = full['actions'][0]['entries'][0]
    assert action['type'] == 'PLAYEMITTER' and action['fields']['targets'] == [7]
    assert SELECTION['wp03_050'] == (7,*lists[1])


def build_layers(catalog, flash):
    sys.path.insert(0,str(ROOT/'.cache/mhw_efx_editor'))
    source_selection()
    rows, cache = [], {}
    # Both layouts/tail records are known-good generated resources from the base bank.
    poly_template = catalog['effect/world/iai_line',EFL][1]
    for clip, indices in SELECTION.items():
        full = json.loads((FULL/(clip+'.json')).read_text())['full_efx']['entries']
        decoded = json.loads((ROOT/'.cache/mhw_ls_presentation/decoded'/(clip+'.json')).read_text())
        for index in indices:
            attrs = {a['type']:a['fields'] for a in decoded[index]['attributes']}
            if not attrs['SPAWN'].get('emitterRepeatCount'):
                raise ValueError((clip,index,'infinite emitter'))
            strip = 'RIBBON' in attrs
            item = attrs['RIBBON' if strip else 'BILLBOARD3D']
            uid = (0x3d00 if clip == 'wp03_005' else 0x3d10)+index
            name = f'effect/world/tf_{uid:x}'
            out = bytearray(poly_template if strip else flash)
            emitter,unit,_,_ = block_offsets(out)
            # The electrical atlas's RGB darkens GU's alpha pass. Use the
            # authored light mask for these two blade-following glows.
            blade_glow=clip=='wp03_050' and index in (7,12)
            atlas_attrs=attrs
            if blade_glow:
                atlas_attrs={a['type']:a['fields'] for a in decoded[6]['attributes']}
            atlas,w,h = world_atlas(catalog,atlas_attrs,cache,
                additive_alpha=blade_glow or (clip=='wp03_050' and index==6))
            for at in (0x70,0x130):
                out[unit+at:unit+at+64] = atlas.encode().ljust(64,b'\0')
            tint = int.from_bytes(bytes(item['color']),'little')
            energy = 2 if blade_glow or (clip=='wp03_050' and index==6) else .10*item['brightness'] if strip else 1
            struct.pack_into('<2f',out,unit+32,energy,0)
            struct.pack_into('<2I',out,unit+72,tint,tint)
            struct.pack_into('<2I',out,unit+96,w//2,h//2)
            if strip:
                scale = item['scale']
                length = item['length']*scale
                struct.pack_into('<2I',out,unit+0x178,tint,tint)
                struct.pack_into('<2f',out,unit+0x180,item['width']*scale/2,item['width_jitter']*scale/2)
                struct.pack_into('<3f',out,unit+544,-length/2,0,0)
                struct.pack_into('<3f',out,unit+560, length/2,0,0)
                spread = attrs.get('EMITTERSHAPE3D',{}).get('rangeXYZ')
                if spread and attrs['SPAWN']['maxParticles'] > 1:
                    # Native box emission preserves the source footprint;
                    # GU does not reproduce World's ring subdivision sampler.
                    extent = [max(abs(v),abs(j)) for v,j in zip(spread[::2],spread[1::2])]
                    if clip=='wp03_050' and index==11:
                        extent[1],extent[2]=extent[2],extent[1]
                    struct.pack_into('<6f',out,emitter+96,extent[0],0,extent[1],0,extent[2],0)
                    out[emitter+120]=1
            else:
                # Mode 13 is BSBlendBlendAddDestColor, independently verified in the GU shader table.
                out[unit+3] = 13
                struct.pack_into('<2f',out,unit+40,item['scale']*item['width']/w,0)
                struct.pack_into('<I',out,unit+100,round(h/2*item['height']/item['width']))
            data = patch_spawn_curve(out,attrs)
            asset(catalog,name,EFL,data)
            rows.append((uid,800,name))
            if strip:DYNAMICS.append((name,0,attrs))
            assert full[index]['kind']=='standard'
    assert len({r[0] for r in rows})==10
    return rows
