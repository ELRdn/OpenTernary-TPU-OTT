// Simple dual-port synchronous RAM. One-cycle read. Contents are not reset.
module tpc_sdp_ram #(
    parameter integer WIDTH=512,DEPTH=256,AW=$clog2(DEPTH)
)(
    input wire clk,
    input wire wr_en,input wire [AW-1:0] wr_addr,input wire [WIDTH-1:0] wr_data,
    input wire rd_en,input wire [AW-1:0] rd_addr,output reg [WIDTH-1:0] rd_data
);
    (* ram_style="block" *) reg [WIDTH-1:0] mem[0:DEPTH-1];
    always @(posedge clk) begin
        if(wr_en) mem[wr_addr]<=wr_data;
        if(rd_en) rd_data<=mem[rd_addr];
    end
endmodule
