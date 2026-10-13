`timescale 1ns/1ps
module tb_aes_core();
   reg clk, rst_n, valid_in;
   reg [127:0] plaintext;
   reg[127:0] primekey;
   wire[127:0] ciphertext;
   wire valid_out;
   aes_core dut(
        clk, rst_n, valid_in,
        plaintext, primekey,
        ciphertext, valid_out
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
        plaintext = 128'h3243f6a8885a308d313198a2e0370734;
        primekey  = 128'h2b7e151628aed2a6abf7158809cf4f3c;
        $display("-------------------plaintext-------------------");
        for(i=3; i>=0; i=i-1) begin
            $display(
                "|\t%02h\t||\t%02h\t||\t%02h\t||\t%02h\t|",
                plaintext[i*8+96 +: 8], plaintext[i*8+64 +: 8], plaintext[i*8+32 +: 8], plaintext[i*8 +: 8]
            );
        end
        $display("-------------------primekey-------------------");
        for(i=3; i>=0; i=i-1) begin
            $display(
                "|\t%02h\t||\t%02h\t||\t%02h\t||\t%02h\t|",
                primekey[i*8+96 +: 8], primekey[i*8+64 +: 8], primekey[i*8+32 +: 8], primekey[i*8 +: 8]
            );
        end
        @(negedge clk);
        valid_in = 1'b0;
        wait(valid_out);
        #1;
        $display("-------------------RESULT-------------------");
        for(i=3; i>=0; i=i-1) begin
            $display(
                "|\t%02h\t||\t%02h\t||\t%02h\t||\t%02h\t|",
                ciphertext[i*8+96 +: 8], ciphertext[i*8+64 +: 8], ciphertext[i*8+32 +: 8], ciphertext[i*8 +: 8]
            );
        end
        #100;
        $stop;
   end

endmodule