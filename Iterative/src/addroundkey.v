module addroundkey(
    input [127:0] state_in,
    input [127:0] roundkey,
    output [127:0] state_out
);
    assign state_out = state_in ^ roundkey;

endmodule