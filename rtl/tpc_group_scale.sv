// Separate scaling path: general multipliers/DSPs ARE permitted here.
// Coefficient word [15:0]=unsigned mantissa, [23:16]=right shift 0..31,
// [31:24]=reserved zero. Signed RNE. INT64 final accumulation.
module tpc_group_scale #(
    parameter integer ROWS=16,BATCH=4,GROUP=128,TAG_W=16,
    parameter integer GP_W=9+$clog2(GROUP)
)(
    input wire clk,input wire rst,
    input wire in_valid,output wire in_ready,
    input wire [BATCH*ROWS*32-1:0] in_sums,input wire [ROWS*32-1:0] in_scale,
    input wire in_first,input wire in_last,input wire in_error,
    input wire [TAG_W-1:0] in_tag,
    output reg out_valid,input wire out_ready,
    output reg [BATCH*ROWS*64-1:0] out_data,
    output reg out_error,output reg [TAG_W-1:0] out_tag
);
    localparam integer COUNT=ROWS*BATCH,PW=GP_W+17;
    wire advance=!out_valid||out_ready;
    assign in_ready=!rst&&advance;
    reg v0,v1,f0,f1,l0,l1,e0,e1,tile_error;
    reg [TAG_W-1:0] t0,t1;
    reg signed [PW-1:0] product[0:COUNT-1];
    reg [7:0] shift0[0:ROWS-1];
    reg signed [63:0] rounded[0:COUNT-1],accum[0:COUNT-1];
    wire signed [63:0] next_accum[0:COUNT-1];
    wire signed [PW-1:0] product_wire[0:COUNT-1];
    wire [COUNT-1:0] bad_sum;
    wire [ROWS-1:0] bad_scale;
    // RNE works at the actual signed product width, not an artificial 64-bit width.
    // Sign extension happens only AFTER rounding. This eliminates wide barrel
    // shifters/comparators while preserving the INT64 accumulation contract.
    function automatic signed [PW-1:0] rne;
        input signed [PW-1:0] value;
        input [7:0] shift;
        reg [PW-1:0] magnitude,q,r,h,mask;
        reg [PW-1:0] one;
        begin
            one={{(PW-1){1'b0}},1'b1};
            magnitude=value[PW-1]?$unsigned(-value):$unsigned(value);
            q=magnitude;r=0;h=0;mask=0;
            if(shift>31 || shift>=PW) rne=0;
            else if(shift==0) rne=value;
            else begin
                mask=(one<<shift)-1'b1;
                q=magnitude>>shift;r=magnitude&mask;h=one<<(shift-1'b1);
                if(r>h||(r==h&&q[0])) q=q+1'b1;
                rne=value[PW-1]?-$signed(q):$signed(q);
            end
        end
    endfunction
    genvar r,b;
    generate for(r=0;r<ROWS;r=r+1) begin: check_scale
        assign bad_scale[r]=(in_scale[r*32+24 +:8]!=0)||(in_scale[r*32+16 +:8]>31);
    end endgenerate
    generate for(b=0;b<BATCH;b=b+1) begin: bs
        for(r=0;r<ROWS;r=r+1) begin: rs
            localparam integer I=b*ROWS+r;
            wire signed [31:0] value=in_sums[I*32 +:32];
            wire signed [GP_W-1:0] narrow=value[GP_W-1:0];
            wire signed [16:0] m={1'b0,in_scale[r*32 +:16]};
            assign product_wire[I]=$signed(narrow)*$signed(m);
            assign bad_sum[I]=(value>GROUP*128)||(value<-(GROUP*128));
            assign next_accum[I]=f1?rounded[I]:accum[I]+rounded[I];
        end
    end endgenerate
    integer i;
    always @(posedge clk) begin
        if(rst) begin
            v0<=0;v1<=0;f0<=0;f1<=0;l0<=0;l1<=0;e0<=0;e1<=0;t0<=0;t1<=0;tile_error<=0;
            out_valid<=0;out_data<=0;out_error<=0;out_tag<=0;
            for(i=0;i<COUNT;i=i+1) begin product[i]<=0;rounded[i]<=0;accum[i]<=0;end
            for(i=0;i<ROWS;i=i+1) shift0[i]<=0;
        end else if(advance) begin
            out_valid<=0;
            v0<=in_valid;v1<=v0;f0<=in_first;f1<=f0;l0<=in_last;l1<=l0;
            e0<=in_error||(|bad_sum)||(|bad_scale);e1<=e0;t0<=in_tag;t1<=t0;
            if(in_valid) begin
                for(i=0;i<COUNT;i=i+1) product[i]<=product_wire[i];
                for(i=0;i<ROWS;i=i+1) shift0[i]<=in_scale[i*32+16 +:8];
            end
            if(v0) for(i=0;i<COUNT;i=i+1)
                rounded[i]<=$signed(rne(product[i],shift0[i%ROWS]));
            if(v1) begin
                for(i=0;i<COUNT;i=i+1) accum[i]<=next_accum[i];
                tile_error<=(f1?1'b0:tile_error)||e1;
                if(l1) begin
                    out_valid<=1;out_error<=(f1?1'b0:tile_error)||e1;out_tag<=t1;
                    for(i=0;i<COUNT;i=i+1) out_data[i*64 +:64]<=next_accum[i];
                end
            end
        end
    end
`ifndef SYNTHESIS
    initial if(GP_W>32||PW>=64) $fatal(1,"unsupported scale width");
`endif
endmodule
