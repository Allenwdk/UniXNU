// SPDX-License-Identifier: MIT
// The first-use check's sampler (NATIVE-YCBCR.md): the RGBA a texture reads at the centre of each
// texel of a window, so a native surface's reading and the compute conversion's are compared on
// the same texels.
#include <metal_stdlib>
using namespace metal;

kernel void ycbcr_sample(texture2d<float, access::sample> src [[texture(0)]],
                         sampler samp [[sampler(0)]],
                         device float4 *out [[buffer(0)]],
                         constant uint2 &window [[buffer(1)]],
                         uint2 gid [[thread_position_in_grid]]) {
    if (gid.x >= window.x || gid.y >= window.y) return;
    const float2 uv = (float2(gid) + 0.5) / float2(window);
    out[gid.y * window.x + gid.x] = src.sample(samp, uv);
}
