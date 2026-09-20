// Independent C++ fixed arithmetic. Not an RTL or FPGA timing simulator.
#include <cstdint>
#include <cstddef>
static int64_t rne(int64_t x, unsigned s) {
    if(!s) return x;
    const uint64_t a=x<0?uint64_t(-x):uint64_t(x);
    uint64_t q=a>>s;
    const uint64_t r=a&((uint64_t(1)<<s)-1), h=uint64_t(1)<<(s-1);
    if(r>h || (r==h && (q&1))) ++q;
    return x<0?-int64_t(q):int64_t(q);
}
extern "C" int tpc_gemm(const int8_t* a,const int8_t* w,const uint16_t* m,
    const uint8_t* s,int64_t* out,size_t bsize,size_t rows,size_t k,size_t group) {
    if(!a||!w||!m||!s||!out||!k||k>4096||!group||!rows||!bsize) return 1;
    const size_t ng=(k+group-1)/group;
    for(size_t r=0;r<rows;++r) for(size_t g=0;g<ng;++g) if(s[r*ng+g]>31) return 2;
    for(size_t i=0;i<rows*k;++i) if(w[i]<-1||w[i]>1) return 3;
    for(size_t b=0;b<bsize;++b) for(size_t r=0;r<rows;++r) {
        int64_t total=0;
        for(size_t g=0;g<ng;++g) {
            int32_t dot=0;
            const size_t end=(g+1)*group<k?(g+1)*group:k;
            for(size_t j=g*group;j<end;++j) {
                const int32_t x=a[b*k+j]; // extend BEFORE negate
                if(w[r*k+j]==1) dot+=x;
                else if(w[r*k+j]==-1) dot-=x;
            }
            total+=rne(int64_t(dot)*m[r*ng+g],s[r*ng+g]);
        }
        out[b*rows+r]=total;
    }
    return 0;
}
extern "C" int64_t tpc_rne(int64_t x,unsigned s) { return s<=31?rne(x,s):0; }
