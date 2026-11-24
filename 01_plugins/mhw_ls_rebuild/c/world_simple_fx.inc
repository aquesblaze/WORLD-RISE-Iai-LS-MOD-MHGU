/* World event layers rendered by GU native particles. */
#include "world_simple_fx_assets.h"
static void *world_sfx_archive,*world_sfx_handle,*world_sfx_manager;
static unsigned world_sfx_ready,world_sfx_failed,world_sfx_seen;
static int world_sfx_hit;
static float world_sfx_origin[3];
/* 公会太刀 helm stroke bookkeeping, restored with the old hit flash. */
static unsigned world_helm_line_pending,world_helm_tail_pending;
/* ISS roundslash: schedule on damage hit, emit after F70-equivalent delay. */
static unsigned world_roundslash_pending;
static float world_roundslash_due;
static unsigned world_sfx_path(const char *a,const char *b)
{
    for(unsigned i=0;i<64;++i){char c=a[i]=='\\'?'/':a[i];if(c!=b[i])return 0;if(!c)return 1;}
    return 0;
}
static void world_fx_begin(void *a){(void)a;world_sfx_seen=0;world_sfx_hit=-1;world_helm_tail_pending=0;world_roundslash_pending=0;if(world.move!=W_LAND)world_helm_line_pending=0;}
static void world_sfx_oriented(void *a,const float *point,unsigned uid,const float *blade)
{
    if(!world_sfx_ready||*(void **)(main_base+0x18509e8)!=world_sfx_manager)return;
    unsigned char request[0x110] __attribute__((aligned(16)));
    ((void (*)(void *))(main_base+0x40b10))(request);put(request,8,2);
    put(request,20,word(request,20)|1);
    for(unsigned k=0;k<3;++k)set_real(request,32+4*k,point[k]);put(request,44,0);
    unsigned counter_line=uid==0x3f6b||uid==0x3f70||uid==0x3f71||uid==0x3fc3||uid==0x3fc4;
    unsigned line=uid==0x3f64||uid==0x3f6c||counter_line||blade;
    if(line){
        put(request,20,word(request,20)|2);
        unsigned yaw=counter_line?((world.heading+6007u)&65535u):u16(a,HEADING);
        set_real(request,48,0);set_real(request,52,(float)yaw*(360.0f/65536));set_real(request,56,0);
        if(blade){
            float x=blade[8],y=blade[9],z=blade[10],hor;
            float sum=x*x+z*z;
            __asm__("vsqrt.f32 %0, %1":"=t"(hor):"t"(sum));
            /* Geometry starts on local X, rotate it onto the posed blade axis. */
            unsigned az=world_direction(x,z),el=world_direction(y,hor);
            set_real(request,52,((int)az-16384)*(360.0f/65536));
            set_real(request,56,(float)(short)el*(360.0f/65536));
        }
    }
    uptr *vt=*(uptr **)a;
    uptr effect=((uptr (*)(void *,void *,u32,u32,void *,uptr))vt[0x138/4])
        (a,world_sfx_handle,2,uid,request,word(a,0x3310));
    world_last_effect=(u32)effect;
    if(uid>=0x3f61&&uid<=0x3f63)world_last_hit_effect=(u32)effect;
    ((void (*)(void *))(main_base+0x40b50))(request);
    log_event("world_simple_fx_emit",(u32)(uptr)a,uid,world.source,effect!=0);
    if(uid==0x3f64||uid==0x3f6b||uid==0x3f70||uid==0x3f71)
        log_event(uid==0x3f64?"world_iai_line":"world_iai_counter_line",(u32)(uptr)a,(u32)effect,u16(a,HEADING),(u32)(real(a,FRAME)*1000));
}
static void world_sfx_emit(void *a,const float *p,unsigned uid){world_sfx_oriented(a,p,uid,0);}
/* Update the private blade stroke after GU evaluates its native particle. */
static void *world_white_resource,*world_counter_core[3];
static float world_white_anchor[3];
static void world_white_stroke(void *a){
    for(unsigned k=0;k<3;++k)world_white_anchor[k]=real(a,0x40+4*k);
    world_sfx_emit(a,world_white_anchor,0x3f85);
}
#include "world_thrust_foresight_fx.inc"
#include "world_particle_dynamics.inc"
static int (*world_original_poly)(void *);
static int world_poly_update(void *g)
{
    int live=world_original_poly(g);
    if(!live||!world_bound)return live;
    void *effect=(void *)(uptr)word(g,8),*particle=(void *)(uptr)word(g,176);
    if(!effect||!particle)return live;
    unsigned res=word(effect,244);
    if(!res)return live;
    world_particle_motion(g,(void *)(uptr)res);
    world_tf_follow(g,(void *)(uptr)res);
    if(world.move==W_BIG&&world.rank&&
       (res==(u32)(uptr)world_counter_core[0]||res==(u32)(uptr)world_counter_core[1]||res==(u32)(uptr)world_counter_core[2])){
        void *a=(void *)(uptr)world_bound_actor;
        if(!a||world.epoch!=byte(a,AREA)||u16(a,MOTION)!=0x500+world.slot||byte(particle,125)!=2)return live;
        unsigned pale=res==(u32)(uptr)world_counter_core[0];
        float clock=real(a,FRAME)+(world.rank==2?2:0);
        float middle=pale?59:55,end=pale?64:58,early=pale?55:54;
        /* The two endpoints are in native particle space, retaining the cast direction. */
        float u=clock<early?.30f*(clock-52)/(early-52):
            clock<middle?.30f+.31f*(clock-early)/(middle-early):
            .61f+.39f*(clock-middle)/(end-middle);
        if(u<0)u=0;if(u>1)u=1;
        float reveal=.08f+.92f*u;
        float *vertices=(float *)((uptr)particle+u16(g,212));
        for(unsigned i=0;i<2;++i){
            float *near=vertices+8*i,*far=near+4;
            for(unsigned k=0;k<3;++k){
                float span=far[k]-near[k],pivot=near[k]+span*.124f;
                near[k]=pivot+(near[k]-pivot)*reveal;
                far[k]=pivot+(far[k]-pivot)*reveal;
            }
        }
        if(!(world_sfx_seen&(1u<<18))){
            world_sfx_seen|=1u<<18;log_event("world_counter_ribbon",(u32)(uptr)a,world.rank,(u32)clock,(u32)(1000*reveal));
        }
        return live;
    }
    unsigned white=res==(u32)(uptr)world_white_resource&&(world.move==W_SMALL||world.move==W_FORESIGHT||world.move==W_THRUST||world.move==W_DOWN||world.move==W_RISE);
    if(!white)return live;
    if(!(world_sfx_seen&1024)){world_sfx_seen|=1024;log_event("world_blade_layout",(u32)(uptr)g,word(particle,124),u16(g,212),word(g,52));}
    if(byte(particle,125)!=2)return live;
    void *a=(void *)(uptr)world_bound_actor;
    if(!a||u16(a,MOTION)!=0x500+world.slot||world.epoch!=byte(a,AREA))return live;
    void *w=(void *)(uptr)word(a,0x23a0);
    if(!w||word(w,0x30)!=(u32)(uptr)a)return live;
    const float *m=(const float *)((uptr)w+0xb0);
    float *buf=(float *)((uptr)particle+u16(g,212));
    for(unsigned ix=0;ix<4;++ix)for(unsigned k=0;k<3;++k)
        buf[ix*4+k]=m[12+k]-world_white_anchor[k]+m[8+k]*(ix&1?225.f:35.f)+m[k];
    if(!(world_sfx_seen&512)){world_sfx_seen|=512;log_event("world_blade_live",(u32)(uptr)a,(u32)(uptr)g,(u32)(uptr)particle,(u32)real(a,FRAME));}
    return live;
}
#include "world_helm_iai_fx.inc"
static void world_fx_tick(void *a)
{
    if(world_sfx_failed)return;
    if(!world_sfx_archive){
        void *manager=*(void **)(main_base+0x2126a64);if(!manager)return;
        uptr *vt=*(uptr **)manager;
        world_sfx_archive=((void *(*)(void *,void *,const char *,unsigned))vt[0x30/4])
            (manager,(void *)(main_base+0x2124df0),"arc/forge/world_simple_fx",1);
        if(!world_sfx_archive){world_sfx_failed=1;return;}
    }
    if(!world_sfx_ready){
        unsigned flags=byte(world_sfx_archive,0x50);
        if(flags&0x50){world_sfx_failed=1;log_event("world_simple_fx_failed",(u32)(uptr)a,flags,0,0);return;}
        if(!(flags&1))return;
        unsigned n=word(world_sfx_archive,0x68);void **objects=*(void ***)((uptr)world_sfx_archive+0x64);
        if(n!=WORLD_SIMPLE_FX_COUNT||!objects)return;
        void *pel=0;
        for(unsigned i=0;i<n;++i){
            if(!objects[i])return;unsigned child=byte(objects[i],0x50);
            if(child&0x50){world_sfx_failed=1;log_event("world_simple_fx_failed",(u32)(uptr)a,child,i,0);return;}
            if(!(child&1))return;
            if(world_sfx_path((char *)objects[i]+8,"effect/world/iai_line_e11_0"))world_counter_core[0]=objects[i];
            if(world_sfx_path((char *)objects[i]+8,"effect/world/iai_line_e10_0"))world_counter_core[1]=objects[i];
            if(world_sfx_path((char *)objects[i]+8,"effect/world/iai_line_e10_rank3"))world_counter_core[2]=objects[i];
            if(world_sfx_path((char *)objects[i]+8,"effect/world/iai_line_blade_white"))world_white_resource=objects[i];
            if(*(uptr *)objects[i]==main_base+0x175261c&&world_sfx_path((char *)objects[i]+8,"effect/pel/pl/world_simple"))pel=objects[i];
        }
        if(!pel)return;
        void *manager=*(void **)(main_base+0x18509e8);
        if(!manager||*(void **)(main_base+0x188a0d4)!=manager||*(uptr *)manager!=main_base+0x1731534)return;
        world_sfx_handle=((void *(*)(void *,void *))(main_base+0x3268d8))(manager,pel);
        if(!world_sfx_handle||word(world_sfx_handle,4)>=word(manager,0x5c)){world_sfx_failed=1;return;}
        world_sfx_manager=manager;world_sfx_ready=1;
        log_event("world_simple_fx_ready",(u32)(uptr)a,word(world_sfx_handle,4),n,0);
    }
    if((world.move==W_GROUND && world.source!=363)||!world_bound||world.actor!=(u32)(uptr)a||world.epoch!=byte(a,AREA)||!world.move||
       (int16_t)u16(a,HP)<=0||u16(a,STATE)!=16||u16(a,MOTION)!=0x500+world.slot)return;
    float frame=real(a,FRAME),point[3];
    world_tf_tick(a,frame);
    world_big_fx_tick(a,frame);
    /* The airborne blade stroke is separate from the delayed target impacts. */
    if(!(world_sfx_seen&(1u<<16))&&
       ((world.move==W_DOWN&&frame>=8)||(world.move==W_RISE&&frame>=2))){
        world_sfx_seen|=1u<<16;world_white_stroke(a);
    }
    /* 红线（0x3f81 及其尾迹）由 world_helm_line_tick 统一发射。 */
    const WEvent *event=w_event(world.source,frame);
    if(!event||event->hit<0||event->hit==world_sfx_hit)return;
    world_sfx_hit=event->hit;
    void *weapon=(void *)(uptr)word(a,0x23a0);
    const float *matrix=weapon&&word(weapon,0x30)==(u32)(uptr)a?world_bone(weapon,0):0;
    if(matrix){for(unsigned k=0;k<3;++k)point[k]=matrix[12+k]+matrix[8+k]*70;}
    else {for(unsigned k=0;k<3;++k)point[k]=real(a,0x40+4*k);point[1]+=80;}
    if(world.move==W_GROUND&&world.ground_node==1&&!world.spirit_paid)return;
    if(world.move==W_SMALL||world.move==W_FORESIGHT){
        world_white_stroke(a);return;
    }
    if(world.move==W_GROUND)world_sfx_emit(a,point,0x3f61);
}
