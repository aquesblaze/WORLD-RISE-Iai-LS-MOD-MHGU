/* Source-owned input kernel. Legacy manual queues below w_step's VM branch
 * remain available only for historical development-build comparisons. */
typedef struct {WState *s;const WObservation *o;uint64_t known,values;} WGroundQuery;
static unsigned world_property(WGroundQuery *q,unsigned property)
{
    uint64_t bit=(uint64_t)1<<property;
    if(q->known&bit)return (q->values&bit)!=0;
    q->known|=bit;unsigned value=0;WState *s=q->s;const WObservation *o=q->o;
    static const unsigned commands[]={39,53,60,25,46,51,52,32};
    if(property<8)value=w_controls_query(&s->controls,commands[property],1,0);
    else switch(property){
    case 8:value=o->base.motion_finished;break;
    case 9:value=1;break; /* contact is validated by the native monster registry */
    case 10:value=o->rank>=1;break;
    case 11:value=w_controls_query(&s->controls,24,1,0);break;
    case 12:value=s->hit_success;break;
    case 13:value=o->grounded;break;
    case 14:value=1;break; /* source Finish gauge threshold is0; colour is separate */
    case 15:value=o->base.gauge>=25;break;
    case 16:value=o->base.gauge>=15;break;
    case 17:value=o->base.gauge>=20;break;
    case 18:value=s->counter_success&&s->hit_success;break;
    }
    if(value)q->values|=bit;
    return value;
}
/* These native-only states have no w_guild_source() slot, so the unowned-state
 * guard below would discard every input. Handle their ZR chords here instead.
 * Adept Cut-In is deliberately NOT here: ZR after Cut-In must remain the plain
 * native Reckoning, with no World move stealing its animation. */
static unsigned w_valor_spirit3(const WObservation *o)
{
    /* Wait for the observed 0x5B9 follow-up pose. The earlier 0x5F0/0x5C2/
     * 0x5BF frames are the Spirit III cut-in; a fast ZR there must not replace
     * that animation with Reckoning. */
    return o->grounded&&o->state==16&&o->base.motion==0x5B9&&
        (o->base.native_action==W_VALOR_SPIRIT_III||
         o->base.native_action==W_VALOR_SPIRIT_III_DASH);
}
static unsigned w_native_reckoning(const WObservation *o)
{
    return o->grounded&&o->state==16&&
        ((o->style==3&&o->base.native_action==0x43)||
         o->base.native_action==W_VALOR_RECKONING)&&
        (o->base.motion==0x5B9||o->base.motion==0x5BA);
}
static int world_query_node(WGroundQuery *q,unsigned node)
{
    const WGroundNode *n=w_ground_node(node);if(!n)return -1;
    for(unsigned i=0;i<n->count;++i){
        const WGroundEdge *edge=world_ground_edges+n->offset+i;
        unsigned stack[32],top=0;
        for(unsigned j=0;j<edge->count;++j){
            WGroundTerm term=world_ground_terms[edge->offset+j];
            if(term.op<=1){if(top>=32)return -1;stack[top++]=term.op?world_property(q,term.value):term.value;}
            else{
                if(term.value>top)return -1;
                unsigned result=term.op==2;
                for(unsigned k=0;k<term.value;++k){unsigned v=stack[--top];if(term.op==2)result&=v;else result|=v;}
                stack[top++]=result;
            }
        }
        if(top==1&&stack[0])return (int)edge->target;
    }
    return -1;
}
static void world_input_permission(unsigned source,const WEvent *event,uint32_t *permission)
{
    for(unsigned i=0;i<8;++i)permission[i]=event&&i<7?event->input[i]:0;
    permission[2]=(permission[2]&~(3u<<22))|(w_foresight_stage(source,event)<<22);
}
static unsigned world_source_node(unsigned source)
{
    switch(source){
    case 1:return 0;case 101:return 11;case 102:return 10;case 103:return 7;
    case 104:return 1;case 105:return 4;case 106:return 12;case 107:return 3;
    case 108:return 2;case 109:return 5;case 110:return 6;case 112:return 23;
    case 127:return 9;case 128:return 8;case 140:return 28;case 170:return 45;
    case 174:return 57;case 307:return 64;
    case 308:case 309:case 310:case 311:return 65;
    default:return 0xffff;
    }
}
/* Only the post-small-Iai spirit opener has no GU counterpart. Resolve the
 * other World edges to stock commands so their follow-up context, hit rows,
 * gauge accounting and presentation all belong to the native handler. */
static WDecision world_route(WState *s,const WObservation *o,unsigned edge)
{
    const WGroundNode *n=w_ground_node(edge);
    if(!n)return (WDecision){0};
    int dest=n->kind==2?w_ground_select(edge,0):(int)edge;
    if(dest==28||dest==45||dest==61||(s->move==W_SMALL&&edge==82))
        return ground_enter(s,o,edge,0);
    if(!s->move){
        /* The two ordinary combo edges use GU's thrust and combo upper.
         * Spirit insertions share these poses but have different actions. */
        unsigned from=o->base.native_action, motion=o->base.motion;
        if(edge==1&&w_guild_spirit_opener(from,motion,o->previous_weapon_action))
            return (WDecision){.kind=W_NATIVE,.native_action=o->base.gauge>=15?16:17,.heading=o->base.heading};
        unsigned upper=(from==4&&motion==0x569&&edge==31)||(from==22&&(motion==0x569||motion==0x570)&&edge==3);
        unsigned thrust=(from==25||from==41)&&motion==0x56b&&edge==4;
        if((from==7||from==25||from==41)&&motion==0x56b&&edge==39)
            return (WDecision){.kind=W_NATIVE,.native_action=5,.heading=o->base.heading};
        if(upper||thrust)
            return (WDecision){.kind=W_NATIVE,.native_action=upper?25:4,.heading=o->base.heading};
        return (WDecision){0};
    }

    unsigned action;
    switch(dest){
    case 1:action=o->base.gauge>=15?16:17;break;
    case 2:action=26;break;
    case 3:case 38:action=25;break;
    case 4:action=4;break;
    case 5:action=30;break;
    case 7:action=8;break;
    /* Measured against camera-centered walking: GU 28 travels left, 29 right. */
    case 8:action=28;break;
    case 9:action=29;break;
    case 10:action=5;break;
    case 11:action=0;break;
    case 12:action=23;break;
    case 23:action=22;break;
    default:return (WDecision){0};
    }
    WDecision d=w_leave(s);d.kind=W_NATIVE;d.native_action=action;d.heading=o->base.heading;
    return d;
}
/* Preserve a two-button tap across GU's native request hook and the
 * partner's delayed confirmation. Both physical buttons must overlap on
 * the same stock attack in a valid source window. */
static void world_guild_chords(WState *s,unsigned held,const uint32_t *permission)
{
    WControls *c=&s->controls;
    static const unsigned ids[]={53,60,24},partners[]={ML_X,ML_A,ML_B},buttons[]={0,1,3};
    for(unsigned i=0;i<3;++i){
        unsigned id=ids[i],mask=ML_R|partners[i];
        int bit=world_command_bits[id];
        unsigned stage=w_permission_bit(permission,bit-1)|(w_permission_bit(permission,bit)<<1);
        if(!stage||(held&~mask)){
            if(s->gu_chord_wait==id)s->gu_chord_wait=0;
            continue;
        }
        if(held==mask&&(w_command_has(c->commands.raw,id)||w_command_has(c->commands.observed,id)))
            s->gu_chord_wait=id;
        if(s->gu_chord_wait!=id)continue;
        if(c->buttons[buttons[i]].pressed){
            w_command_collect(&c->commands,id,stage,0,0,0,0);
            w_command_promote(&c->commands,id);
        }
        if(!c->buttons[buttons[i]].waiting)s->gu_chord_wait=0;
    }
}
static WDecision world_command_step(WState *s,const WObservation *o,unsigned source,const WEvent *event)
{
    const MLObservation *b=&o->base;
    /* The landing follow-up needs a ZR edge that is separate from the ZR used
     * to start the Helm dive. Track how long the button has been released and
     * keep this sample's armed state before consuming the new press. */
    unsigned land_armed=s->land_r_clear>=2;
    if(b->held&ML_R)s->land_r_clear=0;
    else if(s->land_r_clear<3)++s->land_r_clear;
    unsigned idle=!s->move&&(o->state==1||o->state==2)&&b->native_action<=5&&o->grounded;
    unsigned air_spirit=!s->move&&o->state==16&&
        ((((b->native_action>=42&&b->native_action<=47)||(b->native_action>=76&&b->native_action<=81))&&
          (b->motion==0x598||b->motion==0x568))||
         (b->native_action>=72&&b->native_action<=75&&
          ((b->motion>=0x599&&b->motion<=0x59c)||b->motion==0x568)));
    if(s->air_sheathe_sample!=b->sample_sequence){
        s->air_sheathe_sample=b->sample_sequence;
        if(!air_spirit)s->air_sheathe_buffer=0;
        else{
            if(b->simulation_delta>0&&b->simulation_delta<30)
                s->air_sheathe_buffer-=b->simulation_delta/60;
            if(!o->grounded&&b->held==(ML_R|ML_B)&&s->air_sheathe_held!=(ML_R|ML_B))
                s->air_sheathe_buffer=.35f;
        }
        s->air_sheathe_held=b->held;
    }
    /* Valor Spirit III and both native Reckonings have no World source and no
     * TIML permission bits. Accept their ZR chords before the unowned-state
     * guard discards them. The ZR held through the move that started the native
     * state must not be read as a fresh follow-up. */
    unsigned native_armed=s->native_r_clear>=2;
    /* Only a solo ZR resets the arming timer; a later ZR+B/A/X chord stays
     * armed for its whole hold. */
    if((b->held&ML_R)&&!(b->held&(ML_B|ML_A|ML_X)))s->native_r_clear=0;
    else if(!(b->held&ML_R)&&s->native_r_clear<3)++s->native_r_clear;
    unsigned valor_spirit3=!s->move&&w_valor_spirit3(o);
    unsigned native_reckoning=!s->move&&w_native_reckoning(o);
    if(valor_spirit3||native_reckoning){
        unsigned other=b->held&(ML_B|ML_A|ML_X);
        unsigned choice=0;
        if(native_armed&&b->animation_frame>=4&&(b->held&ML_R)&&
           !(b->held&(ML_Y|ML_ZR))){
            if(other==ML_B)choice=W_SHEATHE;
            else if(other==ML_A)choice=W_FORESIGHT;
            else if(other==ML_X)choice=W_THRUST;
        }
        /* Let the chord mature like the controls VM does, so a button pressed
         * as part of the native animation is not stolen instantly. */
        if(choice&&choice==s->native_chord){
            if(++s->native_chord_wait>=4){
                unsigned mask=choice==W_SHEATHE?ML_R|ML_B:
                    choice==W_FORESIGHT?ML_R|ML_A:ML_R|ML_X;
                return enter(s,o,choice,mask);
            }
        }else{s->native_chord=choice;s->native_chord_wait=0;}
        /* A fresh solo ZR on Valor Spirit III requests native Reckoning. Solo
         * ZR on Reckoning itself stays native and is left to the game. */
        if(!choice&&valor_spirit3&&native_armed&&b->animation_frame>=4&&
           (b->held&ML_R)&&!(b->held&(ML_B|ML_A|ML_X|ML_Y|ML_ZR))){
            WDecision d=w_leave(s);d.kind=W_NATIVE;
            d.native_action=W_VALOR_RECKONING;
            d.heading=b->magnitude>=50?b->input_heading:b->heading;
            return d;
        }
        s->controls=(WControls){0};s->gu_chord_wait=0;s->adept_round_pending=0;
        return (WDecision){0};
    }
    /* 循环纳刀按需求移除（纳刀原则参照「还原世界 v1.1」）：
     * 居合/纳刀结束后不再用 R+B 直接接纳刀，特殊纳刀只走源 TIML 的正常窗口，
     * 空中气刃落地那条保留；纳刀内仍需新按 R 才转大居合。 */
    if(!s->move){
        source=w_guild_source(o->state,b->native_action,b->motion);
        if(!source||!o->grounded){s->controls=(WControls){0};s->gu_chord_wait=0;return (WDecision){0};}
        if(air_spirit&&(b->motion==0x568||b->motion==0x59a||b->motion==0x59c)&&b->animation_frame>=10&&b->animation_frame<60&&
           s->air_sheathe_buffer>0&&!(b->held&(ML_X|ML_A|ML_Y|ML_ZR))){
            s->air_sheathe_buffer=0;
            return enter(s,o,W_SHEATHE,ML_R|ML_B);
        }
        event=w_event(source,idle?0:b->animation_frame);
    }
    uint32_t permission[8];world_input_permission(source,event,permission);
    const float direction[4]={(float)b->input_heading,0,0,0};
    int delta=ml_heading_delta(b->input_heading,b->heading);
    /* Recorded GU input: positive quarter-turn is the hunter's left.
     * Original World motion128 is left,127 is right; legacy preview labels
     * had these reversed and must not define this command binding. */
    unsigned facing=delta>=8192&&delta<=24576?3:
        delta<=-8192&&delta>=-24576?1:delta>24576||delta< -24576?2:0;
    if(s->input_motion!=b->motion){w_controls_bind(&s->controls);s->input_motion=b->motion;s->gu_chord_wait=0;}
    /* A short R+B tap can end before the two Foresight cancel windows.
     * Latch only a fresh chord; the source timeline still decides entry. */
    unsigned sheath_edge=b->held==(ML_R|ML_B)&&
        !(s->controls.buttons[2].raw&&s->controls.buttons[3].raw);
    w_controls_tick(&s->controls,b->actor,b->epoch,b->sample_sequence,b->held,
        b->simulation_delta/60,permission,direction,b->magnitude>=50,facing,facing);
    if(!s->move)world_guild_chords(s,b->held,permission);
    else s->gu_chord_wait=0;
    float frame=b->animation_frame;
    unsigned fresh=b->held&~s->consumed;
    if(s->main_source&&(b->motion_finished||frame>=w_clip(source)->length-1)){
        unsigned main=s->main_source;s->main_source=0;
        return ground_motion(s,main,source,frame,W_MOTION);
    }
    if(s->move==W_SHEATHE){
        if(event&&event->phase==1&&b->simulation_delta>0&&b->simulation_delta<30)
            s->hold_seconds+=b->simulation_delta/60;
        /* The chord that opened the stance has already spent R; keeping it
         * held must not spend the stance on a big Iai by itself. */
        /* Source 306 has no roll permission bit. Wait until phase1 (F73), when
         * the sheathing root motion has placed the hunter in the Iai stance;
         * pressing B earlier must not cut off the sheath animation. */
        if((fresh&ML_B)&&!(fresh&ML_R)&&s->controls.buttons[3].edge&&
           event&&event->phase==1){
            WDecision d=w_leave(s);d.kind=W_ROLL;
            d.heading=b->magnitude>=50?b->input_heading:b->heading;
            return d;
        }
        if((fresh&ML_R)&&w_controls_query(&s->controls,39,1,0))return enter(s,o,W_BIG,ML_R);
        if(w_controls_query(&s->controls,25,1,0))return enter(s,o,W_SMALL,ML_X);
        if(s->hold_seconds>=3.5f)return enter(s,o,W_SHEATHE_END,0);
        return (WDecision){0};
    }
    /* Rise-style follow-ups from the Iai Spirit Slash itself. Node65 has no
     * ZR+B or ZR+A edge, so the raw chord owns these transitions. ZR may still
     * be held from entering ISS, so only the partner needs a fresh edge. */
    if(s->move==W_BIG){
        /* Debounce ZR vs B: the held state must stay stable for 2 samples
         * before a B press can be read as ZR+B or as a solo roll. This removes
         * the race where releasing ZR one frame early flips the follow-up. */
        if(b->held&ML_R){if(s->iss_r_held<3)++s->iss_r_held;s->iss_r_clear=0;}
        else {if(s->iss_r_clear<3)++s->iss_r_clear;s->iss_r_held=0;}
        if(b->held&ML_B){if(s->iss_b_held<3)++s->iss_b_held;}else s->iss_b_held=0;
        /* All ISS follow-ups share the same F70 gate. A quick press during the
         * counter stays latched so it survives until the gate opens.
         * bit0=solo ZR (Spirit III), bit1=ZR+A (Foresight),
         * bit2=ZR+B (Special Sheathe), bit3=solo B (roll). */
        if((b->held&ML_R)&&s->controls.buttons[2].edge&&
           !(b->held&(ML_X|ML_A|ML_B|ML_Y|ML_ZR))){
            s->follow_ready|=1u;
            s->iss_zr_frame=(unsigned)frame;
        }
        if((b->held&(ML_R|ML_A))==(ML_R|ML_A)&&
           !(b->held&(ML_X|ML_B|ML_Y|ML_ZR))&&
           (s->controls.buttons[1].edge||s->controls.buttons[2].edge))
            s->follow_ready|=2u;
        if(s->iss_r_held>=2&&s->iss_b_held>=2&&(fresh&ML_B)&&
           !(b->held&(ML_X|ML_A|ML_Y|ML_ZR)))
            s->follow_ready|=4u;
        if(s->iss_r_clear>=2&&s->iss_b_held>=2&&(fresh&ML_B)&&
           !(b->held&(ML_R|ML_X|ML_A|ML_Y|ML_ZR)))
            s->follow_ready|=8u;
        /* Source 311 keeps moving well past F40. Hold every follow-up until
         * F70 so the ISS recovery is not cut off. Chord priority is kept:
         * ZR+B, then solo B roll, ZR+A, and finally the Spirit III finisher.
         * The solo moves wait W_ISS_CHORD_GRACE extra frames: pressing ZR+B
         * a few frames apart must still become the sheathe, not Spirit III. */
        if(frame>=70){
            if(s->counter_success&&(s->follow_ready&4u)&&
               !(b->held&(ML_X|ML_A|ML_Y)))
                return enter(s,o,W_SHEATHE,ML_R|ML_B);
            if(s->counter_success&&(s->follow_ready&8u)&&
               frame>=70+W_ISS_CHORD_GRACE&&
               !(b->held&(ML_R|ML_X|ML_A|ML_Y))){
                WDecision d=w_leave(s);d.kind=W_ROLL;
                d.heading=b->magnitude>=50?b->input_heading:b->heading;return d;
            }
            if(s->counter_success&&(s->follow_ready&2u)&&
               !(b->held&(ML_X|ML_B|ML_Y)))
                return enter(s,o,W_FORESIGHT,ML_R|ML_A);
            /* Helper 36 carries the source-backed 124 -> 108 Spirit-III prep;
             * node2's own ZR edge then gives Roundslash at its real F110 window.
             * The grace is measured from the solo ZR press as well as the F70
             * gate, so a partner that arrives a few frames after a late ZR
             * still wins the chord. */
            unsigned solo_ready=70+W_ISS_CHORD_GRACE;
            if(s->iss_zr_frame+W_ISS_CHORD_GRACE>solo_ready)
                solo_ready=s->iss_zr_frame+W_ISS_CHORD_GRACE;
            if((s->follow_ready&1u)&&s->counter_success&&o->base.gauge>=20&&
               frame>=solo_ready&&
               !(b->held&(ML_B|ML_A|ML_X|ML_Y|ML_ZR))){
                /* Native Valor Spirit Slash III for every style. With no analog
                 * direction action0x74 performs the planted cut; with a
                 * directional analog input action0x87 performs the traveling
                 * cut. Both leave the World move so the next ZR is native
                 * Reckoning. */
                WDecision d=w_leave(s);d.kind=W_NATIVE;
                d.native_action=b->magnitude>=50?W_VALOR_SPIRIT_III_DASH:
                    W_VALOR_SPIRIT_III;
                d.heading=b->magnitude>=50?b->input_heading:b->heading;
                return d;
            }
        }
    }
    if(s->move==W_THRUST&&s->hit_success&&o->rank>=1)return enter(s,o,W_RISE,0);
    if(s->move==W_RISE){
        /* 起跳段不触发下劈：等真正腾空（W_AIR）才允许。
         * 只在这里记录“R 已松开”，腾空后按 R 才生效。 */
        if(!(b->held&ML_R))s->helm_air_armed=1;
        /* The last displayed pose in the two original jump starts is F45.32.
         * GU binds the successor on the next engine update. */
        if(b->motion_finished||frame>=w_clip(source)->length-2)return enter(s,o,W_AIR,0);
        return (WDecision){0};
    }
    if(s->move==W_AIR){
        if(o->grounded&&frame>0)return enter(s,o,W_LAND,0);
        /* 腾空后才允许：起跳段（W_RISE）不触发，这里再按 R 直接下劈。 */
        if(!(b->held&ML_R))s->helm_air_armed=1;
        if(s->helm_air_armed&&(b->held&ML_R)&&frame>=1){
            s->helm_air_armed=0;return enter(s,o,W_DOWN,ML_R);
        }
        WGroundQuery air={.s=s,.o=o};
        int next=world_query_node(&air,56);
        if(next==58)return enter(s,o,W_DOWN,ML_R|ML_X|ML_A);
        /* Keep the established hands-off Helm variant as a separate fallback. */
        if((event&&((event->input[0]>>30)&3)==3)||b->motion_finished||frame>=w_clip(source)->length-1)
            return enter(s,o,W_DOWN,0);
        return (WDecision){0};
    }
    if(s->move==W_DOWN){if(o->grounded&&frame>0)return enter(s,o,W_LAND,0);return (WDecision){0};}
    if(s->move==W_LAND){
        /* World/Outlanders-style Sakura Slash I follow-up. After the Spirit
         * Helm Breaker lands, a fresh solo ZR press starts the native Long
         * Sword Hunter Art directly: no equipped art slot and no art gauge are
         * required, because the adapter reproduces GU's own action51 request.
         * The ZR used for the dive was consumed on W_DOWN entry, and
         * land_r_clear additionally requires a release, so holding the dive
         * button cannot fire the follow-up. A/B/X/Y keep their existing landing
         * chords (special sheathe and Foresight).
         * The art dispatch below is gated by W_SAKURA_LANDING_ENABLED (0 by
         * default): the follow-up is currently disabled but all of its state
         * tracking stays compiled, so setting the toggle to 1 restores it.
         * Wilds-style gating: the art belongs to the level the Helm Breaker
         * leaves behind. The landing cost is either still pending (0.5 s) or
         * already paid, so compare against the rank after it: only yellow (2)
         * starts the art. A red start pays Helm first and then follows up,
         * red -> yellow -> white; lower levels are refused instead of being
         * drained to nothing. */
        /* Chord grace: a solo landing ZR waits W_LAND_CHORD_GRACE frames
         * before it becomes Sakura Slash. If B or A arrives inside that
         * window it completes ZR+B (special sheathe) or ZR+A (Foresight)
         * instead, so a slightly late partner is no longer read as a solo
         * press. The Helm dive's own ZR is still filtered by land_r_clear. */
        unsigned fire=0;
        if(s->land_zr_wait){
            if((b->held&(ML_R|ML_B))==(ML_R|ML_B)&&
               !(b->held&(ML_X|ML_A|ML_Y|ML_ZR))){
                s->land_zr_wait=0;
                return enter(s,o,W_SHEATHE,ML_R|ML_B);
            }
            if((b->held&(ML_R|ML_A))==(ML_R|ML_A)&&
               !(b->held&(ML_X|ML_B|ML_Y|ML_ZR))){
                s->land_zr_wait=0;
                return enter(s,o,W_FORESIGHT,ML_R|ML_A);
            }
            if(--s->land_zr_wait)return (WDecision){0};
            fire=1;
        }else if(land_armed&&(fresh&ML_R)){
            /* The partner may also be held first (B/A then ZR); the same
             * direct chords apply, so either order behaves like ZR+B/ZR+A. */
            if((b->held&ML_B)&&!(b->held&(ML_X|ML_A|ML_Y|ML_ZR))){
                s->land_zr_wait=0;
                return enter(s,o,W_SHEATHE,ML_R|ML_B);
            }
            if((b->held&ML_A)&&!(b->held&(ML_X|ML_B|ML_Y|ML_ZR))){
                s->land_zr_wait=0;
                return enter(s,o,W_FORESIGHT,ML_R|ML_A);
            }
            if(!(b->held&(ML_X|ML_A|ML_B|ML_Y|ML_ZR))){
                s->land_zr_wait=W_LAND_CHORD_GRACE;
                return (WDecision){0};
            }
        }
        if(fire&&!(b->held&(ML_X|ML_A|ML_B|ML_Y|ML_ZR))){
#if W_SAKURA_LANDING_ENABLED
            /* The Helm landing cost may still be queued for 0.5 s; judge the
             * level the player will be left with, not the one still shown. */
            int rank_after=(int)o->rank;
            if(s->helm_cost_pending&&rank_after>0)--rank_after;
            if(rank_after!=2)
                s->sakura_denied=(unsigned)(rank_after<0?0:rank_after)+1;
            else{
                WDecision d=w_leave(s);
                d.kind=W_NATIVE;d.native_action=W_ART_SAKURA_SLASH;
                d.native_flags=W_ART_SAKURA_FLAGS;d.heading=b->heading;
                /* The native art normally raises the spirit level. Track the
                 * chain so w_step can turn that into a one-level cost instead.
                 * w_leave() may already have paid the Helm landing cost in
                 * this same decision, so the baseline is the rank after it. */
                int base=(int)o->rank+d.rank_delta;
                s->sakura_stage=1;s->sakura_rank=base<0?0:(unsigned)base;
                s->sakura_frames=0;s->sakura_grace=0;s->sakura_paid=0;
                return d;
            }
#else
            /* Temporarily disabled. The solo ZR still goes through the chord
             * grace above, so a late B/A keeps working; it simply has no art
             * follow-up while the toggle is 0. */
#endif
        }
    }
    if(s->move==W_SHEATHE_END){
        if(b->motion_finished||frame>=w_clip(source)->length-1){WDecision d=w_leave(s);d.kind=W_IDLE;return d;}
        return (WDecision){0};
    }
    if(!s->move&&(source==149||source==154)){
        if(w_controls_query(&s->controls,24,1,0))return enter(s,o,W_SHEATHE,ML_R|ML_B);
        if(w_controls_query(&s->controls,60,1,0))
            return enter(s,o,W_FORESIGHT,ML_R|ML_A);
        return (WDecision){0};
    }
    unsigned node=s->move==W_GROUND?s->ground_node:world_source_node(source);
    if(node==0xffff||!o->grounded)return (WDecision){0};
    if(s->move==W_FORESIGHT){
        if(sheath_edge&&frame>=13&&frame<90){
            s->queued=W_SHEATHE;s->queue_until=frame<47?47:160;
        }
        if(s->queued==W_SHEATHE){
            if(frame>=s->queue_until||(b->held&(ML_X|ML_A|ML_Y|ML_ZR)))s->queued=0;
            else if(input_stage(event,WI_SHEATHE)==3)return ground_enter(s,o,61,ML_R|ML_B);
        }
    }
    WGroundQuery query={.s=s,.o=o};
    /* Shared weapon-ground special-sheathe transition, before local links.
     * Its own TIML command permission still owns both buffering and entry. */
    if(node!=0&&node!=64&&node!=65&&world_property(&query,11))
        return ground_enter(s,o,61,ML_R|ML_B);
    /* Adept's Spirit III (source108) never opens GU's ZR TIML window, so the
     * source graph's node2 -> node5 Roundslash edge cannot fire at its normal
     * frame. Style3 alone buffers a freshly pressed ZR with node5's own gauge
     * gate and submits its action30 after W_ADEPT_ROUNDSLASH_FRAME, letting the
     * Spirit III ground slash finish. world_route() deliberately declines node5
     * when no plugin move is bound (Guild owns it natively), so the native-Adept
     * case must not go through that helper. Firing too early cut straight into
     * Roundslash on the first ZR of the ZR-ZR-ZR-ZR chain; every other style
     * keeps the TIML path. */
    if(node==2&&source==108&&o->style==3&&!s->main_source&&
       o->base.gauge>=25){
        if(b->held&(ML_B|ML_A|ML_X|ML_Y|ML_ZR))s->adept_round_pending=0;
        else{
            if((fresh&ML_R)&&s->controls.buttons[2].edge)s->adept_round_pending=1;
            if(s->adept_round_pending&&frame>=W_ADEPT_ROUNDSLASH_FRAME){
                WDecision d=w_leave(s);d.kind=W_NATIVE;d.native_action=30;
                d.heading=o->base.heading;return d;
            }
        }
    }else s->adept_round_pending=0;
    int next=world_query_node(&query,node);
    if(next>=0){
        WDecision d=world_route(s,o,(unsigned)next);
        if(d.kind!=W_KEEP)return d;
    }
    if(s->move&&event&&((event->input[0]>>8)&3)==3&&
       w_controls_query(&s->controls,17,0,0)){
        WDecision d=w_leave(s);d.kind=W_ROLL;
        d.heading=b->magnitude>=50?b->input_heading:b->heading;return d;
    }
    if(s->move&&(b->motion_finished||frame>=w_clip(source)->length-1)){
        WDecision d=w_leave(s);d.kind=W_IDLE;return d;
    }
    return (WDecision){0};
}
