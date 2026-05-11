module sub_shift(
    input [127:0] state_in,
    output [127:0] after_shiftrows
);
    wire [127:0] after_subbytes;
    subbytes sb(
        .start_of_round(state_in),
        .after_subbytes(after_subbytes)
    );
    shiftrows shr(
        .after_subbytes(after_subbytes),
        .after_shiftrows(after_shiftrows)
    );
    
endmodule