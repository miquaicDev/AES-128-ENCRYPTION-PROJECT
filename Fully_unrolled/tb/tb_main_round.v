`timescale 1ns/1ps
module tb_main_round();
   reg clk, rst_n, valid_in;
   reg [127:0] state_in;
   reg [127:0] keyin;
   reg [31:0]round_rcon;
   wire[127:0] state_out;
   wire [127:0] keyout;
   wire valid_out;
   main_round main_round_dut (
        .clk(clk), 
        .rst_n(rst_n), 
        .valid_in(valid_in), 
        .state_in(state_in),
        .keyin(keyin), 
        .round_rcon(round_rcon), 
        .state_out(state_out), 
        .keyout(keyout), 
        .valid_out(valid_out)
    );
   initial clk=0;
   always #5 clk = ~clk;
   integer i;
   initial begin
        rst_n = 0;
        valid_in = 0;
        #20;
        @(negedge clk);
        rst_n = 1;
        valid_in = 1;
        state_in = 128'h193de3bea0f4e22b9ac68d2ae9f84808;
        keyin = 128'h2b7e151628aed2a6abf7158809cf4f3c;
        round_rcon = 32'h01000000;
        $display("-------------------state in-------------------");
        for(i=3; i>=0; i=i-1) begin
            $display(
                "|\t%02h\t||\t%02h\t||\t%02h\t||\t%02h\t|",
                state_in[i*8+96 +: 8], state_in[i*8+64 +: 8], state_in[i*8+32 +: 8], state_in[i*8 +: 8]
            );
        end
        $display("-------------------key in-------------------");
        for(i=3; i>=0; i=i-1) begin
            $display(
                "|\t%02h\t||\t%02h\t||\t%02h\t||\t%02h\t|",
                keyin[i*8+96 +: 8], keyin[i*8+64 +: 8], keyin[i*8+32 +: 8], keyin[i*8 +: 8]
            );
        end
        @(negedge clk);
        valid_in = 1'b0;
        
        wait(valid_out);
        #1;
        $display("-------------------state out-------------------");
        for(i=3; i>=0; i=i-1) begin
            $display(
                "|\t%02h\t||\t%02h\t||\t%02h\t||\t%02h\t|",
                state_out[i*8+96 +: 8], state_out[i*8+64 +: 8], state_out[i*8+32 +: 8], state_out[i*8 +: 8]
            );
        end
        $display("-------------------key out-------------------");
        for(i=3; i>=0; i=i-1) begin
            $display(
                "|\t%02h\t||\t%02h\t||\t%02h\t||\t%02h\t|",
                keyout[i*8+96 +: 8], keyout[i*8+64 +: 8], keyout[i*8+32 +: 8], keyout[i*8 +: 8]
            );
        end
        #100;
        $stop;
   end

endmodule