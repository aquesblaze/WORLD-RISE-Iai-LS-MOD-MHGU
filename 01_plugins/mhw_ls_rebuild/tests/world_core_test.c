#include <assert.h>
#include <stdio.h>
#include "../c/world_core.h"
static WObservation o;
static WState s;
static void reset(void){s=(WState){0};o=(WObservation){.base={.actor=1,.epoch=1,.sample_sequence=1,.native_action=4,.motion=0x569,.simulation_delta=1,.gauge=100},.state=16,.drawn=1,.alive=1,.grounded=1,.rank=3,.resources_ready=1};w_step(&s,&o);}
static WDecision step(float f,unsigned keys){o.base.animation_frame=f;o.base.held=keys;++o.base.sample_sequence;return w_step(&s,&o);}
static void bind(WDecision d){assert(d.kind==W_ENTER);o.base.native_action=w_action(d.move);o.base.motion=0x500+d.slot;o.base.animation_frame=0;o.base.motion_finished=0;step(0,0);}
int main(void){
 /* Press age survives source recovery and a short release; a late request
  * must not add another chord window. Duplicate hooks do not tick twice. */
 WKeys keys={0};MLObservation raw={.actor=1,.epoch=1,.sample_sequence=1,.simulation_delta=1};
 w_keys_tick(&keys,&raw);raw.held=ML_R;++raw.sample_sequence;w_keys_tick(&keys,&raw);
 assert(!(keys.ready&ML_R));float remaining=keys.remaining[2];w_keys_tick(&keys,&raw);
 assert(keys.remaining[2]==remaining);
 for(int i=0;i<8;++i){raw.held=0;++raw.sample_sequence;w_keys_tick(&keys,&raw);}
 assert(keys.ready&ML_R);
 raw.held=ML_R;++raw.sample_sequence;w_keys_tick(&keys,&raw);assert(!(keys.ready&ML_R));
 raw.epoch=2;++raw.sample_sequence;w_keys_tick(&keys,&raw);assert(!keys.waiting&&!keys.ready);
 reset();assert(w_event(170,83)->hit==-1);assert(w_event(170,84)->hit==65);assert(w_event(170,96.99f)->hit==65);assert(w_event(170,97)->hit==-1);
 assert(w_event(307,12)->hit==-1);assert(w_event(307,13)->hit==84);assert(w_event(307,19)->hit==-1);assert(w_event(307,33)->hit==101);assert(w_event(307,37)->hit==-1);
 for(unsigned rank=0;rank<4;++rank)assert(w_event(308+rank,17)->hit==(int)(86+rank));
 assert(step(10,ML_R|ML_B).kind==W_KEEP);
 WDecision d=step(38,ML_R|ML_B);assert(d.kind==W_ENTER&&d.move==W_SHEATHE);bind(d);
 assert(step(65,ML_X).kind==W_KEEP);assert(step(79,0).kind==W_KEEP);d=step(80,0);assert(d.kind==W_ENTER&&d.move==W_SMALL);bind(d);
 assert(step(14,0).regen_seconds==0);o.contact=1;assert(step(15,0).regen_seconds==15);assert(step(16,0).regen_seconds==0);
 reset();d=step(38,ML_R|ML_B);bind(d);step(65,ML_R);d=step(80,0);assert(d.source==311);bind(d);d=w_leave(&s);assert(d.rank_delta==0);assert(w_leave(&s).rank_delta==0);
 reset();bind(step(38,ML_R|ML_B));step(65,ML_R);bind(step(80,0));o.counter=1;d=step(10,0);assert(d.rank_delta==1&&!d.gauge_clear&&!d.gauge_hold);assert(w_leave(&s).rank_delta==0);
 reset();o.state=1;o.base.native_action=0;d=step(0,ML_R|ML_X);assert(d.move==W_THRUST);o.state=16;bind(d);o.contact=1;d=step(85,0);assert(d.move==W_RISE);o.contact=0;bind(d);d=step(46,0);assert(d.move==W_AIR);o.grounded=0;bind(d);step(15,ML_A);d=step(42,0);assert(d.move==W_DOWN&&d.rank_delta==0);bind(d);
 o.grounded=1;d=step(40,0);assert(d.move==W_LAND&&d.rank_delta==0);bind(d);
 int cost=0;for(int i=0;i<35;++i)cost+=step(5+i,0).rank_delta;
 assert(cost==-1);assert(w_leave(&s).rank_delta==0);
 reset();o.state=1;o.base.native_action=0;assert(step(0,ML_ZR|ML_X).kind==W_KEEP);
 reset();bind(step(38,ML_R|ML_B));o.base.epoch=2;step(80,ML_X);assert(s.move==W_NONE);
 /* Native area loads may skip the normal action-request hook. Exit costs
  * follow the same actor once, but must never transfer to a new actor. */
 reset();bind(step(38,ML_R|ML_B));step(65,ML_R);bind(step(80,0));
 o.base.epoch=2;d=step(5,ML_R|ML_X);assert(d.rank_delta==0&&s.move==W_NONE);
 assert(step(6,ML_R|ML_X).rank_delta==0&&s.move==W_NONE);
 reset();bind(step(38,ML_R|ML_B));step(65,ML_R);bind(step(80,0));
 assert(step(37,0).rank_delta==0);o.base.epoch=2;assert(step(38,0).rank_delta==0);
 reset();bind(step(38,ML_R|ML_B));step(65,ML_R);bind(step(80,0));
 o.counter=1;assert(step(1,0).rank_delta==1);o.base.epoch=2;assert(step(5,0).rank_delta==0);
 reset();bind(step(38,ML_R|ML_B));step(65,ML_R);bind(step(80,0));
 o.base.actor=2;o.base.epoch=2;assert(step(5,0).rank_delta==0&&s.move==W_NONE);
 reset();s.move=W_DOWN;s.helm_cost_pending=1;s.rank=3;o.base.epoch=2;
 assert(step(5,0).rank_delta==-1);assert(step(6,0).rank_delta==0);
 reset();bind(step(38,ML_R|ML_B));
 assert(w_event(306,72)->phase==0&&w_event(306,73)->phase==1);
 for(int i=0;i<209;++i)assert(step(80+i,0).kind==W_KEEP);
 d=step(289,0);if(d.kind==W_KEEP)d=step(290,0);
 assert(d.kind==W_ENTER&&d.move==W_SHEATHE_END&&d.source==312);bind(d);
 o.drawn=0;assert(step(1,0).kind==W_KEEP);
 o.base.motion_finished=1;assert(step(w_clip(312)->length,0).kind==W_IDLE);
 /* A delayed observation can both settle a cost/reward and leave the move. */
 reset();bind(step(38,ML_R|ML_B));step(65,ML_R);bind(step(80,0));
 o.base.motion_finished=1;d=step(176,0);assert(d.kind==W_IDLE&&d.rank_delta==0);
 reset();bind(step(38,ML_R|ML_B));step(65,ML_X);bind(step(80,0));
 o.contact=1;o.counter=1;d=step(60,ML_B);assert(d.kind==W_ROLL&&d.regen_seconds==30);
 /* Source native command mappings separate sheathe from R+circle and fades. */
 reset();o.base.motion=0x57f;d=step(50,ML_R|ML_B);assert(d.move==W_SHEATHE);
 reset();bind(step(38,ML_R|ML_A));
 assert(step(25,ML_R|ML_B).kind==W_KEEP);
 d=step(40,0);assert(d.move==W_SHEATHE);
 reset();bind(step(38,ML_R|ML_B));step(65,ML_X);bind(step(80,0));
 assert(step(40,ML_B).kind==W_KEEP);assert(step(59,0).kind==W_KEEP);
 assert(step(60,0).kind==W_ROLL);
 /* Turning waits for the source trigger, then eases over simulation time.
  * A held stick must not reapply the angle every frame of a trigger span. */
 reset();bind(step(38,ML_R|ML_B));o.base.magnitude=100;o.base.input_heading=32768;
 d=step(80,ML_X);assert(d.kind==W_ENTER&&d.heading==0);bind(d);
 unsigned heading=0;step(9,0);assert(!w_rotation(&s,&o,&heading));
 step(10,0);assert(w_rotation(&s,&o,&heading)&&heading>54613&&heading<56000);
 o.base.heading=heading;step(11,0);assert(w_rotation(&s,&o,&heading)&&heading==54613);
 o.base.heading=heading;step(12,0);assert(!w_rotation(&s,&o,&heading));
 reset();bind(step(38,ML_R|ML_B));o.base.magnitude=100;o.base.input_heading=2000;
 d=step(80,ML_X);assert(d.kind==W_ENTER&&d.heading==0);bind(d);
 step(10,0);assert(!w_rotation(&s,&o,&heading));
 for(unsigned fps=30;fps<=120;fps*=2){
  reset();o.base.magnitude=100;o.base.input_heading=16384;
  bind(step(38,ML_R|ML_X));o.base.simulation_delta=60.0f/fps;
  for(unsigned i=0;i<fps/5+1;++i){step((float)i*60/fps,0);if(w_rotation(&s,&o,&heading))o.base.heading=heading;}
  assert(o.base.heading==8192); /* source group1 fixed45deg, not full stick */
 }
 reset();bind(step(38,ML_R|ML_B));step(65,ML_X);bind(step(80,0));
 assert(step(30,ML_X|ML_A).kind==W_KEEP);d=step(50,0);
 assert(d.kind==W_ENTER&&d.move==W_GROUND&&d.source==360);
 reset();bind(step(38,ML_R|ML_B));step(65,ML_X);bind(step(80,0));
 assert(step(30,ML_X).kind==W_KEEP);d=step(50,0);
 assert(d.kind==W_ENTER&&d.move==W_GROUND&&d.source==358);
 /* Native common TIML turn is80deg/s for AIR frames0..20. Its angular
  * distance is independent of simulation rate; it must stop at frame20. */
 for(unsigned fps=30;fps<=120;fps*=2){
  reset();s.move=W_AIR;s.source=172;s.slot=227;o.grounded=0;
  o.base.native_action=243;o.base.motion=0x5e3;o.base.magnitude=100;
  o.base.input_heading=16384;o.base.simulation_delta=60.0f/fps;
  for(unsigned i=0;i<fps/3;++i){step((float)i*60/fps,0);if(w_rotation(&s,&o,&heading))o.base.heading=heading;}
  assert(o.base.heading>=4853&&o.base.heading<=4855);
  step(20,0);assert(!w_rotation(&s,&o,&heading));
 }
 /* Actual World trace: 307 -> dedicated363 ->104 starting42, including
  * an empty gauge. Phase changes must not spend a second Spirit-I cost. */
 for(unsigned gauge=0;gauge<=100;gauge+=100){
  reset();bind(step(38,ML_R|ML_B));step(65,ML_X);bind(step(80,0));
  o.base.gauge=gauge;assert(step(30,ML_R).kind==W_KEEP);d=step(50,0);
  assert(d.kind==W_ENTER&&d.move==W_GROUND&&d.source==363);
  assert(d.gauge_delta==-(int)(gauge?15:0));bind(d);
  assert(step(41,0).kind==W_KEEP);d=step(42,0);
  assert(d.kind==W_MOTION&&d.source==104&&d.start==42&&d.blend==10&&d.gauge_delta==0);
  o.base.motion=0x500+d.slot;assert(step(42,0).kind==W_KEEP);
  assert(s.ground_node==1);
 }
 /* Source Spirit-I face insertion uses118->112 at14, then121->106 at23;
  * Spirit-II face insertion uses107, then124->108 at9. */
 reset();bind(step(38,ML_R|ML_B));step(65,ML_X);bind(step(80,0));
 d=step(50,ML_R);bind(d);d=step(42,0);assert(d.kind==W_MOTION);
 o.base.motion=0x500+d.slot;step(42,0);
 d=step(56,ML_A);assert(d.kind==W_ENTER&&d.source==118&&s.ground_node==23);bind(d);
 d=step(14,0);assert(d.kind==W_MOTION&&d.source==112&&d.start==14);
 o.base.motion=0x500+d.slot;step(14,0);
 d=step(50,ML_R);assert(d.kind==W_ENTER&&d.source==121&&s.ground_node==12);bind(d);
 d=step(22,0);assert(d.kind==W_MOTION&&d.source==106&&d.start==23);
 o.base.motion=0x500+d.slot;step(23,0);
 d=step(44,ML_A);assert(d.kind==W_ENTER&&d.source==107&&s.ground_node==38);bind(d);
 d=step(60,ML_R);assert(d.kind==W_ENTER&&d.source==124&&s.ground_node==2);bind(d);
 d=step(20,0);assert(d.kind==W_MOTION&&d.source==108&&d.start==9);
 reset();bind(step(38,ML_R|ML_A));o.counter=1;o.contact=1;
 assert(step(70,ML_R).kind==W_KEEP);d=step(90,0);
 assert(d.kind==W_NATIVE&&d.native_action==30);
 /* Tests enter the landing state directly; runtime coverage comes from the
  * full thrust/jump/contact fixture, not this isolated decision check. */
 reset();s.move=W_LAND;s.source=174;s.slot=229;s.rank=3;
 o.base.native_action=245;o.base.motion=0x5e5;
 assert(step(5,ML_R|ML_B).kind==W_KEEP);d=step(15,0);assert(d.move==W_SHEATHE);
 reset();s.move=W_LAND;s.source=174;s.slot=229;s.rank=3;
 o.base.native_action=245;o.base.motion=0x5e5;
 assert(step(60,ML_R|ML_A).kind==W_KEEP);d=step(80,0);assert(d.move==W_FORESIGHT);
 /* Float channels interpolate in the source runtime; integer flags do not.
  * Mid-curve values distinguish linear evaluation from keyframe stepping. */
 assert(w_float(308,W_FLOAT_SPEED,11.5f)==1.25f);
 assert(w_float(311,W_FLOAT_SPEED,11.5f)==1.5f);
 assert(w_float(311,W_FLOAT_SPEED,31.5f)==1.5f);
 assert(w_float(173,W_FLOAT_SPEED,12.5f)==1.25f);
 assert(w_float(172,W_FLOAT_TURN,19.9f)==80);
 assert(w_float(172,W_FLOAT_TURN,20)==0);
 assert(w_float(109,W_FLOAT_TURN,32)==50);
 assert(w_float(311,W_FLOAT_CAMERA,18.5f)>.5499f&&w_float(311,W_FLOAT_CAMERA,18.5f)<.5501f);
 assert(w_float(170,W_FLOAT_SPEED,100)==1);
 /* Buffered loop uses source execute stages, not GU's missing return link. */
 reset();assert(step(5,ML_X).kind==W_KEEP&&s.queued!=0);
 for(int i=6;i<38;++i)assert(step((float)i,0).kind==W_KEEP);
 d=step(38,0);assert(d.kind==W_NATIVE&&d.native_action==25);
 reset();o.base.native_action=25;o.base.motion=0x56b;
 step(22,ML_A);for(int i=23;i<42;++i)assert(step((float)i,0).kind==W_KEEP);
 d=step(42,0);assert(d.kind==W_NATIVE&&d.native_action==4);
 /* A raw R tap must not depend on GU eventually issuing a native request.
  * Its wait elapses during source recovery, and a later chord wins. */
 reset();assert(step(5,ML_R).kind==W_KEEP&&s.queued==0x300);
 for(int i=6;i<38;++i)assert(step((float)i,0).kind==W_KEEP);
 assert(step(38,0).kind==W_NATIVE_R);
 reset();o.base.native_action=0;o.base.motion=0x565;
 assert(step(5,ML_R).kind==W_KEEP&&s.queued==0x300);
 for(int i=6;i<70;++i)assert(step((float)i,0).kind==W_KEEP);
 assert(step(70,0).kind==W_NATIVE_R);
 reset();assert(step(20,ML_R).kind==W_KEEP&&s.queued==0x300);
 for(int i=21;i<38;++i)assert(step((float)i,0).kind==W_KEEP);
 d=step(38,0);assert(d.kind==W_NATIVE_R);
 reset();o.base.native_action=25;o.base.motion=0x56b;
 step(24,ML_R);for(int i=25;i<42;++i)assert(step((float)i,0).kind==W_KEEP);
 d=step(42,0);assert(d.kind==W_NATIVE_R);
 reset();step(20,ML_R);step(22,ML_R|ML_A);
 d=step(38,0);assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
 reset();step(20,ML_R);o.state=4;step(22,0);assert(!s.queued);
 o.state=16;assert(step(38,0).kind==W_KEEP);
 reset();o.base.native_action=25;o.base.motion=0x56b;
 step(60,ML_A);d=step(61,ML_A|ML_R);assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
 reset();s.consumed=ML_A;d=step(60,ML_A|ML_R);
 assert(d.kind==W_ENTER&&d.move==W_FORESIGHT);
 reset();o.base.native_action=25;o.base.motion=0x56b;
 step(60,ML_A);d=step(61,ML_A|ML_X);assert(d.kind==W_KEEP&&s.queued==0);
 /* Successful jump completes without an attack input; no early down. */
 reset();s.move=W_AIR;s.source=172;s.slot=227;s.rank=3;
 o.grounded=0;o.base.native_action=243;o.base.motion=0x5e3;
 assert(step(20,0).kind==W_KEEP);assert(step(41,0).kind==W_KEEP);
 d=step(42,0);assert(d.kind==W_ENTER&&d.move==W_DOWN);
 reset();s.move=W_AIR;s.source=172;s.slot=227;s.rank=3;
 o.grounded=0;o.base.native_action=243;o.base.motion=0x5e3;
 d=step(50,0);assert(d.move==W_DOWN);
 for(unsigned rank=1;rank<=3;++rank){
  reset();s.move=W_AIR;s.source=172;s.slot=227;s.rank=rank;
  o.grounded=0;o.rank=rank;o.base.native_action=243;o.base.motion=0x5e3;
  assert(step(41,0).kind==W_KEEP);assert(step(42,0).move==W_DOWN);
 }
 reset();o.state=1;o.base.native_action=0;o.rank=0;
 d=step(0,ML_R|ML_X);o.state=16;bind(d);o.contact=1;
 assert(step(85,0).kind==W_KEEP&&s.move==W_THRUST);
 puts("PASS: source combat, typed interpolation, buffered alternating loop and chord priority");
}
