module aes_core(
   input clk, rst_n, valid_in,
   input [127:0] plaintext,
   input [127:0] primekey,
   output [127:0] ciphertext,
   output valid_out
);
    // reduce delay In-Reg
    reg [127:0] plaintext_reg;
    reg [127:0] primekey_reg;
    reg valid_in_reg;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            plaintext_reg <= 0;
            primekey_reg  <= 0;
            valid_in_reg  <= 0;
        end else begin
            plaintext_reg <= plaintext;
            primekey_reg  <= primekey;
            valid_in_reg  <= valid_in;
        end
    end

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
   // init round
    wire [128*10-1:0] state_array;
    wire [128*10-1:0] roundkey_array;
    wire [9:0] valid_array;
    assign roundkey_array[127:0] = primekey_reg;
    addroundkey addkey_init(
        plaintext_reg, primekey_reg, state_array[127:0]
    );
    assign valid_array[0] = valid_in_reg;

    // round 1 -> 9
    genvar i;
    generate
       for(i=1; i<10; i=i+1)begin:nine_round
           main_round nine_round(
                .clk(clk),
                .rst_n(rst_n),
                .valid_in(valid_array[i-1]),
                .state_in(state_array[128*(i-1) +: 128]),
                .keyin(roundkey_array[128*(i-1) +: 128]),
                .round_rcon({rcon[i], 24'h000000}),
                .state_out(state_array[128*i +: 128]),
                .keyout(roundkey_array[128*i +: 128]),
                .valid_out(valid_array[i])
           );
       end
   endgenerate
   
   // round 10
   final_round round_10(
        .clk(clk),
        .rst_n(rst_n),
        .valid_in(valid_array[9]),
        .state_in(state_array[1279:1152]),
        .keyin(roundkey_array[1279:1152]),
        .round_rcon({rcon[10], 24'h000000}),
        .state_out(ciphertext),
        .keyout(),
        .valid_out(valid_out)
   );    
endmodule