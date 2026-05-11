module mix_add(
    input [127:0] state_in,
    input [127:0] keyin,
    input bypass_mix,
    output [127:0] state_out
);
    wire [127:0] after_mixcolumns, addkey_in;
    mixcolumns mc(
        .after_shiftrows(state_in),
        .after_mixcolumns(after_mixcolumns)
    );
    assign addkey_in = (bypass_mix)? state_in:after_mixcolumns;
    addroundkey addkey(
        .state_in(addkey_in),
        .roundkey(keyin),
        .state_out(state_out)
    );

endmodule