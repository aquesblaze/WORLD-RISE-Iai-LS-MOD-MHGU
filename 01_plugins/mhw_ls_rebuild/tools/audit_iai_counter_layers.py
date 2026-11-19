"""Trace the rank selectors and preserve the original layer/curve evidence."""
import base64,hashlib,json,struct
from animation_port import ROOT,PROJECT
source=ROOT/'.cache/mhw_ls_ground_rebuild/full_presentation/wp03_004.json'
d=json.loads(source.read_text(encoding='utf8')); rows=d['full_efx']['entries']
def attrs(i):
    return {a['type']:a['fields'] for a in rows[i]['attributes'] if 'fields' in a}
def children(i):
    b=base64.b64decode(d['play'][i]['entries'][0]['raw']['bytes_base64'])
    n,=struct.unpack_from('<I',b,52);assert len(b)==56+4*n
    return struct.unpack_from('<'+'I'*n,b,56)
actions={}
for t in d['subselect']:
    parent=t['entries'][0]; a=attrs(parent); action=a['PTLIFE']['relationIndex']
    actions[t['table_type']]=dict(parent=parent,delay=a['SPAWN']['emitterDelayFrame'],action=action,children=children(action))
assert actions[2]['children']==(11,30,31,32,33) and actions[4]['children']==actions[8]['children']==(9,10,21,22,23,24,28,29)
layers={}
for idx in sorted(set(actions[2]['children']+actions[4]['children'])):
    a=attrs(idx);shape='RIBBON' if 'RIBBON' in a else 'BILLBOARD3D';v=a[shape];life=a['LIFE'];sp=a['SPAWN'];uv=a['UVSEQUENCE']
    layers[idx]=dict(shape=shape,color=v['color'],brightness=v['brightness'],width=v['width'],length_or_height=v.get('length',v.get('height')),
        delay=sp['emitterDelayFrame'],life=[life[k]for k in ('fadeInDuration','duration','fadeOutDuration')],spawn=[sp['spawnNum'],sp['loopNum']],
        source_texture_atlas=uv['path'].rstrip(chr(0)),sequence=uv['sequenceNo'],pattern_jitter=uv['patternNoJitter'],translation=a['TRANSFORM3D']['translate'][::2],bleed=a.get('LUMINANCEBLEED'))
    if idx in (10,11):
        anim=next(x for x in rows[idx]['timl']['animations'] if x)
        curves=anim['types'][0];assert curves['timelineParam']==0x1436e592
        keys={hex(tr['datatype']):[(k['frame'],[s['value'] for s in k['subs']]) for k in tr['keyframes']] for tr in curves['transforms']}
        assert keys['0x9f1e012e']==[(0,[50]),(30,[5])] and keys['0x58689812']==[(0,[255,101,101,255]),(100,[255,101,101,150])]
        layers[idx].update(ribbon_timl=keys,epv_color=[v['epvcolor_0'],v['epvcolor_1']],ribbon_mode=v['ribbonMode'],scale=v['scale'],
           thickness=v['width'],scale_y=[a['SCALEANIM']['scaleSpeedY'],a['SCALEANIM']['scaleAccelY']])
out={'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'selectors':actions,'layers':layers,
    'interpretation':'Data isolation (not live toggling): #11 white and #10 yellow/red are alternate red core filaments. White #30 warm lens, #31 cool soft wash, #32 delayed point particles, #33 offset bright glint. Colored #23 is short red glow, not the persistent red core.',
    'limits':'World TIML frames are effect-local. Compare visible duration with original motion-video samples, not LIFE=110. GU adapts original texture masks with native additive effects; no original HDR shader or full particle cloud.'}
(PROJECT/'research/world_iai_counter_layers.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf8')
