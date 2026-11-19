#include <assert.h>
#include "../c/world_gauge_gain.h"

int main(void)
{
    unsigned rest=0,total=0;
    for(unsigned i=0;i<10;++i)total+=(unsigned)world_normal_gauge_gain(7,&rest);
    assert(total==77&&rest==0);
    assert(world_normal_gauge_gain(6,&rest)==6&&rest==6);
    assert(world_normal_gauge_gain(6,&rest)==7&&rest==2);
    assert(world_normal_gauge_gain(-15,&rest)==-15&&rest==2);
    assert(world_normal_gauge_gain(0,&rest)==0&&rest==2);
    assert(world_normal_gauge_gain(101,&rest)==101&&rest==2);
    for(unsigned i=0;i<=100;++i){rest=0;assert(world_normal_gauge_gain((int)i,&rest)==(int)(i*11/10));}
    unsigned normal[]={1,4,5,7,8,14,22,25,32,33,34,41,63,64,65,69,70,71};
    for(unsigned i=0;i<sizeof(normal)/sizeof(*normal);++i){
        assert(world_normal_gauge_action(16,normal[i]));
        assert(!world_normal_gauge_action(1,normal[i]));
    }
    unsigned excluded[]={16,17,18,19,23,24,26,27,28,42,47,48,50,76,81,82,240,247,248,250};
    for(unsigned i=0;i<sizeof(excluded)/sizeof(*excluded);++i)assert(!world_normal_gauge_action(16,excluded[i]));
    return 0;
}
