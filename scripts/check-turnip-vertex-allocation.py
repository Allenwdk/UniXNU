#!/usr/bin/env python3
"""Run the selected Mesa vertex-binding body with failing and successful CS peers.

Uses the actual function and draw-state helper, not a duplicate implementation.
The peer fails before allocating a command map, as the Darwin BO path did.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, default=Path(__file__).resolve().parents[1] / '.cache/mesa-work')
args = parser.parse_args()
source = args.source
text = (source / 'src/freedreno/vulkan/tu_cmd_buffer.cc').read_text()
start = text.index('tu_CmdBindVertexBuffers2(')
end = text.index('\ntemplate <chip CHIP>', start)
function = text[start:end]
header = (source / 'src/freedreno/vulkan/tu_cs.h').read_text()
start = header.index('static inline struct tu_draw_state\ntu_cs_draw_state(')
end = header.index('\nvoid\ntu_cs_reset', start)
helper = header[start:end]
peer = r'''
#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
using VkResult=int;
constexpr int VK_SUCCESS=0;
using VkDeviceSize=uint64_t;
constexpr uint64_t VK_WHOLE_SIZE=~uint64_t(0);
struct tu_buffer {struct {uint64_t address, size;} vk;};
using VkBuffer=tu_buffer *;
constexpr VkBuffer VK_NULL_HANDLE=nullptr;
struct tu_draw_state {uint64_t iova; uint32_t size; bool writeable;};
struct tu_cs {uint32_t *cur=nullptr; void *device=nullptr; bool writeable=false;};
struct tu_cs_memory {uint32_t *map; uint64_t iova; bool writeable;};
struct tu_cmd_buffer {
 struct {int record_result=0;} vk;
 struct {unsigned max_vbs_bound=0; tu_draw_state vertex_buffers{};
 struct {uint64_t base; uint32_t size;} vb[16]{}; unsigned dirty=0;} state;
 tu_cs sub_cs;
};
using VkCommandBuffer=tu_cmd_buffer *;
#define VK_FROM_HANDLE(type, name, handle) auto *name=handle
#define MAX2(a,b) std::max(a,b)
constexpr unsigned TU_CMD_DIRTY_VERTEX_BUFFERS=1;
static VkResult allocation_result;
static uint32_t packets[64];
static unsigned allocated, finalized, written;
static VkResult tu_cs_alloc(tu_cs *, uint32_t, uint32_t, tu_cs_memory *m) {
 if(allocation_result) return allocation_result;
 ++allocated; *m={packets,0x100001000,true}; return 0;
}
static void tu_cs_init_external(tu_cs *cs, void *, uint32_t *map, uint32_t *, uint64_t, bool) {cs->cur=map;}
static void tu_cs_begin(tu_cs *) {}
static VkResult tu_cs_reserve_space(tu_cs *, uint32_t) {return 0;}
static VkResult tu_cs_begin_sub_stream(tu_cs *sub, uint32_t n, tu_cs *cs) {
 tu_cs_memory m{}; auto r=tu_cs_alloc(sub,n,1,&m); if(r) return r;
 tu_cs_init_external(cs,nullptr,m.map,m.map+n,m.iova,m.writeable);return 0;
}
static tu_draw_state tu_cs_end_draw_state(tu_cs *, tu_cs *cs) {
 ++finalized; return {0x100001000,uint32_t(cs->cur-packets),true};
}
static void vk_command_buffer_set_error(decltype(tu_cmd_buffer::vk) *vk, VkResult r) {if(!vk->record_result)vk->record_result=r;}
static void vk_cmd_set_vertex_binding_strides(decltype(tu_cmd_buffer::vk) *,uint32_t,uint32_t,const uint64_t *) {}
static tu_buffer *tu_buffer_from_handle(VkBuffer b) {return b;}
static uint64_t vk_buffer_address(decltype(tu_buffer::vk) *b,uint64_t off) {return b->address+off;}
static uint32_t vk_buffer_range(decltype(tu_buffer::vk) *b,uint64_t off,uint64_t size) {return std::min(b->size-off,size);}
struct reg {uint64_t qword;};
#define A6XX_VFD_VERTEX_BUFFER_BASE(i,...) reg{__VA_ARGS__}
#define A6XX_VFD_VERTEX_BUFFER_SIZE(i,s) uint32_t(s)
static void tu_cs_emit_regs(tu_cs *cs,reg base,uint32_t size) {
 *cs->cur++=0x4000a083; *cs->cur++=uint32_t(base.qword);
 *cs->cur++=uint32_t(base.qword>>32); *cs->cur++=size; ++written;
}
'''
main = r'''
int main() {
 tu_buffer b{{0x100010000,4096}}; VkBuffer buffers[]={&b}; uint64_t offsets[]={64},sizes[]={128};
 for(int failure:{-1,-2,-4}) {
  tu_cmd_buffer cmd{};allocation_result=failure; allocated=finalized=written=0;
  tu_CmdBindVertexBuffers2(&cmd,0,1,buffers,offsets,sizes,nullptr);
  assert(cmd.vk.record_result==failure && !allocated && !finalized && !written);
  assert(cmd.state.vertex_buffers.iova==0 && cmd.state.dirty==0);
 }
 tu_cmd_buffer cmd{}; allocation_result=0; allocated=finalized=written=0;
 tu_CmdBindVertexBuffers2(&cmd,0,1,buffers,offsets,sizes,nullptr);
 assert(!cmd.vk.record_result && allocated==1 && finalized==1 && written==1);
 assert(cmd.state.vertex_buffers.iova==0x100001000 && cmd.state.vertex_buffers.size==4);
 assert(packets[0]==0x4000a083 && packets[1]==0x10040 && packets[2]==1 && packets[3]==128);
 assert(cmd.state.dirty==TU_CMD_DIRTY_VERTEX_BUFFERS);
 std::puts("PASS: actual vertex-binding body preserves 3 allocation errors without writes; success retains 4 packet words and draw state");
}
'''
with tempfile.TemporaryDirectory(prefix='tu-vertex-allocation-') as d:
    path=Path(d); cpp=path/'test.cpp'; exe=path/'test'
    cpp.write_text(peer+'\n'+helper+'\nvoid '+function+'\n'+main)
    subprocess.run(['clang++','-std=c++20','-O1','-g','-ftrivial-auto-var-init=zero','-fsanitize=address,undefined',str(cpp),'-o',str(exe)],check=True)
    subprocess.run([str(exe)],check=True)
