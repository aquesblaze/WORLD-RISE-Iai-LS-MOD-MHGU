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
    if(world.move!=W_BIG)return;
    float point[3];
    if(frame>=(world.source==308||world.source==310?10:12)&&!(world_sfx_seen&4)){
        world_sfx_seen|=4;
        if(world_joint47(a,point)){
            world_sfx_emit(a,point,0x3f64);
            world_sfx_emit(a,point,0x3f65);
        }
    }
    if(world.counter_success&&frame>=12&&!(world_sfx_seen&8)){
        world_sfx_seen|=8;
        if(world_joint47(a,point))for(unsigned uid=0x3f66;uid<=0x3f68;++uid)world_sfx_emit(a,point,uid);
    }
    /* World training footage: the second streak crosses the finish of the
     * dash as the hunter turns. Its long axis stays in the scene.
     * EFL submits ahead of presentation: capture shows ~4 motion frames
     * from requesting the first particle to its first visible pixels.
     * The second stroke uses entry rank, including a complete whiff. */
    if(world.rank&&frame>=(world.rank==2?50:52)){
        unsigned white=world.rank==1;
        if(!(world_sfx_seen&(1u<<5))){
            for(unsigned k=0;k<3;++k)world_sfx_origin[k]=real(a,0x40+4*k);
            world_sfx_origin[1]+=83;
            world_sfx_seen|=1u<<5;
            world_sfx_emit(a,world_sfx_origin,white?0x3f6b:(world.rank==3?0x3f71:0x3f70));
            world_sfx_emit(a,world_sfx_origin,white?0x3f7c:0x3f7d);
            world_sfx_emit(a,world_sfx_origin,white?0x3f75:0x3f77);
            if(!white){world_sfx_emit(a,world_sfx_origin,0x3f78);world_sfx_emit(a,world_sfx_origin,0x3f79);}
        }
        if(frame>=73&&!(world_sfx_seen&(1u<<19))){
            world_sfx_seen|=1u<<19;
            for(unsigned i=0;i<12;++i)world_sfx_emit(a,world_sfx_origin,0x3f90+12*(world.rank-1)+i);
        }
        if(frame>=54&&!(world_sfx_seen&(1u<<10))){
            world_sfx_seen|=1u<<10;
            world_sfx_emit(a,world_sfx_origin,white?0x3f76:0x3f7a);
            if(!white)world_sfx_emit(a,world_sfx_origin,0x3f7b);
        }
    }
    if(world.counter_success&&world.rank==1&&
       (world_sfx_seen&(1u<<5))&&frame>=61&&!(world_sfx_seen&(1u<<17))){
        world_sfx_seen|=1u<<17;
        world_sfx_emit(a,world_sfx_origin,0x3f88);
    }
}
