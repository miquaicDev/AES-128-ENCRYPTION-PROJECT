module aes_core(
    input clk,
    input rst_n,
    input valid_in,
    input [127:0] plaintext,
    input [127:0] primekey,
    output [127:0] ciphertext,
    output valid_out
);
    (*rom_style="distributed"*) reg [7:0] rcon [10:1];
    initial begin
        rcon[1] = 8'h01;
        rcon[2] = 8'h02;
        rcon[3] = 8'h04;
        rcon[4] = 8'h08;
        rcon[5] = 8'h10;
        rcon[6] = 8'h20;
        rcon[7] = 8'h40;
        rcon[8] = 8'h80;
        rcon[9] = 8'h1b;
        rcon[10] = 8'h36;
    end
    // reduce delay in-reg
    reg [127:0] plaintext_reg;
    reg [127:0] primekey_reg;
    reg valid_in_reg;
    reg valid_out_reg;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            plaintext_reg <= 0;
            primekey_reg  <= 0;
            valid_in_reg  <= 0;
        end
        else if(valid_in) begin
            plaintext_reg <= plaintext;
            primekey_reg  <= primekey;
            valid_in_reg  <= valid_in;
        end
        else begin
            valid_in_reg <= 0;
        end
    end


    reg stage1_valid, stage2_valid;
    reg [3:0] stage1_round, stage2_round;
    reg [127:0] stage1_key, stage2_key;
    reg [127:0] stage1_reg, stage2_reg, ciphertext_reg;
    wire [127:0] after_shiftrows, start_of_round, key_exp_out, state_out;
    wire bypass_mix = (stage2_round == 4'd10);
    wire [31:0] round_rcon = {rcon[stage1_round], 24'h000000};;
    addroundkey addkey_init(
        plaintext_reg, 
        primekey_reg, 
        start_of_round
    );
    keyexpansion keygen(
        .keyin(stage1_key),
        .round_rcon(round_rcon),
        .keyout(key_exp_out)
    );
    sub_shift stage1(
        .state_in(stage1_reg),
        .after_shiftrows(after_shiftrows)
    );
    mix_add stage2(
        .state_in(stage2_reg),
        .keyin(stage2_key),
        .bypass_mix(bypass_mix),
        .state_out(state_out)
    );

    //wire [3:0] next_stage1_round = valid_in_reg? 4'd1:(stage2_round + 4'd1);
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            stage1_valid <= 0; stage2_valid <= 0;
            stage1_round <= 4'd1; stage2_round <= 4'd1;
            stage1_key <= 0; stage2_key <= 0;
            stage1_reg <= 0; stage2_reg <= 0;
            ciphertext_reg <= 0;
            valid_out_reg <= 0;
        end
        else begin
            //stage1
            if(valid_in_reg) begin
                stage1_valid <= 1'b1;
                stage1_round <= 4'd1;
                stage1_reg <= start_of_round;
                stage1_key <= primekey_reg;
            end
            else if(stage2_valid && stage2_round<4'd10) begin
                stage1_valid <= 1'b1;
                stage1_round <= stage2_round+4'd1;
                stage1_reg <= state_out;
                stage1_key <= stage2_key;
            end
            else begin
                stage1_valid <= 0;
            end
            //stage2
            if (stage1_valid) begin
                stage2_valid <= 1'b1;
                stage2_round <= stage1_round;
                stage2_reg <= after_shiftrows;
                stage2_key <= key_exp_out;
            end
            else begin
                stage2_valid <= 0;
            end
            valid_out_reg <= (stage2_valid && stage2_round == 4'd10);
            if(stage2_round == 4'd10)
                ciphertext_reg <= state_out;
        end
    end
    assign valid_out  = valid_out_reg;
    assign ciphertext = valid_out_reg? ciphertext_reg : 0;

endmodule

