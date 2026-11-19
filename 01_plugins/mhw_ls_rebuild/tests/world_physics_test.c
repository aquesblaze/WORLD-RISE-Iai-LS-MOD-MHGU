#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "../c/world_core.h"

typedef uintptr_t uptr;
typedef uint32_t u32;
typedef u32 (*NativeCall)(void *,u32,u32,u32);
enum {AREA=0x1054,MOTION=0x4b4,FRAME=0x500};
static WState world;
static unsigned sample_sequence,world_bound;
static float real(const void *p,unsigned at){float v;memcpy(&v,(const char *)p+at,4);return v;}
static void set_real(void *p,unsigned at,float v){memcpy((char *)p+at,&v,4);}
static void put(void *p,unsigned at,u32 v){memcpy((char *)p+at,&v,4);}
static u32 word(const void *p,unsigned at){u32 v;memcpy(&v,(const char *)p+at,4);return v;}
static unsigned byte(const void *p,unsigned at){return ((const unsigned char *)p)[at];}
static unsigned u16(const void *p,unsigned at){uint16_t v;memcpy(&v,(const char *)p+at,2);return v;}
static unsigned local_guild(void *p){(void)p;return 1;}
static void log_event(const char *s,u32 a,u32 b,u32 c,u32 d){(void)s;(void)a;(void)b;(void)c;(void)d;}
#include "../c/world_physics.inc"

int main(void)
{
    unsigned char a[0x3400]={0};uint16_t motion=0x5e4;
    world=(WState){.actor=(u32)(uptr)a,.move=W_DOWN,.slot=228};
    memcpy(a+MOTION,&motion,2);world_bound=world_air_owned=world_down_applied=1;
    world_air_actor=(u32)(uptr)a;
    set_real(a,FRAME,32);set_real(a,0x44,350);set_real(a,0x10f0,0);
    world_physics_tick(a);
    assert(real(a,0x1014)==-75 && real(a,0x1024)==-.75f);
    /* Existing downward motion survives a gravity-only reset. */
    set_real(a,0x1014,-88);set_real(a,0x1024,0);world_physics_tick(a);
    assert(real(a,0x1014)==-88 && real(a,0x1024)==-.75f);
    /* A real floor contact must stay settled. */
    set_real(a,0x44,0);set_real(a,0x1014,0);set_real(a,0x1024,0);world_physics_tick(a);
    assert(real(a,0x1014)==0 && real(a,0x1024)==0);
    /* No change before the authored dive or after losing ownership. */
    set_real(a,0x44,350);set_real(a,FRAME,29);world_physics_tick(a);
    assert(real(a,0x1014)==0 && real(a,0x1024)==0);
    set_real(a,FRAME,32);world_air_owned=0;world_physics_tick(a);
    assert(real(a,0x1014)==0 && real(a,0x1024)==0);
    /* Native falling motion keeps its current speed and gravity. */
    world_air_owned=1;set_real(a,0x1014,-92);set_real(a,0x1024,-.75f);
    world_physics_tick(a);
    assert(real(a,0x1014)==-92 && real(a,0x1024)==-.75f);
    /* Even a stopped animation at its last frame must recover, without a timer. */
    set_real(a,FRAME,120);set_real(a,0x1014,0);set_real(a,0x1024,0);
    world_physics_tick(a);
    assert(real(a,0x1014)==-75 && real(a,0x1024)==-.75f);
    /* A replaced motion must never inherit the private dive recovery. */
    motion=0x501;memcpy(a+MOTION,&motion,2);
    set_real(a,0x1014,0);set_real(a,0x1024,0);world_physics_tick(a);
    assert(real(a,0x1014)==0 && real(a,0x1024)==0);
    motion=0x5e4;memcpy(a+MOTION,&motion,2);world_air_actor=0;
    world_physics_tick(a);assert(real(a,0x1024)==0);
    world_air_actor=(u32)(uptr)a;world_air_epoch=1;
    world_physics_tick(a);assert(real(a,0x1024)==0);
    world_physics_begin(a,W_RISE,0);
    assert(world_air_owner(a)&&world_air_epoch==0);
    return 0;
}
