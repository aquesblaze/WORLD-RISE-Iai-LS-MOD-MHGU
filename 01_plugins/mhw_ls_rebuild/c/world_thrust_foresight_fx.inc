/* The EPV record owns the selector. Emit each selected resource once, allowing
 * its native generator to handle its own burst count and particle lifetime. */
static float world_tf_origins[3][3];
static float world_thrust_origins[3][3];
static void world_tf_follow(void *g,void *resource)
{
    if(world.move==W_THRUST){
        unsigned index=world_sfx_path((const char *)resource+8,"effect/world/tf_3d17")?0:
            world_sfx_path((const char *)resource+8,"effect/world/tf_3d1c")?1:
            world_sfx_path((const char *)resource+8,"effect/world/tf_3d16")?2:3;
        if(index==3)return;
        void *a=(void *)(uptr)world_bound_actor;
        if(!a||world.epoch!=byte(a,AREA)||u16(a,MOTION)!=0x500+world.slot)return;
        void *weapon=(void *)(uptr)word(a,0x23a0);
        const float *m=weapon&&word(weapon,0x30)==(u32)(uptr)a?world_bone(weapon,0):0;
        if(!m)return;
        for(void *p=(void *)(uptr)word(g,176);p;p=(void *)(uptr)word(p,4)){
            if(byte(p,125)!=2)continue;
            float *v=(float *)((uptr)p+u16(g,212));
            for(unsigned i=0;i<4;++i)for(unsigned k=0;k<3;++k)
                v[4*i+k]=m[12+k]-world_thrust_origins[index][k]+
                    m[8+k]*(i&1?220.f:35.f)+m[k]*(i<2?1.f:-1.f)*(index==2?4.f:2.f);
        }
        return;
    }
    if(world.move!=W_FORESIGHT)return;
    const char *path=(const char *)resource+8;
    unsigned index=world_sfx_path(path,"effect/world/tf_3d04")?0:
        world_sfx_path(path,"effect/world/tf_3d05")?1:
        world_sfx_path(path,"effect/world/tf_3d06")?2:3;
    if(index==3)return;
    void *a=(void *)(uptr)world_bound_actor;
    if(!a||world.epoch!=byte(a,AREA)||u16(a,MOTION)!=0x500+world.slot)return;
    const float *bone=world_bone(a,index?0:1);
    if(!bone)return;
    float delta[3];
    for(unsigned k=0;k<3;++k)
        delta[k]=bone[12+k]-(index==2?50*bone[4+k]:0)-world_tf_origins[index][k];
    for(void *p=(void *)(uptr)word(g,176);p;p=(void *)(uptr)word(p,4)){
        if(byte(p,125)!=2)continue;
        float *vertices=(float *)((uptr)p+u16(g,212));
        for(unsigned v=0;v<4;++v)for(unsigned k=0;k<3;++k)vertices[4*v+k]+=delta[k];
    }
}
static void world_tf_tick(void *a,float frame)
{
    if(world.move==W_FORESIGHT&&world.foresight_gauge&&!(world_sfx_seen&16)){
        world_sfx_seen|=16;
        /* EFX joints are skeleton indices: World2 is function1, World1
         * is function13 (GU0). They are not GU function IDs2 and1. */
        const float *body=world_bone(a,1),*pelvis=world_bone(a,0);
        if(body){
            for(unsigned k=0;k<3;++k)world_tf_origins[0][k]=body[12+k];
            world_sfx_oriented(a,body+12,0x3d02,body);
            world_sfx_oriented(a,body+12,0x3d04,body);
        }
        if(pelvis){
            for(unsigned k=0;k<3;++k)world_tf_origins[1][k]=pelvis[12+k];
            world_sfx_oriented(a,pelvis+12,0x3d05,pelvis);
            float p[3];
            for(unsigned k=0;k<3;++k)p[k]=pelvis[12+k]-50*pelvis[4+k];
            for(unsigned k=0;k<3;++k)world_tf_origins[2][k]=p[k];
            world_sfx_oriented(a,p,0x3d06,pelvis);
        }
        /* Source joint zero is actor-space. Its local Y is -30 in dist. */
        float dist[3]={real(a,0x40),real(a,0x44)-30,real(a,0x48)};
        world_sfx_emit(a,dist,0x3d03);
    }
    if(world.move!=W_THRUST||!world.rank||frame<10)return;
    void *w=(void *)(uptr)word(a,0x23a0);
    if(!w||word(w,0x30)!=(u32)(uptr)a)return;
    const float *m=world_bone(w,0);if(!m)return;
    float p[3];
    if(!(world_sfx_seen&256)){
        world_sfx_seen|=256;
        for(unsigned k=0;k<3;++k)p[k]=world_thrust_origins[0][k]=m[12+k];
        world_sfx_oriented(a,p,0x3d17,m);
    }
    if(frame>=84&&!(world_sfx_seen&16)){
        world_sfx_seen|=16;
        for(unsigned k=0;k<3;++k)p[k]=world_thrust_origins[1][k]=world_thrust_origins[2][k]=m[12+k];
        world_sfx_oriented(a,p,0x3d1c,m);
        world_sfx_oriented(a,p,0x3d16,m);
        for(unsigned k=0;k<3;++k)p[k]=m[12+k]+m[8+k]*180;
        world_sfx_oriented(a,p,0x3d1b,m);
        /* The old destination-colour proxy draws a solid disk, not refraction. */
    }
}
