#include "../c/world_ground_vm.h"
#if defined(_WIN32)
__declspec(dllexport)
#endif
int ground_select(unsigned node,uint64_t properties)
{return w_ground_select(node,properties);}
