// C ABI around REAL Yosys-compiled RTL. No arithmetic is reimplemented here.
// Inputs/outputs are sampled away from the rising edge to avoid races.
#include <cstdint>
#include <new>
#include "../build/accelerator.cc"
using DUT=cxxrtl_design::p_tpc__accelerator;
template<size_t W> static void put(cxxrtl::value<W>& v,unsigned i,uint32_t x){v.data[i]=x;}
template<size_t W> static void put(cxxrtl::wire<W>& v,unsigned i,uint32_t x){v.next.data[i]=x;}
template<size_t W> static uint32_t getword(const cxxrtl::value<W>& v,unsigned i){return v.data[i];}
template<size_t W> static uint32_t getword(const cxxrtl::wire<W>& v,unsigned i){return v.curr.data[i];}
extern "C" void* tpc_rtl_new(){ return new(std::nothrow) DUT; }
extern "C" void tpc_rtl_delete(void* p){ delete static_cast<DUT*>(p); }
extern "C" int tpc_rtl_tick(void* p,const uint32_t* in,uint32_t* out){
    if(!p||!in||!out) return 1;
    DUT& d=*static_cast<DUT*>(p);
    const uint32_t f=in[0];
    d.p_clk.set(false);
    d.p_rst.set(bool(f&1));
    d.p_a__valid.set(bool(f&2));d.p_w__valid.set(bool(f&4));
    d.p_s__valid.set(bool(f&8));d.p_cmd__valid.set(bool(f&16));
    d.p_out__ready.set(bool(f&32));
    d.p_w__bank.set(bool(f&64));d.p_s__bank.set(bool(f&128));d.p_cmd__bank.set(bool(f&256));
    d.p_a__addr.set(in[1]);d.p_w__addr.set(in[2]);d.p_s__addr.set(in[3]);
    d.p_cmd__k.set(in[4]);d.p_cmd__rows.set(in[5]);d.p_cmd__batch.set(in[6]);d.p_cmd__tag.set(in[7]);
    for(unsigned j=0;j<16;++j){put(d.p_a__data,j,in[8+j]);put(d.p_w__data,j,in[24+j]);put(d.p_s__data,j,in[40+j]);}
    d.step(); // settle with clock low before sampling ready/valid
    out[0]=uint32_t(d.p_a__ready.get<bool>()) | (uint32_t(d.p_w__ready.get<bool>())<<1)
        | (uint32_t(d.p_s__ready.get<bool>())<<2) | (uint32_t(d.p_cmd__ready.get<bool>())<<3)
        | (uint32_t(d.p_out__valid.get<bool>())<<4) | (uint32_t(d.p_out__error.get<bool>())<<5)
        | (uint32_t(d.p_busy.get<bool>())<<6) | (uint32_t(d.p_done.get<bool>())<<7)
        | (d.p_status.get<uint32_t>()<<8);
    out[2]=d.p_out__tag.get<uint32_t>();out[3]=0;
    for(unsigned j=0;j<128;++j)out[4+j]=getword(d.p_out__data,j);
    d.p_clk.set(true);d.step(); // actual register transition
    out[1]=uint32_t(d.p_busy.get<bool>()) | (uint32_t(d.p_done.get<bool>())<<1)
        | (d.p_status.get<uint32_t>()<<8);
    return 0;
}
