// Group-scaled matrix engine. Metadata FIFO binds each group to its coefficients.
// Caller must provide exactly one FIRST and LAST per group; command frontend enforces this.
module tpc_stream_engine #(
    parameter integer ROWS=16,LANES=16,BATCH=4,GROUP=128,TAG_W=16
)(
    input wire clk,input wire rst,
    input wire in_valid,output wire in_ready,
    input wire [BATCH*LANES*8-1:0] in_a,input wire [ROWS*LANES*2-1:0] in_w,
    input wire [LANES-1:0] in_keep,input wire [ROWS-1:0] in_rows,input wire [BATCH-1:0] in_batch,
    input wire in_first,input wire in_last,input wire in_tile_first,input wire in_tile_last,
    input wire [ROWS*32-1:0] in_scale,input wire [TAG_W-1:0] in_tag,
    output wire out_valid,input wire out_ready,
    output wire [BATCH*ROWS*64-1:0] out_data,output wire out_error,output wire [TAG_W-1:0] out_tag
);
    wire mr,mv,me,sr,fi,fo;
    wire [BATCH*ROWS*32-1:0] ms;
    wire [TAG_W-1:0] mt;
    wire [ROWS*32+1:0] metadata;
    wire allowed=!in_first||fi;
    wire accept=in_valid&&in_ready;
    assign in_ready=mr&&allowed;
    tpc_sync_fifo #(.WIDTH(ROWS*32+2),.DEPTH(4)) meta_fifo(
        .clk(clk),.rst(rst),.in_valid(accept&&in_first),.in_ready(fi),
        .in_data({in_tile_last,in_tile_first,in_scale}),.out_valid(fo),
        .out_ready(mv&&sr),.out_data(metadata));
    tpc_tile_mac #(.ROWS(ROWS),.LANES(LANES),.BATCH(BATCH),.TAG_W(TAG_W)) mac(
        .clk(clk),.rst(rst),.in_valid(in_valid&&allowed),.in_ready(mr),
        .in_a(in_a),.in_w(in_w),.in_keep(in_keep),.in_rows(in_rows),.in_batch(in_batch),
        .in_first(in_first),.in_last(in_last),.in_tag(in_tag),
        .out_valid(mv),.out_ready(sr&&fo),.out_sums(ms),.out_error(me),.out_tag(mt));
    tpc_group_scale #(.ROWS(ROWS),.BATCH(BATCH),.GROUP(GROUP),.TAG_W(TAG_W)) scaler(
        .clk(clk),.rst(rst),.in_valid(mv&&fo),.in_ready(sr),.in_sums(ms),
        .in_scale(metadata[0 +:ROWS*32]),.in_first(metadata[ROWS*32]),
        .in_last(metadata[ROWS*32+1]),.in_error(me),.in_tag(mt),
        .out_valid(out_valid),.out_ready(out_ready),.out_data(out_data),.out_error(out_error),.out_tag(out_tag));
`ifndef SYNTHESIS
    initial if(GROUP%LANES!=0) $fatal(1,"GROUP must be divisible by LANES");
`endif
endmodule
