module tpc_sync_fifo #(
    parameter integer WIDTH=32,DEPTH=4,AW=(DEPTH<=1?1:$clog2(DEPTH))
)(
    input wire clk,input wire rst,
    input wire in_valid,output wire in_ready,input wire [WIDTH-1:0] in_data,
    output wire out_valid,input wire out_ready,output wire [WIDTH-1:0] out_data
);
    reg [WIDTH-1:0] mem[0:DEPTH-1];
    reg [AW-1:0] rd,wr;
    reg [AW:0] count;
    wire push=in_valid&&in_ready,pop=out_valid&&out_ready;
    assign in_ready=!rst&&count<DEPTH;
    assign out_valid=!rst&&count!=0;
    assign out_data=mem[rd];
    always @(posedge clk) begin
        if(rst) begin rd<=0;wr<=0;count<=0;end
        else begin
            if(push) begin mem[wr]<=in_data;wr<=(wr==DEPTH-1)?0:wr+1'b1;end
            if(pop) rd<=(rd==DEPTH-1)?0:rd+1'b1;
            case({push,pop})
                2'b10:count<=count+1'b1;
                2'b01:count<=count-1'b1;
                default:count<=count;
            endcase
        end
    end
endmodule
