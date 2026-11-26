/* Delayed contacts retain a monster-local bone point, not a stale world point.
 * GU's native Sakura shell owns allocation, damage dispatch and destruction.
 * World source timing: first helm0.4s, interval0.05s, seven; big Iai0.5s.
 */
typedef struct {
    unsigned live,target,uid,area,tier,kind,emitted;
    int bone;float point[3],remaining,age;
} WFollow;
static WFollow world_follow[8];
/* Keep suppressing hitstop after the dive becomes W_LAND, while any Helm
 * shell is still travelling or pending. */
static unsigned world_helm_active(void *a)
{
    if(world.actor&&a&&(u32)(uptr)a!=world.actor)return 0;
    if(world.move==W_DOWN||world.move==W_LAND)return 1;
    for(unsigned i=0;i<8;++i)
        if(world_follow[i].live&&world_follow[i].kind==1)return 1;
    return 0;
}
static unsigned world_follow_captured,world_helm_tier;
static unsigned world_helm_count,world_helm_hit_frame;
static unsigned world_helm_emitted,world_helm_audio_hit;
#if ML_WORLD_PRESENTATION
static float world_helm_sound_point[3];
#endif
/* 公会太刀的红线：捕获命中瞬间的刀姿，之后用这条刀身四边形发射 0x3f81。 */
static float world_helm_blade[16];
#include "world_helm_stroke.h"
typedef struct {unsigned target;float next;} WPrimaryCooldown;
static WPrimaryCooldown world_primary_cooldown[10];
static float world_elapsed;
static u32 (*world_original_monster_query)(void *,void *,void *);
typedef void (*WMonsterDamage)(void *,void *,void *,void *,void *,void *,void *);
static void (*world_original_monster_damage)(void *,void *,void *,void *,void *,void *,void *,void *);
static unsigned world_owned_shell_attack(void *attack);
static unsigned world_primary_helm(void *attack)
{
    return world_attack_owned&&(uptr)attack==(uptr)world_attack_actor+0x3020&&
        u16(attack,0x34)==world_attack_id&&(world.move==W_DOWN||world.move==W_LAND);
}
static unsigned world_owns_weapon_hit(void *attack)
{
    return world_attack_owned&&(uptr)attack==(uptr)world_attack_actor+0x3020&&
        u16(attack,0x34)==world_attack_id;
}
static void (*world_original_contact_stop)(void *,void *);
static void world_contact_stop(void *manager,void *attack)
{
    void *a=(void *)(uptr)world_attack_actor;
    /* Only the outgoing contact pause of an owned Small ISS weapon hit is
     * replaced. Every other attack keeps GU's native hitstop. */
    if(world.move==W_SMALL&&world_owns_weapon_hit(attack)&&world_bound&&
       world_bound_actor==(u32)(uptr)a&&world.epoch==byte(a,AREA)&&
       u16(a,STATE)==16&&u16(a,ACTION)==w_action(W_SMALL)&&u16(a,MOTION)==0x500+world.slot&&
       byte(attack,0x6e)==0&&(word(attack,0x30)&8)&&word(attack,0x70)==(u32)(uptr)a){
        /* GU stores the hunter's hitstop pair at +0x27ac/+0x27b0. Two native
         * timer units are the slow timer's lightest positive request, so all
         * Small ISS contacts get the same short pause instead of GU's
         * varying values. Damage and animation are untouched. */
        set_real(a,0x27ac,0);
        set_real(a,0x27b0,2);
        log_event("world_small_contact_stop",(u32)(uptr)a,byte(attack,6),u16(attack,0x34),word(a,0x27b0));
        return;
    }
    world_original_contact_stop(manager,attack);
}
static void world_monster_damage(void *manager,void *attack,void *target,void *point,
                                 void *v1,void *v2,void *part,void *shape)
{
    /* GU171350's native type42 path records the real intersection, hurtpart
     * and target, but skips damage, hitstop, sharpness and gauge callbacks.
     * World COL82 is a zero-damage sampler; only its delayed shells hurt.
     * Change the type after native collision filtering, then restore it before
     * returning to that pass. All other attacks retain their native path. */
    unsigned helm=world_primary_helm(attack);
    if(!helm){
        world_original_monster_damage(manager,attack,target,point,v1,v2,part,shape);
        /* Delayed Helm shells use real GU attacks, so their hit callback can
         * set hitstop after the W_LAND transition. Clear it too. */
        if(world.actor&&world_owned_shell_attack(attack))
            world_helm_clear_hitstop((void *)(uptr)world.actor);
        return;
    }
    unsigned type=byte(attack,0x3a);
    *(unsigned char *)((uptr)attack+0x3a)=0x42;
    ((WMonsterDamage)(main_base+0x171350))(manager,attack,target,point,v1,v2,part);
    *(unsigned char *)((uptr)attack+0x3a)=(unsigned char)type;
    if(helm)world_helm_clear_hitstop((void *)(uptr)world_attack_actor);
}
static void (*world_original_shell_position)(void *);
typedef struct {unsigned shell,request,helm_impact;float until,point[3];} WShellPosition;
static WShellPosition world_shell_positions[32];
static unsigned world_owned_shell_attack(void *attack)
{
    for(unsigned i=0;i<32;++i){
        WShellPosition *p=world_shell_positions+i;
        if(p->shell&&p->until>=world_elapsed&&p->shell+0x13a8==(u32)(uptr)attack)return 1;
    }
    return 0;
}
static void world_shell_position(void *shell)
{
    for(unsigned i=0;i<32;++i){
        WShellPosition *p=world_shell_positions+i;
        if(p->shell==(u32)(uptr)shell&&p->request==word(shell,0x136c)&&world_elapsed<=p->until){
            for(unsigned k=0;k<3;++k)set_real(shell,0x40+4*k,p->point[k]);
            return;
        }
    }
    world_original_shell_position(shell);
}
static void *world_monster(unsigned uid)
{
    void *manager=(void *)(uptr)*(u32 *)(main_base+0x1851fe0);
    return manager?((void *(*)(void *,u32))(main_base+0x5ceb4))(manager,uid):0;
}
static const float *world_bone(void *a,int bone)
{
    if(!a)return 0;
    uptr *vt=*(uptr **)a;
    return ((const float *(*)(void *,int))vt[(bone<0?0x54:0xd0)/4])(a,bone);
}
static const float *world_raw_bone(void *a,unsigned bone)
{
    unsigned count=word(a,0x490);uptr records=word(a,0x494);
    /* Native53aad8 resolves function IDs through498 into160-byte records494;
     * the posed matrix begins at record10.490 is the allocated record count. */
    return records&&count<=256&&bone<count?(const float *)(records+160*bone+0x10):0;
}
/* Source equipment helper47 is a child of left-hand function12, rather
 * than the hand origin itself. Samples use the same source local
 * coordinates as the real weapon attachment controller. */
#if ML_WORLD_FX_PROBE || ML_WORLD_AUDIO_PROBE || ML_WORLD_PRESENTATION
static unsigned world_joint47(void *a,float *out)
{
    unsigned motion=u16(a,MOTION);float frame=W_ATTACH_FRAME(motion,real(a,FRAME));
    const MLAttachmentClip *clip=0;
    for(unsigned i=0;i<sizeof(ml_attachment_clips)/sizeof(*clip);++i)
        if(W_ATTACH_SLOT(motion)==ml_attachment_clips[i].slot){clip=ml_attachment_clips+i;break;}
    if(!clip||!(frame>=0&&frame<10000))return 0;
    unsigned n=(unsigned)frame;if(n>=clip->frames)n=clip->frames-1;
    unsigned next=n+1<clip->frames?n+1:n;float f=frame-(float)n;if(f>1)f=1;
    const float *x=ml_attachment_samples[clip->offset+n]+7,*y=ml_attachment_samples[clip->offset+next]+7;
    const float *m=world_bone(a,12);if(!m)return 0;
    float p[3];for(unsigned k=0;k<3;++k)p[k]=x[k]+(y[k]-x[k])*f;
    for(unsigned k=0;k<3;++k)out[k]=m[12+k]+m[k]*p[0]+m[4+k]*p[1]+m[8+k]*p[2];
    return 1;
}
#endif
static int world_nearest_bone(void *target,const void *a)
{
    float nearest=1.0e30f;int bone=-1;
    unsigned count=word(target,0x490);if(count>256)return -1;
    for(unsigned i=0;i<count;++i){
        const float *m=world_raw_bone(target,i);if(!m)break;
        float d=0;for(unsigned k=0;k<3;++k){float v=m[12+k]-real(a,0x40+4*k);d+=v*v;}
        if(d<nearest){nearest=d;bone=(int)i;}
    }
    return bone;
}
static unsigned world_inverse(const float *m,const float *p,float *out)
{
    float x=p[0]-m[12],y=p[1]-m[13],z=p[2]-m[14];
    float a=m[0],b=m[4],c=m[8],d=m[1],e=m[5],f=m[9],g=m[2],h=m[6],i=m[10];
    float det=a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g);
    if(!(det>0.000001f||det<-.000001f))return 0;
    out[0]=((e*i-f*h)*x+(c*h-b*i)*y+(b*f-c*e)*z)/det;
    out[1]=((f*g-d*i)*x+(a*i-c*g)*y+(c*d-a*f)*z)/det;
    out[2]=((d*h-e*g)*x+(b*g-a*h)*y+(a*e-b*d)*z)/det;
    for(unsigned j=0;j<3;++j)if(!(out[j]>-1000000&&out[j]<1000000))return 0;
    return 1;
}
static void world_follow_clear(void)
{
    for(unsigned i=0;i<8;++i){world_follow[i].live=0;world_follow[i].remaining=0;}
#if ML_WORLD_PRESENTATION
    for(unsigned i=0;i<32;++i)world_shell_positions[i].helm_impact=0;
#endif
    world_follow_captured=world_helm_tier=0;
    world_helm_count=world_helm_emitted=0;
    world_helm_hitstop_seen=0;
    for(unsigned i=0;i<10;++i)world_primary_cooldown[i].target=0;
}
static void world_follow_capture(void *a)
{
    unsigned helm=world.move==W_DOWN||world.move==W_LAND;
    if((helm&&world_helm_count>=7)||(!helm&&world.move!=W_BIG)||!world_contact(a))return;
    /* A no-color Iai still records the hit target for its camera, although
     * it has no delayed damage shell. */
    unsigned tier=helm?world_helm_tier:world.rank;
    /* 勇气风格蓝刃（原生气刃等级 4 及以上）的登龙按红刃（3）判定伤害。 */
    if(helm&&tier>3){tier=3;log_event("world_helm_tier_red",(u32)(uptr)a,world.rank,0,0);}
    if((helm&&!tier)||tier>3)return;
    void *target=(void *)(uptr)word(a,0x30d0);void *part=(void *)(uptr)word(a,0x30cc);
    void *data=(void *)(uptr)word(target,0x1428);unsigned uid=byte(data,0x1b5);
    if(world_monster(uid)!=target||byte(target,AREA)!=world.epoch)return;
    int bone=(int16_t)u16(part,0);if(bone==255)bone=-1;
    if(helm){
        int other=(int16_t)u16(part,2);if(other==255)other=-1;
        const float *m1=world_bone(target,bone),*m2=world_bone(target,other);
        if(m1&&m2){
            float d1=0,d2=0;
            for(unsigned k=0;k<3;++k){float p=real(a,0x3040+4*k),x=m1[12+k]-p,y=m2[12+k]-p;d1+=x*x;d2+=y*y;}
            if(d2<d1)bone=other;
        }
    }
    if(!helm)bone=world_nearest_bone(target,a);
    const float *matrix=helm?world_bone(target,bone):bone<0?0:world_raw_bone(target,(unsigned)bone);
    float point[3];if(!matrix)return;
    if(helm){if(!world_inverse(matrix,(const float *)((uptr)a+0x3040),point))return;}
    else for(unsigned k=0;k<3;++k)point[k]=real(a,0x3040+4*k)-matrix[12+k];
    /* Source big Iai owns one pending record2cf0, overwritten by a subsequent
     * genuine contact. It does not emit one additional shell per target. */
    WFollow *job=world_follow+(helm?world_helm_count:7);
    /* Source2122682 rejects a still-positive slot.21226fc/212272a copies
     * the previous slot's remaining timer, which freezes once it crosses0.
     * An absolute deadline would continue ageing after emission and therefore
     * mis-time a later blade contact following fallback shells. */
    if(helm&&job->remaining>0)return;
    float remaining=helm?(world_helm_count?world_follow[world_helm_count-1].remaining+.05f:.4f):.5f;
    *job=(WFollow){.live=1,.target=(u32)(uptr)target,.uid=uid,.area=world.epoch,.tier=tier,
        .kind=helm?1:(world.counter_success||world_counter_seen)?3:2,.bone=bone,
        .point={point[0],point[1],point[2]},.remaining=remaining,.age=world_elapsed,.emitted=helm?world_helm_count:0};
    world_follow_captured=1;
    if(helm){
        #if ML_WORLD_PRESENTATION
        if(!world_helm_count){
            void *weapon=(void *)(uptr)word(a,0x23a0);
            const float *blade=weapon&&word(weapon,0x30)==(u32)(uptr)a?world_bone(weapon,0):0;
            world_helm_stroke(world_helm_blade,blade,(const float *)((uptr)a+0x3040));
            for(unsigned k=0;k<3;++k)world_helm_sound_point[k]=real(a,0x3040+4*k);
            world_audio_blade(a,world_helm_sound_point);
        }
#endif
        ++world_helm_count;
        for(unsigned i=0;i<10;++i)if(!world_primary_cooldown[i].target||world_primary_cooldown[i].target==(u32)(uptr)target){
            world_primary_cooldown[i]=(WPrimaryCooldown){(u32)(uptr)target,world_elapsed+1.5f/60};break;
        }
        log_event("world_helm_primary",(u32)(uptr)a,world_helm_count,(u32)(uptr)target,(u32)real(a,FRAME));
        log_event("world_helm_clock",(u32)(uptr)a,world_helm_count,(u32)(world_elapsed*1000),(u32)real(a,FRAME));
    }
    log_event("world_follow_capture",(u32)(uptr)a,job->kind,tier,uid);
}
static u32 world_monster_query(void *manager,void *attack,void *target)
{
    unsigned own=world_attack_owned&&(uptr)attack==(uptr)world_attack_actor+0x3020&&u16(attack,0x34)==world_attack_id;
    unsigned helm=own&&(world.move==W_DOWN||world.move==W_LAND);
    if(helm){
        if(world_helm_count>=7)return 0;
        for(unsigned i=0;i<10;++i)if(world_primary_cooldown[i].target==(u32)(uptr)target&&world_elapsed<world_primary_cooldown[i].next)return 0;
    }
    u32 result=world_original_monster_query(manager,attack,target);
#if ML_WORLD_PRESENTATION
    if(!own && byte(attack,0xb4)==1 && word(attack,0xb0)==(u32)(uptr)target){
        for(unsigned i=0;i<32;++i){
            WShellPosition *p=world_shell_positions+i;
            if(!p->helm_impact||p->shell+0x13a8!=(u32)(uptr)attack||p->until<world_elapsed)continue;
            void *shell=(void *)(uptr)p->shell;
            if(p->request!=word(shell,0x136c)||!world.actor)continue;
            if(p->helm_impact==1&&!world_helm_audio_hit){
                world_helm_audio_hit=1;
                /* Sound follows the first real delayed hit, even after a landing cancel. */
                world_audio_epv((void *)(uptr)world.actor,25530,(const float *)((uptr)attack+0x20));
                /* 登龙命中: one rumble per Helm, on the first real contact. */
                world_rumble_start(0.8f,-1.0f);
            }
            p->helm_impact=0;
            /* FX comes from the restored 公会太刀 path in world_burst. */
            log_event("world_helm_fx_contact",world.actor,p->shell,(u32)(uptr)target,p->request);
            break;
        }
    }
#endif
    /* Query returns once per actual target, unlike polling the last-contact
     * field next update. The native pass owns every intersection and callback. */
    if((helm||world.move==W_BIG)&&own&&byte(attack,0xb4)==1&&
       word(attack,0xb0)==(u32)(uptr)target)
        world_follow_capture((void *)(uptr)world.actor);
    if(world.actor&&world_helm_active((void *)(uptr)world.actor))
        world_helm_clear_hitstop((void *)(uptr)world.actor);
    return result;
}
static unsigned world_burst(void *a,WFollow *job,const float *point)
{
    /* GU can deliver another blade contact after a tail fallback has already
     * emitted on a long frame. Remaining<=0 is not an unused slot: retain
     * a per-Helm ordinal ledger so that contact cannot emit the same segment
     * again. Reset only for a new Helm or ownership teardown. */
    if(job->kind==1&&(world_helm_emitted&(1u<<job->emitted))){
        log_event("world_helm_duplicate_suppressed",(u32)(uptr)a,job->emitted,world_helm_count,world_helm_emitted);
        return 0;
    }
    /*2122234 and21255f5 select the last shell for ordinal6, for genuine
     * and fallback contacts alike. Its source COL part multiplier is3.0,
     * versus0.9 for earlier shells; physical/elemental values stay equal. */
    unsigned source=(job->kind==1?(job->emitted==6?1020:1000):1010)+job->tier,hit=0,shape=0;
    for(unsigned i=0;i<sizeof(world_hits)/sizeof(*world_hits);++i)
        if(world_hits[i].source==source){hit=world_hits[i].hit;shape=world_hits[i].shape;break;}
    if(!hit)return 0;
    void *manager=(void *)(uptr)*(u32 *)(main_base+0x1892550);if(!manager)return 0;
    unsigned char *r=((void *(*)(u32,u32))(main_base+0x474204))(0x30,0x10);if(!r)return 0;
    for(unsigned i=0;i<0x30;++i)r[i]=0;
    put(r,0,main_base+0x1760e2c);put(r,4,45);put(r,12,(u32)(uptr)a);
    for(unsigned i=0;i<3;++i)set_real(r,16+4*i,point[i]);
    *(uint16_t *)(r+32)=job->uid;*(uint16_t *)(r+34)=255;
    void *shell=((void *(*)(void *,void *,u32))(main_base+0x48c4f0))(manager,r,0);
    if(!shell)return 0;
    if(job->kind==1)world_helm_emitted|=1u<<job->emitted;
    /* World21253a6 starts regeneration with the first emitted shell, rather
     * than the earlier zero-damage blade contact. */
    if(job->kind==1&&job->emitted==0)world_helm_regen=job->tier==3?15:10;
    /* World resolves the delayed contact point at emission. Sakura normally
     * follows its target bone every frame (474674), so intercept that updater
     * only for these owned shells and retain the emitted World position. */
    for(unsigned i=0;i<32;++i)if(!world_shell_positions[i].shell||world_shell_positions[i].until<world_elapsed){
        world_shell_positions[i]=(WShellPosition){.shell=(u32)(uptr)shell,.request=word(shell,0x136c),.helm_impact=job->kind==1?1:2,
            .until=world_elapsed+.6f,.point={point[0],point[1],point[2]}};break;
    }
    /* Native674404 uses byte7 as started and byte6 as burst count. 255
     * suppresses the Sakura repeat branch; each World job owns one contact.
     * 1378 is elapsed age, not remaining life: advancing it kills the shell. */
    *(unsigned char *)((uptr)shell+6)=255;*(unsigned char *)((uptr)shell+7)=1;
    void *collider=(void *)((uptr)shell+0x13a8);
    ((void (*)(void *,void *,void *,u32,u32,u32))(main_base+0x2b7520))(a,shell,collider,1,hit,0);
    put(collider,0x88,shape);
    /* Helm Breaker rebalance: 8/10/13 MV per hit and 0.3/0.4/0.6 part
     * modifier for hits1-3, hits4-6 and hit7. The regenerated ARC already has
     * the new values; patch only the old source values so a stale deployed ARC
     * agrees too. Owned Helm shells only; byte0x3a (attack type) is untouched. */
    if(job->kind==1){
        unsigned mv=u16(collider,0x38);
        if(job->tier==1&&mv==10u)*(uint16_t *)((uptr)collider+0x38)=(uint16_t)W_HELM_WHITE_MV;
        else if(job->tier==2&&mv==15u)*(uint16_t *)((uptr)collider+0x38)=(uint16_t)W_HELM_YELLOW_MV;
        else if(job->tier==3&&mv==25u)*(uint16_t *)((uptr)collider+0x38)=(uint16_t)W_HELM_RED_MV;
        /* job->emitted is the Helm hit ordinal0..6, including fallback shells. */
        set_real(collider,0x98,job->emitted<3?W_HELM_PART_EARLY:
            (job->emitted<6?W_HELM_PART_MID:W_HELM_PART_LAST));
    }
    /* Native3798cc skips hit visuals for effect ID0. Both source Helm and
     * delayed Iai SHLPs bind EPV2006/0; Sakura45 would duplicate that flash. */
    /* 公会太刀 kept the native shell hit visual; it is the old hit flash. */
    /* Both source delayed shell SHLPs live for0.5s. A3-frame shortcut could
     * expire before the collision pass on a slow frame; native attack IDs
     * already prevent repeat damage to the same target. */
    set_real(collider,0x5c,0);set_real(collider,0x60,30);
    put(collider,0x30,word(collider,0x30)|0x08000000u);
    if(job->kind==3)set_real(collider,0x98,real(collider,0x98)*1.3f);
    typedef float (__attribute__((pcs("aapcs-vfp"))) *ShellFloat)(void *,u32);
    float lifetime=((ShellFloat)(main_base+0x4a2ed0))(shell,0);
    set_real(shell,0x1378,lifetime>30?lifetime-30:0);
    log_event("world_burst",(u32)(uptr)a,source,job->emitted,(u32)(uptr)shell);
#if ML_WORLD_PRESENTATION
    /* Restored 公会太刀 visuals: one sustained stroke at the first shell
     * actually emitted, plus the native hit flash on every emitted shell. */
    if(job->kind==1&&world_helm_emitted==(1u<<job->emitted)){
        world_helm_line(a,point);
    }
    world_fx_hit(a,point,job->emitted);
#endif
    return 1;
}
static void world_follow_tick(void *a,float dt)
{
    world_elapsed+=dt;
    for(unsigned i=0;i<8;++i){
        WFollow *job=world_follow+i;if(!job->live)continue;
        /* Source2125860 retains a pending Iai shell only in action0x66.
         * An already emitted shell owns its lifetime independently. */
        if(job->kind!=1&&(world.move!=W_BIG||u16(a,STATE)!=16||u16(a,ACTION)!=w_action(W_BIG))){job->live=0;continue;}
        void *target=world_monster(job->uid);
        if(job->area!=byte(a,AREA)||(u32)(uptr)target!=job->target||
           byte(target,AREA)!=job->area||world_elapsed-job->age>3){job->live=0;continue;}
        if(!(job->remaining>0)){job->live=0;continue;}
        job->remaining-=dt;
        if(job->remaining<=0){
            const float *m=job->kind==1?world_bone(target,job->bone):world_raw_bone(target,(unsigned)job->bone);
            if(!m){job->live=0;continue;}
            float point[3];for(unsigned k=0;k<3;++k)
                point[k]=job->kind==1?m[k]*job->point[0]+m[4+k]*job->point[1]+m[8+k]*job->point[2]+m[12+k]:m[12+k]+job->point[k];
            /* Source2125425..563c fills unrecorded tail slots only when the
             * last genuine contact emits. All missing slots share0.05s;
             * existing real contacts retain their own bone/point/due time. */
            if(job->kind==1&&i+1==world_helm_count&&world_helm_count<7){
                for(unsigned j=world_helm_count;j<7;++j)if(!world_follow[j].live){
                    world_follow[j]=*job;world_follow[j].emitted=j;world_follow[j].remaining=.05f;
                }
            }
            if(job->tier)world_burst(a,job,point);
            job->live=0;
        }
    }
}
