module shiftrows(
    input [127:0] after_subbytes,
    output [127:0] after_shiftrows
);
    // input_COL --> rows --> shift --> output_COL (after_shiftrows)
    wire [31:0]col0 = {after_subbytes[127:120], after_subbytes[87:80], after_subbytes[47:40], after_subbytes[7:0]};
    wire [31:0]col1 = {after_subbytes[95:88], after_subbytes[55:48], after_subbytes[15:8], after_subbytes[103:96]};
    wire [31:0]col2 = {after_subbytes[63:56], after_subbytes[23:16], after_subbytes[111:104], after_subbytes[71:64]};
    wire [31:0]col3 = {after_subbytes[31:24], after_subbytes[119:112], after_subbytes[79:72], after_subbytes[39:32]};
    
    assign after_shiftrows = {col0, col1, col2, col3};
    
endmodule

// columns: quan he word --> 32bit
    // after_subbytes[127:96];
    // after_subbytes[95:64];
    // after_subbytes[63:32];
    // after_subbytes[31:0];

// rows: quan he chieu ngang (32bit), chieu cao (8bit)
    // {after_subbytes[127:120], after_subbytes[95:88], after_subbytes[63:56], after_subbytes[31:24]};
    // {after_subbytes[119:112], after_subbytes[87:80], after_subbytes[55:48], after_subbytes[23:16]};
    // {after_subbytes[111:104], after_subbytes[79:72], after_subbytes[47:40], after_subbytes[15:8]};
    // {after_subbytes[103:96], after_subbytes[71:64], after_subbytes[39:32], after_subbytes[7:0]};

// shift rows
    // {after_subbytes[127:120], after_subbytes[95:88], after_subbytes[63:56], after_subbytes[31:24]};
    // {after_subbytes[87:80], after_subbytes[55:48], after_subbytes[23:16], after_subbytes[119:112]};
    // {after_subbytes[47:40], after_subbytes[15:8], after_subbytes[111:104], after_subbytes[79:72]};
    // {after_subbytes[7:0], after_subbytes[103:96], after_subbytes[71:64], after_subbytes[39:32]};