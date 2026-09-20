// R output rows x B token lanes x LANES input terms each accepted cycle.
// Default 16x4x16: 1024 ternary products/cycle, 256 in batch-one decode.
// Group boundaries are explicit; no scale is silently omitted.
module tpc_tile_mac #(
    parameter integer ROWS=16, LANES=16, BATCH=4, TAG_W=16
)(
    input wire clk, input wire rst,
    input wire in_valid, output wire in_ready,
    input wire [BATCH*LANES*8-1:0] in_a,
    input wire [ROWS*LANES*2-1:0] in_w,
    input wire [LANES-1:0] in_keep,
    input wire [ROWS-1:0] in_rows,
    input wire [BATCH-1:0] in_batch,
    input wire in_first, input wire in_last, input wire [TAG_W-1:0] in_tag,
    output reg out_valid, input wire out_ready,
    output reg [BATCH*ROWS*32-1:0] out_sums,
    output reg out_error, output reg [TAG_W-1:0] out_tag
);
    localparam integer STAGES=$clog2(LANES)+1;
    wire advance=!out_valid||out_ready;
    assign in_ready=!rst&&advance;
    reg [STAGES-1:0] vp,fp,lp,ep;
    reg [TAG_W-1:0] tp[0:STAGES-1];
    wire [ROWS*LANES*2-1:0] unpacked;
    wire [ROWS*LANES-1:0] invalid;
    wire signed [31:0] dots[0:BATCH*ROWS-1];
    reg signed [31:0] accum[0:BATCH*ROWS-1];
    wire signed [31:0] next_accum[0:BATCH*ROWS-1];
    genvar r,k,b;
    generate for(r=0;r<ROWS;r=r+1) begin: decode_row
        for(k=0;k<LANES;k=k+1) begin: decode_lane
            localparam integer I=r*LANES+k;
            localparam integer P=(I/4)*8+6-2*(I%4);
            // byte 0 is bus[7:0]; first element uses byte[7:6].
            assign unpacked[I*2 +:2]=in_w[P +:2];
            assign invalid[I]=in_rows[r]&&in_keep[k]&&(|in_batch)&&(in_w[P +:2]==2'b11);
        end
    end endgenerate
    generate for(b=0;b<BATCH;b=b+1) begin: tokens
        for(r=0;r<ROWS;r=r+1) begin: channels
            localparam integer I=b*ROWS+r;
            tpc_dot_pipe #(.LANES(LANES)) dot(
                .clk(clk),.ce(advance),.activation(in_a[b*LANES*8 +:LANES*8]),
                .codes(unpacked[r*LANES*2 +:LANES*2]),
                .enabled(in_keep&{LANES{in_rows[r]&&in_batch[b]}}),.sum(dots[I]));
            assign next_accum[I]=fp[STAGES-1]?dots[I]:accum[I]+dots[I];
        end
    end endgenerate
    reg group_open,group_error;
    wire protocol_error=(fp[STAGES-1]&&group_open)||(!fp[STAGES-1]&&!group_open);
    wire current_error=(fp[STAGES-1]?1'b0:group_error)|ep[STAGES-1]|protocol_error;
    integer i;
    always @(posedge clk) begin
        if(rst) begin
            vp<=0;fp<=0;lp<=0;ep<=0;
            out_valid<=0;out_sums<=0;out_error<=0;out_tag<=0;
            group_open<=0;group_error<=0;
            for(i=0;i<STAGES;i=i+1) tp[i]<=0;
            for(i=0;i<BATCH*ROWS;i=i+1) accum[i]<=0;
        end else if(advance) begin
            out_valid<=0;
            vp[0]<=in_valid;fp[0]<=in_first;lp[0]<=in_last;ep[0]<=|invalid;tp[0]<=in_tag;
            for(i=1;i<STAGES;i=i+1) begin
                vp[i]<=vp[i-1];fp[i]<=fp[i-1];lp[i]<=lp[i-1];ep[i]<=ep[i-1];tp[i]<=tp[i-1];
            end
            if(vp[STAGES-1]) begin
                group_open<=!lp[STAGES-1];group_error<=current_error;
                for(i=0;i<BATCH*ROWS;i=i+1) accum[i]<=next_accum[i];
                if(lp[STAGES-1]) begin
                    out_valid<=1;out_error<=current_error;out_tag<=tp[STAGES-1];
                    for(i=0;i<BATCH*ROWS;i=i+1) out_sums[32*i +:32]<=next_accum[i];
                end
            end
        end
    end
`ifndef SYNTHESIS
    initial if((ROWS*LANES)%4!=0) $fatal(1,"packed weight bus requires whole bytes");
`endif
endmodule
