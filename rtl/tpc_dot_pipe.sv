// Narrow registered balanced reduction tree. No general multiplier.
// Latency: one product register + log2(LANES) tree registers.
module tpc_dot_pipe #(parameter integer LANES=16)(
    input wire clk, input wire ce,
    input wire [LANES*8-1:0] activation,
    input wire [LANES*2-1:0] codes,
    input wire [LANES-1:0] enabled,
    output wire signed [31:0] sum
);
    localparam integer LEVELS=$clog2(LANES);
    wire signed [8:0] selected[0:LANES-1];
    reg signed [8:0] products[0:LANES-1];
    genvar k,l,j;
    generate for(k=0;k<LANES;k=k+1) begin: leaf
        wire ignored;
        tpc_ternary_product term(.x(activation[k*8 +:8]),.code(codes[k*2 +:2]),
            .enabled(enabled[k]),.product(selected[k]),.invalid(ignored));
        always @(posedge clk) if(ce) products[k]<=selected[k];
    end endgenerate
    generate for(l=1;l<=LEVELS;l=l+1) begin: level
        localparam integer WIDTH=9+l;
        reg signed [WIDTH-1:0] value[0:(LANES>>l)-1];
        for(j=0;j<(LANES>>l);j=j+1) begin: node
            if(l==1) begin: bottom
                always @(posedge clk) if(ce)
                    value[j]<=$signed({products[2*j][8],products[2*j]})
                             +$signed({products[2*j+1][8],products[2*j+1]});
            end else begin: higher
                always @(posedge clk) if(ce)
                    value[j]<=$signed({level[l-1].value[2*j][WIDTH-2],level[l-1].value[2*j]})
                             +$signed({level[l-1].value[2*j+1][WIDTH-2],level[l-1].value[2*j+1]});
            end
        end
    end endgenerate
    generate if(LEVELS==0) begin: single
        assign sum={{23{products[0][8]}},products[0]};
    end else begin: multiple
        assign sum={{(23-LEVELS){level[LEVELS].value[0][8+LEVELS]}},level[LEVELS].value[0]};
    end endgenerate
`ifndef SYNTHESIS
    initial if(LANES<1 || (LANES&(LANES-1))!=0 || LANES>1024)
        $fatal(1,"LANES must be a power of two in 1..1024");
`endif
endmodule
