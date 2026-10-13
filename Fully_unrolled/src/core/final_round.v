module final_round(
    input clk, rst_n, valid_in,
    input [127:0] state_in,
    input [127:0] keyin,
    input [31:0]round_rcon,
    output reg [127:0] state_out,
    output reg [127:0] keyout,
    output reg valid_out
);
    wire [127:0] roundkey;
    wire [127:0] after_subbytes, after_shiftrows, addroundkey_out;
    reg [127:0] stage1_reg, roundkey_reg;
    reg valid_out_stage1;
    // stage 1:
    keyexpansion genkey(
        .keyin(keyin),
        .round_rcon(round_rcon),
        .keyout(roundkey)
    );
    subbytes sb(
        .start_of_round(state_in),
        .after_subbytes(after_subbytes)
    );
    shiftrows shr(
        .after_subbytes(after_subbytes),
        .after_shiftrows(after_shiftrows)
    );
    always@(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            roundkey_reg <= 0;
            stage1_reg <= 0;
            valid_out_stage1 <= 0;
        end
        else if(valid_in)begin
            roundkey_reg <= roundkey;
            stage1_reg <= after_shiftrows;
            valid_out_stage1 <= 1'b1;
        end
        else begin
            valid_out_stage1 <= 0;
        end
    end

    // stage 2:
    addroundkey addkey(
        .state_in(stage1_reg),
        .roundkey(roundkey_reg),
        .state_out(addroundkey_out)
    );
    always@(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            valid_out <= 0;
            state_out <= 0;
            keyout <= 0;
        end
        else if(valid_out_stage1)begin
            state_out <= addroundkey_out;
            keyout <= roundkey_reg;
            valid_out <= 1'b1;
        end
        else 
            valid_out <= 0;
    end

endmodule