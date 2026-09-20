module t5_equivalence(input wire [7:0] byte_in,output wire equal);
 wire [9:0] codes;wire invalid;
 tpc_radix3_decode5 dut(.byte_in(byte_in),.codes(codes),.invalid(invalid));
 wire [9:0] sum=codes[1:0]+codes[3:2]*10'd3+codes[5:4]*10'd9+codes[7:6]*10'd27+codes[9:8]*10'd81;
 wire digits=(codes[1:0]<3)&&(codes[3:2]<3)&&(codes[5:4]<3)&&(codes[7:6]<3)&&(codes[9:8]<3);
 assign equal=(byte_in<243)?(!invalid&&digits&&sum==byte_in):(invalid&&codes==10'b0101010101);
endmodule
