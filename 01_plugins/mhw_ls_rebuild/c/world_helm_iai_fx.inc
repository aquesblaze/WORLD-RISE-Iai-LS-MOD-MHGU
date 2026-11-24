/* 公会太刀 hit flash and Iai layers, restored on request. These are the
 * v1.0.1 effect set (native EPV cm121 hit flashes plus the old custom
 * iai_line/helm emitters); the v1.0.7 grouped 0x3fc* bank stays in the arc for
 * the parts the rest of the rebuild still uses. */
static float world_helm_line_point[3],world_helm_line_start;
static unsigned world_helm_line_actor,world_helm_line_epoch;
static void world_helm_line(void *a,const float *point)
{
    void *weapon=(void *)(uptr)word(a,0x23a0);
    const float *blade=weapon&&word(weapon,0x30)==(u32)(uptr)a?world_bone(weapon,0):0;
    world_helm_stroke(world_helm_blade,blade,point);
    for(unsigned k=0;k<3;++k)world_helm_line_point[k]=world_helm_blade[12+k];
    world_helm_line_actor=(u32)(uptr)a;world_helm_line_epoch=byte(a,AREA);
    world_helm_line_start=world_elapsed;world_helm_tail_pending=1;
    world_sfx_oriented(a,world_helm_line_point,0x3f81,world_helm_blade);
    log_event("world_helm_line_tip",(u32)(uptr)a,word(world_helm_line_point,0),word(world_helm_line_point,4),word(world_helm_line_point,8));
}
static void world_helm_line_tick(void *a)
{
    if(!world_helm_tail_pending)return;
    if(world_helm_line_actor!=(u32)(uptr)a||world_helm_line_epoch!=byte(a,AREA)||(int16_t)u16(a,HP)<=0){
        world_helm_tail_pending=0;return;
    }
    /* Keep the old five/six-frame tail spacing, relative to actual damage. */
    while(world_helm_tail_pending&&60*(world_elapsed-world_helm_line_start)>=4+world_helm_tail_pending-.001f){
        unsigned phase=world_helm_tail_pending-1;
        if(!phase){world_sfx_oriented(a,world_helm_line_point,0x3f84,world_helm_blade);world_sfx_emit(a,world_helm_line_point,0x3f83);}
        for(unsigned i=0;i<2;++i){
            float p[3]={world_helm_line_point[0]+world_helm_blade[8]*(-25-(i*2+phase)*110),
                world_helm_line_point[1]+world_helm_blade[9]*(-25-(i*2+phase)*110),
                world_helm_line_point[2]+world_helm_blade[10]*(-25-(i*2+phase)*110)};
            world_sfx_oriented(a,p,0x3f82,world_helm_blade);
        }
        world_helm_tail_pending=phase?0:2;
    }
}

static void world_fx_hit(void *a,const float *point,unsigned ordinal)
{world_sfx_emit(a,point,0x3f61+ordinal%3);}
static void world_big_fx_tick(void *a,float frame)
{
    /* Fire pending roundslash even if move already transitioned past W_BIG. */
    if(world_roundslash_pending&&!(world_sfx_seen&(1u<<20))&&world_elapsed>=world_roundslash_due){
        world_sfx_seen|=1u<<20;
        world_roundslash_pending=0;
        float rp[3];
        for(unsigned k=0;k<3;++k)rp[k]=real(a,0x40+4*k);
        rp[1]-=30.0f;
        world_sfx_emit(a,rp,0x3f6c);
        log_event("world_native_roundslash",(u32)(uptr)a,0x3f6c,(u32)(frame*1000),0);
    }
    if(world.move!=W_BIG)return;
    /* Native GU spirit roundslash: cm121_072 (PEL 0x3f6c). Schedule on ISS
     * counter+hit damage, then emit after delay so it appears at ~F70. */
    if(world.counter_success&&world.hit_success&&!world_roundslash_pending&&!(world_sfx_seen&(1u<<20))){
        world_roundslash_pending=1;
        float delay=(70.0f-frame)/60.0f;
        if(delay<0)delay=0;
        world_roundslash_due=world_elapsed+delay;
    }
}
