"""Build the private GU palette with the four moves compiled from World EFX."""
import json,struct,sys
from animation_port import ROOT,PROJECT,sha
sys.path.insert(0,str(ROOT/'05_reference/fx_test23/source_reference'))
from build_effect_assets import entries,pel_groups,pack
from effect_resource_graph import dependency_closure

PEL='effect/pel/pl/world_simple'
FLASH='effect/world/simple_flash'
LINE='effect/world/iai_line'

def counter_streak_texture(catalog,tex,ean,path="effect/world/iai_counter_red"):
    """Map one vertical World electrical filament to GU's horizontal strip UVs."""
    import numpy as np
    from types import SimpleNamespace
    from prepare_world_effect_textures import native_ean
    atlas=catalog[ean['path'],ean['type']][1]
    xy,size=struct.unpack_from('<2I',atlas,48)
    x,y=xy&65535,xy>>16
    cell_w,cell_h=size&65535,size>>16
    # The 90-degree rotation swaps the dimensions.
    if (path,tex['type']) in catalog:return path,cell_h,cell_w
    sys.path.insert(0,str(ROOT/'05_reference/经验包/MHGU_TEX_SKILL/code'))
    import mtgu_tex
    w,h=tex['width'],tex['height']
    info=mtgu_tex.parse_tex(catalog[tex['path'],tex['type']][1])
    original=mtgu_tex.deswizzle_mip(info.mips[0][2],w,h,1,1,4).reshape(h,w,4)
    cell=np.rot90(original[y:y+cell_h,x:x+cell_w])
    h,w=cell.shape[:2]
    core=np.sqrt(cell[:,:,3]/255.)
    glow=(cell[:,:,1]/255.)**2
    taper=np.minimum(1,np.minimum(np.arange(w),np.arange(w)[::-1])/max(1,w*.07))
    pixels=np.zeros_like(cell,order='C')
    # GU also samples RGB outside the alpha core. Keep the coloured halo
    # in the texture channels so transparent margins cannot become a red bar.
    pixels[:,:,0]=np.rint(255*np.maximum(np.sqrt(core),glow**.65)*taper).astype(np.uint8)
    pixels[:,:,1]=np.rint(228*core).astype(np.uint8)
    pixels[:,:,2]=pixels[:,:,1]
    pixels[:,:,3]=np.rint(255*np.maximum(core,glow)*taper).astype(np.uint8)
    if path in ('effect/world/helm_core','effect/world/helm_tail','effect/world/thrust_core'):
        pixels[:,:,1]=np.rint((185 if path.endswith('/helm_core') else 23)*core**3).astype(np.uint8)
        pixels[:,:,2]=np.rint((181 if path.endswith('/helm_core') else 29)*core**3).astype(np.uint8)
    if path in ('effect/world/helm_core','effect/world/helm_tail'):
        # Preserve the source filament's longitudinal intensity variation
        # through GU's additive pass; taper the bright centre as well as alpha.
        edge=np.sin(np.linspace(0,np.pi,w)).clip(0,1)**.72
        pixels[:]=np.rint(pixels*edge[None,:,None]).astype(np.uint8)
    if path.endswith('/helm_tail'):
        # Leave separated sparks in the residual stroke after the main flash.
        pixels[:]=np.rint(pixels*core[:,:,None]**2).astype(np.uint8)
    elif path.endswith('/thrust_core'):
        # Bias the hot filament along the posed strip; keep the blade visible.
        along=np.linspace(.30,1,w)
        pixels[:]=np.rint(pixels*along[None,:,None]).astype(np.uint8)
    elif path.endswith('/iai_embers'):
        # A short native segment per fleck avoids tiling a row of dots down the ribbon.
        x=np.linspace(-1,1,w);y=np.linspace(-1,1,h)[:,None]
        dots=np.maximum(0,1-x*x)**2*np.exp(-((y-.18*x)/.38)**2)
        pixels[:]=np.rint(dots[:,:,None]*[255,128,111,255]).astype(np.uint8)
    elif path.endswith('/iai_rank3'):
        # Source side capture: a warm white core runs through the pink fringe.
        hot=np.maximum(core**.65,glow**.65)*taper
        inner=core**.62*taper
        pixels[:,:,1]=np.rint(230*inner+20*hot).astype(np.uint8)
        pixels[:,:,2]=np.rint(220*inner+15*hot).astype(np.uint8)
    elif path.endswith('/iai_counter_red'):
        # The white core narrows into red at both ends in the training footage.
        pixels[:,:,1:3]=np.rint(pixels[:,:,1:3]*((core*taper)**2)[:,:,None]).astype(np.uint8)
    swizzled=mtgu_tex.swizzle_mip(pixels,w,h,1,1,4)
    data=mtgu_tex._pack_tex(w,h,1,7,[0],swizzled,8,0,2,1,1)
    check=mtgu_tex.parse_tex(data)
    assert np.array_equal(mtgu_tex.deswizzle_mip(check.mips[0][2],w,h,1,1,4).reshape(h,w,4),pixels)
    catalog[path,tex['type']]=(0x40000000|len(data),data)
    uv=native_ean([SimpleNamespace(uv0=(0,0),uv1=(1,1))],w,h)
    catalog[path,ean['type']]=(0x40000000|len(uv),uv)
    return path,w,h

def source_flash(catalog,template,clip,index,uid):
    """Single camera-facing glow; excludes smoke, sparks and GPU particles."""
    from pathlib import Path
    raw=Path(ROOT/'.cache/mhw_ls_presentation/decoded'/f'{clip}.json').read_bytes()
    attrs={a['type']:a['fields'] for a in json.loads(raw)[index]['attributes']}
    sprite=attrs['BILLBOARD3D'];life=attrs['LIFE']
    report=json.loads((PROJECT/'research'/f'{clip}_texture_conversion.json').read_text())
    ean=next(r for r in report['resources'] if r['path']==next(e['ean']for e in report['emitters']if e['emitter']==index))
    tex=next(r for r in report['resources'] if r['path']==ean['texture'])
    for resource in (tex,ean):
        path=Path(resource['output']);assert sha(path)==resource['sha256']
        blob=path.read_bytes()
        if resource is tex:assert blob[:4]==b'TEX\0'
        catalog[resource['path'],resource['type']]=(0x40000000|len(blob),blob)
    b=bytearray(template);emitter,unit,at,pos=[48+(v>>8)for v in struct.unpack_from('<4I',b,48)]
    struct.pack_into('<4I',b,at,life['fadeInDuration'],life['duration'],life['fadeOutDuration'],0)
    # Native sprite extents are texture-pixel half dimensions. Keep them
    # consistent with the atlas; apply world size through the native scale.
    # GU's non-HDR additive pass clips source HDR20 into an opaque orb.
    brightness_compensation=.1
    struct.pack_into('<6f',b,unit+32,sprite['brightness']*brightness_compensation,0,sprite['width']/tex['width']*sprite['scale'],0,0,0)
    color=int.from_bytes(bytes(sprite['color']),'little')
    struct.pack_into('<2I',b,unit+72,color,color)
    struct.pack_into('<2I',b,unit+96,tex['width']//2,tex['height']//2)
    for offset,path in ((0x70,tex['path']),(0x130,ean['path'])):b[unit+offset:unit+offset+64]=path.encode().ljust(64,b'\0')
    if clip=='wp03_004' and index in (22,30):
        # World samples a coloured lens atlas through a warm-white 50x8
        # billboard. In GU an unmodified square atlas leaves a rainbow orb.
        # Bake the source aspect and luminance into its private one-cell atlas.
        from PIL import Image
        import numpy as np
        from types import SimpleNamespace
        from prepare_world_effect_textures import native_ean
        sys.path.insert(0,str(ROOT/'05_reference/经验包/MHGU_TEX_SKILL/code'))
        import mtgu_tex
        xy,wh=struct.unpack_from('<2I',catalog[ean['path'],ean['type']][1],48)
        x,y=xy&65535,xy>>16; w,h=wh&65535,wh>>16
        source=Image.open(Path(tex['output']).with_suffix('.png')).convert('RGBA').crop((x,y,x+w,y+h))
        # Source aspect is a *rendered* aspect, distinct from atlas cell size.
        height=max(1,round(w*sprite['height']/sprite['width']))
        gray=np.asarray(source.convert('L').resize((w,height),Image.Resampling.LANCZOS))
        alpha=np.asarray(source.getchannel('A').resize((w,height),Image.Resampling.LANCZOS))
        mask=np.sqrt(gray.astype(float)/255)*alpha
        cell=np.zeros((h,w,4),np.uint8);top=(h-height)//2
        cell[top:top+height,:,:3]=gray[:,:,None]
        cell[top:top+height,:,3]=np.rint(mask).astype(np.uint8)
        resource='effect/world/iai_anchor_warm'
        raw=mtgu_tex._pack_tex(w,h,1,7,[0],mtgu_tex.swizzle_mip(cell,w,h,1,1,4),8,0,2,1,1)
        uv=native_ean([SimpleNamespace(uv0=(0,0),uv1=(1,1))],w,h)
        for typ,blob in ((tex['type'],raw),(ean['type'],uv)):catalog[resource,typ]=(0x40000000|len(blob),blob)
        for off in (0x70,0x130):b[unit+off:unit+off+64]=resource.encode().ljust(64,b'\0')
        struct.pack_into('<2I',b,unit+96,w//2,h//2)
        struct.pack_into('<6f',b,unit+32,1.25,0,sprite['width']/w*sprite['scale'],0,0,0)
        struct.pack_into('<4I',b,at,0,0,22,0)
    name=f'effect/world/flash_{uid:x}'
    catalog[name,0x6d5ae854]=(0x40000000|len(b),bytes(b))
    return name,{'uid':uid,'clip':clip,'emitter':index,'decoded_sha256':__import__('hashlib').sha256(raw).hexdigest(),
        'billboard':sprite,'life':life,'texture':tex['source'],'atlas':ean['path'],
        'native_brightness_compensation':brightness_compensation,
        'adaptation':'GU one-shot billboard, source atlas/colour/lifetime and width. Source HDR brightness compensated0.1; native uniform scale and shader, not full World anisotropic/HDR curves.'}

def iai_line(catalog,flash,index,path,stroke=None, *, energy=None,width=None,clip="wp03_004",axis=0,embers=False,height=0):
    """Convert one authored wp03_004 ribbon, preserving its atlas and endpoints."""
    from pathlib import Path
    source=json.loads((ROOT/'.cache/mhw_ls_presentation/decoded'/f'{clip}.json').read_text())
    attrs={a['type']:a['fields']for a in source[index]['attributes']}
    ribbon=attrs['RIBBON'];life=attrs['LIFE']
    textures=json.loads((PROJECT/'research'/('wp03_060_texture_conversion.json' if clip in ('wp03_060','wp03_005') else 'wp03_004_texture_conversion.json')).read_text())
    uv=attrs['UVSEQUENCE']
    def atlas_key(v):return v['path'].rstrip(chr(0)),v['sequenceNo']
    key=atlas_key(uv)
    ean=next(r for r in textures['resources'] if r['path']==next(e['ean'] for e in textures['emitters'] if atlas_key(e['source_uv_fields'])==key))
    tex=next(r for r in textures['resources']if r['path']==ean['texture'])
    for r in (tex,ean):
        p=Path(r['output']);assert sha(p)==r['sha256'];data=p.read_bytes()
        catalog[r['path'],r['type']]=(0x40000000|len(data),data)
    core=(clip!='wp03_004' or index in (10,11)) and stroke is not None
    rgba=[255,188,188,255] if core else (ribbon['color'] if stroke else [255,255,255,ribbon['color'][3]])
    if clip=='wp03_004' and core:rgba=[255,248,248,255]
    if clip!='wp03_004':rgba=[255,120,125,255] if clip=='wp03_060' else [255,47,54,255]
    if clip=='wp03_005':rgba=ribbon['color']
    color=int.from_bytes(bytes(rgba),'little')
    proof={'source':clip,'emitter':index,'resource':path,'texture':tex['source'],
           'source_texture_sha256':tex['source_sha256'],'source_life':life,'source_ribbon':ribbon}
    texture,w,h=counter_streak_texture(catalog,tex,ean,{'wp03_060':('effect/world/helm_tail' if index==1 else 'effect/world/helm_core'),'wp03_050':'effect/world/thrust_core'}.get(clip,'effect/world/iai_embers' if embers else 'effect/world/iai_rank3' if clip=='wp03_004' else 'effect/world/iai_counter_red')) if core else (tex['path'],tex['width'],tex['height'])
    atlas=texture if core else ean['path']
    template=catalog['effect/cm/cm120_070',0x6d5ae854][1]
    native=48+(struct.unpack_from('<I',template,48+2*16+4)[0]>>8)
    unit=bytearray(template[native:native+512])+bytearray(64)
    struct.pack_into('<2f',unit,32,energy if energy is not None else ribbon['brightness'],0)
    struct.pack_into('<2f',unit,40,1,0)
    struct.pack_into('<2I',unit,72,color,color)
    struct.pack_into('<2I',unit,96,w//2,h//2)
    for off,resource in ((0x70,texture),(0x130,atlas)):unit[off:off+64]=resource.encode().ljust(64,b'\0')
    # Native A6E2BC mode1: scale at +432, rotation at +480 and the
    # two local vertices at +544/+560 (A67FDC multiplies that vertex array).
    # Mode4 is an attached trail and cannot stand in for a stationary slash.
    unit[0x170]=1
    struct.pack_into('<2I',unit,0x178,color,color)
    struct.pack_into('<2f',unit,0x180,width if width is not None else ribbon['width']/2,0)
    unit[432:]=bytes(len(unit)-432)
    struct.pack_into('<6f',unit,432,1,0,1,0,1,0)
    start,end=stroke[:2] if stroke else (-ribbon['length'],ribbon['length'])
    struct.pack_into('<f',unit,544+4*axis,start)
    struct.pack_into('<f',unit,560+4*axis,end)
    if height:
        for offset in (548,564):struct.pack_into('<f',unit,offset,height)
    struct.pack_into('<I',unit,528,0x644)
    struct.pack_into('<f',unit,532,1)
    head=bytearray(flash[:80]);emitter=bytearray(flash[80:272])
    phases=stroke[2:] if stroke else (life['fadeInDuration'],life['duration'],life['fadeOutDuration'])
    position=flash[752:];lifetime=struct.pack('<4I',*phases,0)
    data=head+emitter+unit+lifetime+position
    struct.pack_into('<I',data,64,struct.unpack_from('<I',head,64)[0]+112)
    for i,(off,kind)in enumerate(((80,0),(272,1),(848,18),(864,0))):struct.pack_into('<I',data,48+i*4,((off-48)<<8)|kind)
    struct.pack_into('<I',data,8,len(data)-48)
    catalog[path,0x6d5ae854]=(0x40000000|len(data),bytes(data))
    return dict(proof,world_space_endpoints=[start,end],gu_life=phases,gu_color=rgba,gu_brightness=energy,gu_half_width=width,
                adaptation='GU native world-space polyline. Red sweep and fade fitted to live training captures.' if stroke else 'White draw stroke with authored atlas and life.')

def main():
    catalog={};base=ROOT/'04_assets/MHGU_romfs/romfs/nativeNX/arc/shell/pl'
    for name in ('com','w07'):catalog.update(entries((base/(name+'.arc')).read_bytes()))
    flags,original=catalog['effect/cm/cm139_000',0x6d5ae854];b=bytearray(original)
    assert len(b)==1056
    emitter,unit,life,position=[48+(v>>8)for v in struct.unpack_from('<4I',b,48)]
    struct.pack_into('<I',b,60,(position-48)<<8)
    struct.pack_into('<H',b,emitter+12,1)
    struct.pack_into('<2f4I2f',b,emitter+64,1,0,1,1,1,0,0,0)
    struct.pack_into('<6f',b,emitter+96,*([0]*6))
    struct.pack_into('<6f',b,emitter+136,1,0,1,0,1,0)
    struct.pack_into('<4I',b,life,0,0,12,0)
    struct.pack_into('<6f',b,unit+32,2,0,.25,0,0,0)
    struct.pack_into('<I',b,unit+56,0);struct.pack_into('<I',b,unit+64,0)
    struct.pack_into('<2I',b,unit+72,0xffffdcb4,0xffffdcb4)
    struct.pack_into('<I',b,unit+80,0)
    atlas=json.loads((PROJECT/'research/wp03_002_texture_conversion.json').read_text())
    name=next(r['ean']for r in atlas['emitters']if r['emitter']==4)
    ean=next(r for r in atlas['resources']if r['path']==name)
    tex=next(r for r in atlas['resources']if r['path']==ean['texture'])
    from pathlib import Path
    for row,offset in [(tex,0x70),(ean,0x130)]:
        resource=Path(row['output']);assert sha(resource)==row['sha256']
        data=resource.read_bytes();catalog[row['path'],row['type']]=(0x40000000|len(data),data)
        b[unit+offset:unit+offset+64]=row['path'].encode().ljust(64,b'\0')
    struct.pack_into('<2I',b,unit+96,tex['width']//2,tex['height']//2)
    struct.pack_into('<10f',b,unit+0x170,0,0,0,0,1,0,0,0,1,0)
    struct.pack_into('<I',b,unit+0x198,0)
    catalog[FLASH,0x6d5ae854]=(flags&0xe0000000|len(b),bytes(b))
    line=iai_line(catalog,b,31,LINE)
    from world_thrust_foresight_fx import build_layers
    from world_helm_iai_fx import add_helm_iai
    counter_rows = list(build_layers(catalog, b))
    counter_rows.extend(add_helm_iai(catalog, b))
    from world_particle_dynamics import write_dynamics
    write_dynamics()
    path=LINE+'_blade_white'
    template=bytearray(catalog[LINE,0x6d5ae854][1])
    struct.pack_into('<4I',template,848,0,4,3,0)
    struct.pack_into('<2f',template,272+0x180,2.3,0)
    catalog[path,0x6d5ae854]=(0x40000000|len(template),bytes(template))
    counter_rows.append((0x3f85,800,path))
    flash_path, sheath_flash = source_flash(catalog, b, 'wp03_002', 2, 0x3f60)
    flash_rows = [(0x3f60, 800, flash_path)]
    pflags,pel=catalog['effect/pel/pl/w07_800',0x5a525c16];rows=[]
    for uid,native,path in [*flash_rows,(0x3f61,800,'effect/cm/cm121_070'),
                            (0x3f62,801,'effect/cm/cm121_070'),(0x3f63,802,'effect/cm/cm121_070'),(0x3f64,800,LINE),
                            *counter_rows]:
        source=next(r for r in pel_groups(pel)[2]if r['uid']==native)
        payload=bytearray(source['raw'][source['payload']:]);struct.pack_into('<H',payload,48,uid)
        struct.pack_into('<3f',payload,0,0,0,0)
        # The art's native slash covers a much larger area than an ordinary
        # sword swing. Keep it close to blade length in the simplified style.
        if uid in (0x3f61,0x3f62,0x3f63):struct.pack_into('<3f',payload,32,.18,.18,.18)
        if path==LINE or path.startswith(LINE+'_') or 0x3d00<=uid<=0x3dff:
            struct.pack_into('<3f',payload,16,0,0,0)
            struct.pack_into('<3f',payload,32,1,1,1)
        rows.append(bytes([len(path)])+path.encode()+b'\x01\0'+payload)
    ids = [struct.unpack_from('<H', row, 1+row[0]+2+48)[0] for row in rows]
    assert len(ids) == len(set(ids)), 'Duplicate private effect ID'
    raw=pel[:8]+struct.pack('<3I',0,0,len(rows))+b''.join(rows)
    catalog[PEL,0x5a525c16]=(pflags&0xe0000000|len(raw),raw)
    selected,edges,external=dependency_closure(catalog,[(PEL,0x5a525c16)],pel_groups);assert not external
    ordered={k:v for k,v in catalog.items()if k in selected and k!=(PEL,0x5a525c16)}
    ordered[PEL,0x5a525c16]=catalog[PEL,0x5a525c16]
    target=ROOT/'.cache/mhw_ls_combat/mods/MHW_WORLD_DEV/romfs/nativeNX/arc/forge/world_simple_fx.arc'
    target.write_bytes(pack(ordered))
    report={'status':'WORLD_LAYERS_BUILT','arc_sha256':sha(target),'resource_count':len(ordered),
        'resources':[{'path':n,'type':hex(t),'bytes':len(d)}for(n,t),(f,d)in ordered.items()],
        'sources':['wp03_005','wp03_050','wp03_060','wp03_004'],
        'iai_draw_line':line,'special_sheathe_flash':sheath_flash}
    (PROJECT/'research/world_simple_fx_bank.json').write_text(json.dumps(report,indent=2)+'\n')
    (PROJECT/'c/world_simple_fx_assets.h').write_text('#pragma once\n#define WORLD_SIMPLE_FX_COUNT '+str(len(ordered))+'u\n')
    print(report['status'],len(ordered),sha(target))

if __name__=='__main__':main()
