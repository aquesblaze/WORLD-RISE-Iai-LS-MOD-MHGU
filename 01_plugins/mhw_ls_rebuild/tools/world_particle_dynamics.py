"""Emit the source particle movement and scale parameters used by native ribbons."""
from animation_port import PROJECT


def write_dynamics():
    from world_helm_iai_fx import DYNAMICS as helm
    from world_thrust_foresight_fx import DYNAMICS as thrust
    rows=[]
    for path, index, attrs in helm+thrust:
        motion=attrs.get('VELOCITY3D',{})
        scale=attrs.get('SCALEANIM',{})
        axis=motion.get('baseAxis',1)
        speed=motion.get('speed',0)
        velocity=[0.,0.,0.]
        velocity[axis%3]=speed*(-1 if axis>=3 else 1)
        offset=[motion.get('offset'+k,0) for k in 'XYZ']
        stretch=[motion.get('size'+k,1)-1 for k in 'XYZ']
        sv=[scale.get('initialScaleSpeed',0)+scale.get('scaleSpeed'+k,0) for k in 'XYZ']
        sa=[scale.get('scaleAccel'+k,1) for k in 'XYZ']
        values=[*velocity,*offset,*stretch,motion.get('speedCoef',1),motion.get('gravity',0),*sv,*sa,
                motion.get('speed',0),motion.get('speedJitter',0)]
        ribbon=attrs['RIBBON']
        # Preserve the source coefficients; particle slots select stable speed jitter.
        floats=','.join(format(float(v),'.9f')+'f' for v in values)
        ids=','.join(str(v) for v in (index,motion.get('velocityType',0),ribbon['ribbonMode'],ribbon['subdivisionCount']-1))
        rows.append('{"'+path+'",'+ids+',{'+floats+'}}')
    text='#pragma once\ntypedef struct {const char *path; unsigned index, radial, mode, history; float p[19];} WParticleDynamics;\n'
    text+='static const WParticleDynamics world_particle_dynamics[]={\n'+',\n'.join(rows)+'\n};\n'
    (PROJECT/'c/world_particle_dynamics.h').write_text(text,encoding='utf8')
