"""Compile the selected wp03_004/060 emitters into native GU particle groups."""
import base64
import json
import math
import struct
from functools import lru_cache
from pathlib import Path

from animation_port import PROJECT, ROOT, sha

EFL = 0x6d5ae854
TEX = 0x241f5deb
EAN = 0x4e397417
PREFIX = 'effect/world/iai_line_'
DYNAMICS=[]


@lru_cache(None)
def source(clip):
    path = ROOT / '.cache/mhw_ls_ground_rebuild/full_presentation' / (clip + '.json')
    return json.loads(path.read_text(encoding='utf8'))


def attributes(clip, index):
    entry = source(clip)['full_efx']['entries'][index]
    return {row['type']: row['fields'] for row in entry['attributes'] if 'fields' in row}


def children(clip, parent):
    attrs = attributes(clip, parent)
    action = source(clip)['play'][attrs['PTLIFE']['relationIndex']]
    raw = base64.b64decode(action['entries'][0]['raw']['bytes_base64'], validate=True)
    n, = struct.unpack_from('<I', raw, 52)
    if len(raw) != 56 + 4*n:
        raise ValueError(f'{clip}[{parent}] action length mismatch')
    return struct.unpack_from('<' + 'I'*n, raw, 56)


def single_parts(blob):
    if blob[:4] != b'EFL\0' or struct.unpack_from('<HH', blob, 16) != (1, 1):
        raise ValueError('Expected a single native emitter')
    words = struct.unpack_from('<4I', blob, 48)
    offsets = [48 + (v >> 8) for v in words]
    offsets += [48 + struct.unpack_from('<I', blob, 64)[0], len(blob)]
    if offsets != sorted(offsets) or offsets[0] < 68:
        raise ValueError('Unexpected emitter block order')
    return [v & 255 for v in words], [bytearray(blob[a:b]) for a,b in zip(offsets, offsets[1:])]


def group_efl(template, parts):
    """Each generator owns a separate transform/delay record, including in a shared request."""
    count = len(parts)
    first = (48 + count*20 + 15) & ~15
    out = bytearray(template[:48]) + bytearray(first-48)
    struct.pack_into('<HH', out, 16, count, count)
    for i, (tags, blocks) in enumerate(parts):
        words = []
        for kind, block in zip([i, *tags[1:]], blocks[:4]):
            words.append((len(out)-48) << 8 | kind)
            out.extend(block)
            out.extend(bytes(-len(out) % 16))
        struct.pack_into('<4I', out, 48+16*i, *words)
        struct.pack_into('<I', out, 48+16*count+4*i, len(out)-48)
        out.extend(blocks[4])
        out.extend(bytes(-len(out) % 16))
    struct.pack_into('<I', out, 8, len(out)-48)
    return bytes(out)


@lru_cache(None)
def atlas_records(clip):
    doc = json.loads((PROJECT/'research'/f'{clip}_texture_conversion.json').read_text(encoding='utf8'))
    resources = {r['path']:r for r in doc['resources']}
    return {row['emitter']:(resources[resources[row['ean']]['texture']], resources[row['ean']])
            for row in doc['emitters']}


def bind_texture(catalog, unit, clip, idx):
    tex, uv = atlas_records(clip)[idx]
    for offset, record in [(0x70,tex),(0x130,uv)]:
        name = record['path']
        key = name,record['type']
        if key not in catalog:
            path = Path(record['output'])
            if sha(path) != record['sha256']:
                raise ValueError(f'Wrong source texture/atlas: {path}')
            blob = path.read_bytes()
            catalog[key] = 0x40000000|len(blob),blob
        unit[offset:offset+64] = name.encode().ljust(64, b'\0')
    struct.pack_into('<2I',unit,96,tex['width']//2,tex['height']//2)
    return tex,uv


def color_curve(unit, keys):
    """Native GU RGB curves use frame, low RGBA and high RGBA for each key."""
    if len(unit)%4 or struct.unpack_from('<I', unit, 64)[0] >> 16:
        raise ValueError('Unexpected curve in polyline template')
    struct.pack_into('<H', unit, 66, len(unit))
    struct.pack_into('<I', unit, 80, struct.unpack_from('<I',unit,80)[0] | 0xc00)
    unit.extend(struct.pack('<I',0x200|len(keys)))
    for frame, rgba in keys:
        value = int.from_bytes(bytes(rgba),'little')
        unit.extend(struct.pack('<3I',frame,value,value))


def setup_core(catalog, flash, rank):
    from build_world_simple_fx import iai_line
    index,uid,near,far,energy,width = [(11,0x3f6b,490,-1580,14,12),
                                        (10,0x3f70,612,-1975,35,15),
                                        (10,0x3f71,800,-2480,34,16)][rank-1]
    path=PREFIX + ('e11_0','e10_0','e10_rank3')[rank-1]
    a=attributes('wp03_004',index)
    entry=source('wp03_004')['full_efx']['entries'][index]
    animation=next(v for v in entry['timl']['animations'] if v)
    tracks={tr['datatype']:tr['keyframes'] for typ in animation['types'] for tr in typ['transforms']}
    rate=tracks[0x9f1e012e]
    tint=tracks[0x58689812]
    rate_points=[(int(k['frame']),k['subs'][0]['value']) for k in rate]
    colors=[(int(k['frame']),[s['value'] for s in k['subs']]) for k in tint]
    assert rate_points==[(0,50),(30,5)] and colors[0][0]==0 and colors[-1][0]==100
    # Keep the 110-frame lifespan but reserve its tail for a smooth fade.
    phases=(0,70,40)
    iai_line(catalog,flash,index,path,(near,far,*phases),energy=energy,width=width)
    blob=catalog[path,EFL][1]
    tags,blocks=single_parts(blob);unit=blocks[1]
    keys=[]
    # The GU material has one additive tint curve; combine World ColorRate and alpha there.
    for time in sorted({t for t,_ in rate_points+colors}|{70,80,90,100,110}):
        u=min(1.,time/rate_points[-1][0]);v=min(1.,time/colors[-1][0])
        light=(rate_points[0][1]*(1-u)+rate_points[-1][1]*u)/rate_points[0][1]
        rgba=[round((x*(1-v)+y*v)*(light if c<3 else 1))
              for c,(x,y) in enumerate(zip(colors[0][1],colors[-1][1]))]
        tail=max(0.,min(1.,(time-70)/40))
        fade=1-tail*tail*(3-2*tail)
        rgba=[round(c*fade) for c in rgba]
        keys.append((time,rgba))
    color_curve(unit,keys)
    data=group_efl(blob,[(tags,blocks)]);catalog[path,EFL]=0x40000000|len(data),data
    return uid,800,path


def emitter(catalog, flash, poly, clip, idx):
    from world_thrust_foresight_fx import patch_spawn_curve
    a=attributes(clip,idx)
    ribbon=a.get('RIBBON')
    shape=ribbon or a['BILLBOARD3D']
    base=poly if ribbon else flash
    tags,blocks=single_parts(base)
    gen,unit,life,position,tail=blocks
    tex,uv=bind_texture(catalog,unit,clip,idx)
    if 'REFRACTION' in a or (ribbon and 'RGBFIRE' in a):
        from world_thrust_foresight_fx import world_atlas
        decoded=json.loads((ROOT/'.cache/mhw_ls_presentation/decoded'/f'{clip}.json').read_text())
        material={r['type']:r['fields'] for r in decoded[idx]['attributes']}
        name,w,h=world_atlas(catalog,material,{})
        for offset in (0x70,0x130):unit[offset:offset+64]=name.encode().ljust(64,b'\0')
        struct.pack_into('<2I',unit,96,w//2,h//2)
        if 'REFRACTION' in a:unit[3]=13
    rgba=shape['color'];color=int.from_bytes(bytes(rgba),'little')
    high=shape['colorRange'] if shape['useColorRange'] else rgba
    struct.pack_into('<2I',unit,72,color,int.from_bytes(bytes(high),'little'))
    # HDR is compressed by the GU additive pass. Keep the native peak in range
    # even when several delayed shells land in neighbouring display frames.
    def exposure(value):
        return min(math.sqrt(max(0.,value)),max(0.,value)*.1)
    energy = exposure(shape['brightness'])
    jitter = exposure(shape['brightness'] + shape.get('brightnessJitter',0.))-energy
    struct.pack_into('<2f',unit,32,energy,jitter)
    pos=a['TRANSFORM3D']['translate'][::2]
    if ribbon:
        struct.pack_into('<2I',unit,0x178,color,int.from_bytes(bytes(high),'little'))
        struct.pack_into('<2f',unit,0x180,shape['width']*shape['scale']*.5,
                         shape['width_jitter']*shape['scale']*.5)
        axis=shape['baseAxis']%3
        extent=shape['length']*shape['scale']*(-1 if shape['baseAxis']>=3 else 1)
        if shape['ribbonMode']==0:
            # A source trail spans recent particle positions. Its length field
            # does not describe a stationary 200-unit vertical strip.
            extent=a['VELOCITY3D']['speed']*(shape['subdivisionCount']-1)*shape['scale']
        anchor=shape['spawnAnchorOffset'] if shape['ribbonMode'] else 0
        for endpoint,fraction in [(544,-anchor),(560,1-anchor)]:
            struct.pack_into('<3f',unit,endpoint,*pos)
            struct.pack_into('<f',unit,endpoint+axis*4,pos[axis]+fraction*extent)
    else:
        # GU billboard applies uniform size to an EAN frame. Bake the source
        # aspect in the image, preserving its alpha, frame order and UV origin.
        bind_aspect(catalog,unit,tex,uv,shape)
    region=a.get('EMITTERSHAPE3D')
    if region and a['SPAWN']['maxParticles']>1:
        # GU A5E450: box 1 samples symmetric extents, cylinder 5 and
        # ellipsoid 7 accept inner radius + thickness in the source order.
        mode={0:1,1:7,2:5}[region['shapeType']]
        gen[120]=mode
        ranges=region['rangeXYZ']
        if mode==1:ranges=[q for inner,size in zip(ranges[::2],ranges[1::2]) for q in (abs(inner)+abs(size),0)]
        struct.pack_into('<6f',gen,96,*ranges)
        struct.pack_into('<i',gen,16,-1)
    b=group_efl(base,[(tags,blocks)])
    return single_parts(patch_spawn_curve(b,a))


def bind_aspect(catalog,unit,tex,uv,shape):
    from PIL import Image
    import numpy as np
    from types import SimpleNamespace
    from prepare_world_effect_textures import native_ean
    import mtgu_tex
    ean=catalog[uv['path'],EAN][1]
    cells=struct.unpack_from('<I',ean,20)[0]
    ratio=shape['height']/shape['width']
    cell_w=128;cell_h=128
    cols=math.ceil(math.sqrt(cells));rows=math.ceil(cells/cols)
    width=1<<((cols*cell_w-1).bit_length());height=1<<((rows*cell_h-1).bit_length())
    resource='effect/world/bb_'+uv['path'].rsplit('/',1)[-1]+'_'+str(round(ratio*10000))
    if (resource,TEX) not in catalog:
        with Image.open(Path(tex['output']).with_suffix('.png')) as source_image:
            sheet=Image.new('RGBA',(width,height))
            frames=[]
            for i in range(cells):
                x,y,w,h=struct.unpack_from('<4H',ean,48+24*i)
                stamp=source_image.crop((x,y,x+w,y+h))
                sw,sh=(cell_w, max(1,round(cell_w*ratio))) if ratio<=1 else (max(1,round(cell_h/ratio)),cell_h)
                cx=(i%cols)*cell_w;cy=(i//cols)*cell_h
                sheet.paste(stamp.resize((sw,sh),Image.Resampling.LANCZOS),(cx+(cell_w-sw)//2,cy+(cell_h-sh)//2))
                frames.append(SimpleNamespace(uv0=(cx/width,cy/height),uv1=((cx+cell_w)/width,(cy+cell_h)/height)))
        rgba=np.array(sheet);pixels=mtgu_tex.swizzle_mip(rgba,width,height,1,1,4)
        data=mtgu_tex._pack_tex(width,height,1,7,[0],pixels,8,0,2,1,1)
        atlas=native_ean(frames,width,height)
        catalog[resource,TEX]=0x40000000|len(data),data
        catalog[resource,EAN]=0x40000000|len(atlas),atlas
    for off in (0x70,0x130):unit[off:off+64]=resource.encode().ljust(64,b'\0')
    struct.pack_into('<2I',unit,96,width//2,height//2)
    struct.pack_into('<2f',unit,40,max(shape['height'],shape['width'])*shape['scale']/cell_w,0)


def add_helm_iai(catalog,flash):
    """Return PEL rows for collision, draw, counter and rank-selected requests."""
    poly=catalog['effect/world/iai_line',EFL][1]
    rows=[setup_core(catalog,flash,rank) for rank in (1,2,3)]
    helm=children('wp03_060',0);assert helm==(1,2,3,4,5,6)
    groups={s['table_type']:s['entries'] for s in source('wp03_004')['subselect']}
    neutral=children('wp03_004',groups[1][0]);white=children('wp03_004',groups[2][0])
    colored=children('wp03_004',groups[4][0]);assert colored==children('wp03_004',groups[8][0])
    assert neutral==(20,25,26,27) and 11 in white and 10 in colored
    effects=[('helm_impact','wp03_060',helm),('iai_draw','wp03_004',neutral[:1]),
             ('iai_counter','wp03_004',neutral[1:]),('iai_white','wp03_004',tuple(i for i in white if i!=11)),
             ('iai_color','wp03_004',tuple(i for i in colored if i!=10)),
             ('iai_lens','wp03_004',(19,)),('iai_weapon','wp03_004',children('wp03_004',13))]
    for n,(label,clip,indices) in enumerate(effects):
        path=PREFIX+label
        parts=[emitter(catalog,flash,poly,clip,i) for i in indices]
        DYNAMICS.extend((path,j,attributes(clip,i)) for j,i in enumerate(indices) if 'RIBBON' in attributes(clip,i))
        blob=group_efl(flash,parts)
        catalog[path,EFL]=0x40000000|len(blob),blob
        rows.append((0x3fc0+n,800,path))
    return rows
