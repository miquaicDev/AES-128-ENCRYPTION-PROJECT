module xtimes(
    input [7:0] byte_in,
    output [7:0] byte_out
);
    assign byte_out = (byte_in[7]==1)? {byte_in[6:0], 1'b0}^8'h1b : {byte_in[6:0], 1'b0};

endmodule