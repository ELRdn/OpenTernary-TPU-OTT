module product_equivalence(input wire signed [7:0] x,input wire [1:0] code,
 input wire enabled,output wire equal);
 wire signed [8:0] product;wire invalid;
 tpc_ternary_product dut(.x(x),.code(code),.enabled(enabled),.product(product),.invalid(invalid));
 wire signed [1:0] w=(code==0)?-2'sd1:((code==2)?2'sd1:2'sd0);
 wire signed [9:0] reference=$signed(x)*$signed(w);
 wire signed [9:0] actual={product[8],product};
 assign equal=(actual==(enabled?reference:10'sd0)) && (invalid==(enabled&&(code==3)));
endmodule
