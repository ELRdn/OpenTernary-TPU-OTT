// Canonical codes: 00=-1, 01=0, 10=+1, 11=invalid.
module tpc_ternary_product(
    input wire signed [7:0] x, input wire [1:0] code, input wire enabled,
    output reg signed [8:0] product, output reg invalid
);
    wire signed [8:0] wide_x={x[7],x};
    always @* begin
        product=9'sd0;invalid=1'b0;
        if(enabled) case(code)
            2'b00: product=-wide_x;
            2'b01: product=9'sd0;
            2'b10: product=wide_x;
            default: begin product=9'sd0;invalid=1'b1;end
        endcase
    end
endmodule
