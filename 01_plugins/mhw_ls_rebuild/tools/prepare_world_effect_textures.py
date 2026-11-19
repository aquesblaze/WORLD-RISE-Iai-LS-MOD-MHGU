"""Convert source UV atlases to private GU TEX/EAN resources, without EFL claims."""
import argparse,hashlib,json,shutil,struct,subprocess,sys
from pathlib import Path
import numpy as np
from PIL import Image
from animation_port import ROOT,PROJECT,sha

CACHE=ROOT/'.cache/mhw_ls_presentation'
OUT=CACHE/'gu_effects'
sys.path.insert(0,str(ROOT/'.cache/mhw_efx_editor'))
sys.path.insert(0,str(ROOT/'05_reference/经验包/MHGU_TEX_SKILL/code'))
import mtgu_tex

def native_ean(frames,width,height):
    """One native atlas entry; frame UVs remain in the source orientation."""
    assert frames and width<65536 and height<65536
    payload=struct.pack('<8I',32,len(frames),width//2,height//2,0,0,1|(1<<16),width|(height<<16))
    for frame in frames:
        u0,v0=frame.uv0;u1,v1=frame.uv1
        values=(u0*width,v0*height,(u1-u0)*width,(v1-v0)*height)
        pixels=[round(v)for v in values]
        assert all(abs(v-n)<.005 for v,n in zip(values,pixels)),('Subpixel atlas requires explicit native mapping',values)
        x,y,w,h=pixels
        assert 0<=x<=65535 and 0<=y<=65535 and 0<w<=65535 and 0<h<=65535
        payload+=struct.pack('<2I4f',x|(y<<16),w|(h<<16),u0,v0,u1,v1)
    return struct.pack('<4s3I',b'EAN\0',0x20120224,len(payload),0x01000001)+payload

def main():
    from efx_format.uvs import UVSFile
    ap=argparse.ArgumentParser();ap.add_argument('--clip',default='wp03_002');ap.add_argument('--emitter',type=int);args=ap.parse_args()
    decoded=CACHE/'decoded'/f'{args.clip}.json';emitters=json.loads(decoded.read_text(encoding='utf8'))
    selected={};bindings=[]
    for index,emitter in enumerate(emitters):
        if args.emitter is not None and index!=args.emitter:continue
        attrs={a['type']:a['fields']for a in emitter['attributes']}
        uv=attrs.get('UVSEQUENCE')
        if not uv:continue
        assert uv['sequenceNoJitter']==0,('Sequence range not implemented',index)
        path=uv['path'].rstrip('\0').replace('\\','/');key=(path,uv['sequenceNo'])
        selected[key]=None;bindings.append({'emitter':index,'key':key,'source_uv_fields':uv})
    OUT.mkdir(exist_ok=True);tex_dir=CACHE/'texture_conversion';tex_dir.mkdir(exist_ok=True)
    converter=ROOT/'MHW工具包/材质与贴图/MHWTexConverter_by_Jodo.exe';textures={};resources=[]
    for key in selected:
        path,sequence=key;source=CACHE/'source'/f'{path}.uvs';uvs=UVSFile.parse(source.read_bytes())
        assert uvs.serialize()==source.read_bytes()
        group=uvs.groups[sequence];assert group.map_count==1 and len(group.path_indices)==1
        texture_path=uvs.strings[group.path_indices[0]].path.replace('\\','/')
        if texture_path not in textures:
            original=CACHE/'source'/f'{texture_path}.tex';assert original.exists()
            private='effect/world/'+hashlib.sha256(texture_path.encode()).hexdigest()[:12]
            local=tex_dir/(private.split('/')[-1]+'.tex');shutil.copyfile(original,local)
            candidates=list(tex_dir.glob('*_'+local.stem+'.dds'))
            if not candidates:
                result=subprocess.run([str(converter),str(local)],capture_output=True,timeout=30)
                assert result.returncode==0,result.stderr
                candidates=list(tex_dir.glob('*_'+local.stem+'.dds'))
            assert len(candidates)==1,candidates
            dds=candidates[0];im=Image.open(dds).convert('RGBA');rgba=np.asarray(im);width,height=im.size
            swizzled=mtgu_tex.swizzle_mip(rgba,width,height,1,1,4)
            raw=mtgu_tex._pack_tex(width,height,1,7,[0],swizzled,8,0,2,1,1)
            info=mtgu_tex.parse_tex(raw)
            assert np.array_equal(mtgu_tex.deswizzle_mip(info.mips[0][2],width,height,1,1,4),rgba)
            target=OUT/(private.split('/')[-1]+'.tex');target.write_bytes(raw)
            im.save(target.with_suffix('.png'))
            textures[texture_path]={'path':private,'type':0x241f5deb,'output':str(target),'sha256':sha(target),
                'source':str(original),'source_sha256':sha(original),'dds_sha256':sha(dds),'width':width,'height':height,
                'rgba_sha256':hashlib.sha256(rgba.tobytes()).hexdigest(),'pixel_roundtrip_exact':True,
                'swizzle_k':mtgu_tex.swizzle_k_for(height)}
            resources.append(textures[texture_path])
        tex=textures[texture_path]
        order=group._frame_indices or list(range(len(group.frames)))
        assert all(0<=i<len(group.frames)for i in order)
        frames=[group.frames[i]for i in order]
        # Native EAN pivots are integer pixels (not float32). The source UVS
        # neutral pivot is .5/.5, confirmed by every selected frame here.
        assert all(f._unkn==(.5,.5,0.,0.)for f in frames)
        data=native_ean(frames,tex['width'],tex['height'])
        private='effect/world/'+hashlib.sha256((path+':'+str(sequence)).encode()).hexdigest()[:12]
        target=OUT/(private.split('/')[-1]+'.ean');target.write_bytes(data)
        record={'path':private,'type':0x4e397417,'output':str(target),'sha256':sha(target),
            'source':str(source),'source_sha256':sha(source),'sequence':sequence,'frame_count':len(frames),
            'source_frame_order':order,'texture':tex['path'],'width':tex['width'],'height':tex['height']}
        resources.append(record);selected[key]=record
    for row in bindings:row.update(ean=selected[tuple(row.pop('key'))]['path'])
    report={'status':'PASS_TEXTURE_PIXELS_AND_UV_ATLAS_ENCODING','clip':args.clip,'decoded_sha256':sha(decoded),
        'converter':str(converter),'converter_sha256':sha(converter),'resources':resources,'emitters':bindings,
        'installed':False,'native_render_verified':False,
        'limits':['TEX/EAN data transport only. Source shader channels, emitter transforms, lifetime and native EFL rendering are not validated by this report.']}
    target=PROJECT/'research'/f'{args.clip}_texture_conversion.json';target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print(report['status'],len(textures),'textures',len(selected),'atlases')

if __name__=='__main__':main()
