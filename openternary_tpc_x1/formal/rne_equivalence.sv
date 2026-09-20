module rne_equivalence(input wire signed [32:0] value, input wire [7:0] shift, output wire equal);
localparam integer PW=33;
    function automatic signed [63:0] rne_old;
        input signed [63:0] value;
        input [7:0] shift;
        reg [63:0] magnitude,q,r,h,mask;
        begin
            magnitude=value[63]?$unsigned(-value):$unsigned(value);
            q=magnitude;r=0;h=0;mask=0;
            if(shift>31) rne_old=64'sd0;
            else if(shift==0) rne_old=value;
            else begin
                mask=(64'h1<<shift)-1'b1;
                q=magnitude>>shift;r=magnitude&mask;h=64'h1<<(shift-1'b1);
                if(r>h||(r==h&&q[0])) q=q+1'b1;
                rne_old=value[63]?-$signed(q):$signed(q);
            end
        end
    endfunction
    // RNE works at the actual signed product width, not an artificial 64-bit width.
    // Sign extension happens only AFTER rounding. This eliminates wide barrel
    // shifters/comparators while preserving the INT64 accumulation contract.
    function automatic signed [PW-1:0] rne_new;
        input signed [PW-1:0] value;
        input [7:0] shift;
        reg [PW-1:0] magnitude,q,r,h,mask;
        reg [PW-1:0] one;
        begin
            one={{(PW-1){1'b0}},1'b1};
            magnitude=value[PW-1]?$unsigned(-value):$unsigned(value);
            q=magnitude;r=0;h=0;mask=0;
            if(shift>31 || shift>=PW) rne_new=0;
            else if(shift==0) rne_new=value;
            else begin
                mask=(one<<shift)-1'b1;
                q=magnitude>>shift;r=magnitude&mask;h=one<<(shift-1'b1);
                if(r>h||(r==h&&q[0])) q=q+1'b1;
                rne_new=value[PW-1]?-$signed(q):$signed(q);
            end
        end
    endfunction

wire signed [63:0] a=rne_old({{31{value[32]}},value},shift);
wire signed [32:0] narrow=rne_new(value,shift);
wire signed [63:0] b={{31{narrow[32]}},narrow};
assign equal=(a==b);
endmodule
