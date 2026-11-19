#include <assert.h>
#include <math.h>
#include <stdint.h>
#include <string.h>
typedef uintptr_t uptr;
static unsigned sample_sequence=1;
static uptr word(const void *p,unsigned at){uptr n;memcpy(&n,(const char *)p+at,sizeof n);return n;}
static unsigned u16(const void *p,unsigned at){uint16_t n;memcpy(&n,(const char *)p+at,2);return n;}
static unsigned byte(const void *p,unsigned at){return ((const unsigned char *)p)[at];}
static int world_sfx_path(const char *a,const char *b){return strcmp(a,b)==0;}
#include "../c/world_particle_dynamics.inc"

int main(void)
{
    unsigned char generator[256]={0},particle[384]={0},resource[80]={0};
    uptr p=(uptr)particle;uint16_t index=1,offset=256;uint32_t age=2;
    memcpy(generator+176,&p,sizeof p);memcpy(generator+30,&index,2);
    memcpy(generator+212,&offset,2);memcpy(particle+20,&age,4);
    particle[125]=2;
    strcpy((char *)resource+8,"effect/world/iai_line_helm_impact");
    float *vertices=(float *)(particle+256);
    for(unsigned i=0;i<4;++i)vertices[4*i]=i&1?1:-1;
    world_particle_motion(generator,resource);
    // World wp03_060 #2 expands by 0.45 on each simulation tick.
    assert(fabsf(vertices[0]+1.9f)<.0001f);
    assert(fabsf(vertices[4]-1.9f)<.0001f);
    // Updating the same live particle again must not multiply its scale twice.
    ++sample_sequence;
    world_particle_motion(generator,resource);
    assert(fabsf(vertices[4]-1.9f)<.0001f);
    assert(fabsf(world_series(.5f,3)-1.75f)<.0001f);
    assert(world_series(1,100)==100);
    strcpy((char *)resource+8,"effect/world/tf_3d06");
    index=0;memcpy(generator+30,&index,2);
    age=0;memcpy(particle+20,&age,4);
    for(unsigned i=0;i<4;++i){vertices[4*i]=0;vertices[4*i+1]=i&1?200:-200;}
    ++sample_sequence;
    world_particle_motion(generator,resource);
    age=2;memcpy(particle+20,&age,4);++sample_sequence;
    world_particle_motion(generator,resource);
    // A rotated trail must discard the old rigid span along its actual axis.
    assert(fabsf(vertices[5]-vertices[1])<10);
    return 0;
}
