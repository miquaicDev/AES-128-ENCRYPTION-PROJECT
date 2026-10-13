module mixcolumns(
    input [127:0] after_shiftrows, 
    output [127:0] after_mixcolumns
);
    genvar i;
    generate
        for(i=3; i>=0; i=i-1)begin:mult2mat
            wire [7:0] s3 = after_shiftrows[32*i+0 +: 8];
            wire [7:0] s2 = after_shiftrows[32*i+8 +: 8];
            wire [7:0] s1 = after_shiftrows[32*i+16 +: 8];
            wire [7:0] s0 = after_shiftrows[32*i+24 +: 8];
            wire [7:0] s0_mult2, s1_mult2, s2_mult2, s3_mult2;
            xtimes mult20(s0, s0_mult2);
            xtimes mult21(s1, s1_mult2);
            xtimes mult22(s2, s2_mult2);
            xtimes mult23(s3, s3_mult2);
            wire [7:0]s0_mult3 = s0_mult2 ^ s0;
            wire [7:0]s1_mult3 = s1_mult2 ^ s1;
            wire [7:0]s2_mult3 = s2_mult2 ^ s2;
            wire [7:0]s3_mult3 = s3_mult2 ^ s3;
            assign after_mixcolumns[32*i+0 +: 8] = s0_mult3 ^ s1 ^ s2 ^ s3_mult2;
            assign after_mixcolumns[32*i+8 +: 8] = s0 ^ s1 ^ s2_mult2 ^ s3_mult3;
            assign after_mixcolumns[32*i+16 +: 8]= s0 ^ s1_mult2 ^ s2_mult3 ^ s3;
            assign after_mixcolumns[32*i+24 +: 8]= s0_mult2 ^ s1_mult3 ^ s2 ^ s3;
        end    
    endgenerate

endmodule

// mat a
    // 02 03 01 01
    // 01 02 03 01
    // 01 01 02 03
    // 03 01 01 02

// columns
    // [127:96];
    // [95:64];
    // [63:32];
    // [31:0];
// ==> 96, 64, 32, 0 --> step is 32 --> 32*i
// 32*i+var +: 8 --> get each bytes per word
// var = 0, 8, 16, 24 = s3, s2, s1, s0
// i=4word