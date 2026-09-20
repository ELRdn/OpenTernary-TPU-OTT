// Tile-level NPU integration. External memory transport attaches to the load ports.
// This module is NOT a board DDR controller or a complete Transformer processor.
// Default storage: A 16 KiB, W ping-pong 32 KiB, coefficients ping-pong 4 KiB.
module tpc_accelerator #(
    parameter integer ROWS=16,LANES=16,BATCH=4,GROUP=128,MAX_K=4096,TAG_W=16,
    parameter integer DEPTH=MAX_K/LANES,AW=$clog2(DEPTH),
    parameter integer GDEPTH=MAX_K/GROUP,GAW=$clog2(GDEPTH),
    parameter integer KW=$clog2(MAX_K+1),RW=$clog2(ROWS+1),BW=$clog2(BATCH+1)
)(
    input wire clk,input wire rst,
    input wire a_valid,output wire a_ready,input wire [AW-1:0] a_addr,
    input wire [BATCH*LANES*8-1:0] a_data,
    input wire w_valid,output wire w_ready,input wire w_bank,input wire [AW-1:0] w_addr,
    input wire [ROWS*LANES*2-1:0] w_data,
    input wire s_valid,output wire s_ready,input wire s_bank,input wire [GAW-1:0] s_addr,
    input wire [ROWS*32-1:0] s_data,
    input wire cmd_valid,output wire cmd_ready,input wire cmd_bank,
    input wire [KW-1:0] cmd_k,input wire [RW-1:0] cmd_rows,input wire [BW-1:0] cmd_batch,
    input wire [TAG_W-1:0] cmd_tag,
    output reg busy,output reg done,output reg [2:0] status,
    output wire out_valid,input wire out_ready,
    output wire [BATCH*ROWS*64-1:0] out_data,output wire out_error,output wire [TAG_W-1:0] out_tag
);
    localparam integer LG_L=$clog2(LANES),LG_G=$clog2(GROUP);
    reg active_bank;
    reg [KW-1:0] length;
    reg [AW:0] issued,steps;
    reg [ROWS-1:0] row_mask;
    reg [BATCH-1:0] batch_mask;
    reg [TAG_W-1:0] tag;
    reg pending;
    reg [LANES-1:0] keep;
    reg first,last,tile_first,tile_last;
    reg [DEPTH-1:0] a_loaded;
    reg [2*DEPTH-1:0] w_loaded;
    reg [2*GDEPTH-1:0] s_loaded;
    assign a_ready=!rst&&!busy;
    assign w_ready=!rst&&(!busy||w_bank!=active_bank);
    assign s_ready=!rst&&(!busy||s_bank!=active_bank);
    assign cmd_ready=!rst&&!busy;
    wire ar=a_valid&&a_ready,wr=w_valid&&w_ready,swr=s_valid&&s_ready;
    wire engine_ready;
    wire issue=busy&&(issued<steps)&&(!pending||engine_ready);
    wire [AW-1:0] read_addr=issued[AW-1:0];
    wire [KW:0] k_start=issued*LANES;
    wire [GAW-1:0] group_addr=k_start>>LG_G;
    wire [BATCH*LANES*8-1:0] read_a;
    wire [ROWS*LANES*2-1:0] read_w;
    wire [ROWS*32-1:0] read_s;
    tpc_sdp_ram #(.WIDTH(BATCH*LANES*8),.DEPTH(DEPTH),.AW(AW)) activation_ram(
        .clk(clk),.wr_en(ar),.wr_addr(a_addr),.wr_data(a_data),
        .rd_en(issue),.rd_addr(read_addr),.rd_data(read_a));
    tpc_sdp_ram #(.WIDTH(ROWS*LANES*2),.DEPTH(2*DEPTH),.AW(AW+1)) weight_ram(
        .clk(clk),.wr_en(wr),.wr_addr({w_bank,w_addr}),.wr_data(w_data),
        .rd_en(issue),.rd_addr({active_bank,read_addr}),.rd_data(read_w));
    tpc_sdp_ram #(.WIDTH(ROWS*32),.DEPTH(2*GDEPTH),.AW(GAW+1)) scale_ram(
        .clk(clk),.wr_en(swr),.wr_addr({s_bank,s_addr}),.wr_data(s_data),
        .rd_en(issue),.rd_addr({active_bank,group_addr}),.rd_data(read_s));
    tpc_stream_engine #(.ROWS(ROWS),.LANES(LANES),.BATCH(BATCH),.GROUP(GROUP),.TAG_W(TAG_W)) engine(
        .clk(clk),.rst(rst),.in_valid(pending),.in_ready(engine_ready),
        .in_a(read_a),.in_w(read_w),.in_keep(keep),.in_rows(row_mask),.in_batch(batch_mask),
        .in_first(first),.in_last(last),.in_tile_first(tile_first),.in_tile_last(tile_last),
        .in_scale(read_s),.in_tag(tag),.out_valid(out_valid),.out_ready(out_ready),
        .out_data(out_data),.out_error(out_error),.out_tag(out_tag));
    // These validity bits prevent reading never-initialized addresses. They do not
    // replace software's generation/version ownership of reused buffers.
    reg command_initialized;
    integer c;
    always @* begin
        command_initialized=1'b1;
        for(c=0;c<DEPTH;c=c+1)
            if(c*LANES<cmd_k && (!a_loaded[c]||!w_loaded[cmd_bank*DEPTH+c])) command_initialized=1'b0;
        for(c=0;c<GDEPTH;c=c+1)
            if(c*GROUP<cmd_k && !s_loaded[cmd_bank*GDEPTH+c]) command_initialized=1'b0;
    end
    integer i;
    always @(posedge clk) begin
        if(rst) begin
            busy<=0;done<=0;status<=0;active_bank<=0;length<=0;issued<=0;steps<=0;
            pending<=0;keep<=0;first<=0;last<=0;tile_first<=0;tile_last<=0;
            row_mask<=0;batch_mask<=0;tag<=0;a_loaded<=0;w_loaded<=0;s_loaded<=0;
        end else begin
            done<=0;
            if(ar) a_loaded[a_addr]<=1'b1;
            if(wr) w_loaded[{w_bank,w_addr}]<=1'b1;
            if(swr) s_loaded[{s_bank,s_addr}]<=1'b1;
            if(cmd_valid&&cmd_ready) begin
                if(cmd_k==0||cmd_k>MAX_K||cmd_rows==0||cmd_rows>ROWS||cmd_batch==0||cmd_batch>BATCH) begin
                    status<=3'd1;done<=1;
                end else if(!command_initialized) begin
                    status<=3'd2;done<=1;
                end else begin
                    busy<=1;status<=0;active_bank<=cmd_bank;length<=cmd_k;issued<=0;
                    steps<=(cmd_k+LANES-1)>>LG_L;pending<=0;tag<=cmd_tag;
                    for(i=0;i<ROWS;i=i+1) row_mask[i]<=i<cmd_rows;
                    for(i=0;i<BATCH;i=i+1) batch_mask[i]<=i<cmd_batch;
                end
            end
            if(busy) begin
                if(issue) begin
                    issued<=issued+1'b1;pending<=1;
                    for(i=0;i<LANES;i=i+1) keep[i]<=k_start+i<length;
                    first<=(k_start%GROUP)==0;
                    last<=((k_start+LANES)%GROUP)==0 || k_start+LANES>=length;
                    tile_first<=k_start<GROUP;
                    tile_last<=(k_start/GROUP)==((length-1)/GROUP);
                end else if(pending&&engine_ready) pending<=0;
                if(out_valid&&out_ready) begin
                    busy<=0;done<=1;pending<=0;status<=out_error?3'd3:3'd0;
                end
            end
        end
    end
`ifndef SYNTHESIS
    initial begin
        if(MAX_K%GROUP!=0||GROUP%LANES!=0||DEPTH<2||GDEPTH<2)
            $fatal(1,"unsupported memory geometry");
        if((DEPTH&(DEPTH-1))!=0 || (GDEPTH&(GDEPTH-1))!=0)
            $fatal(1,"memory depths must be powers of two for bank concatenation");
    end
`endif
endmodule
