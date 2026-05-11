`timescale 1ns/1ps

module tb_aes_core();
    reg clk, rst_n, valid_in;
    reg [127:0] plaintext;
    reg [127:0] primekey;
    wire [127:0] ciphertext;
    wire valid_out;

    aes_core dut(
        .clk(clk), 
        .rst_n(rst_n), 
        .valid_in(valid_in),
        .plaintext(plaintext), 
        .primekey(primekey),
        .ciphertext(ciphertext), 
        .valid_out(valid_out)
    );

    initial clk = 0;
    always #5 clk = ~clk;

    localparam NUM_TESTS = 10;
    integer i, out_count;
    
    initial begin
        rst_n = 0;
        valid_in = 0;
        plaintext = 128'h0;
        primekey  = 128'h2b7e151628aed2a6abf7158809cf4f3c; //fixed test key
        #20;
        @(negedge clk);
        rst_n = 1;
        $display("================ B?T ??U B?M D? LI?U ================");
        for(i = 0; i < NUM_TESTS; i = i + 1) begin
            @(negedge clk);
            valid_in = 1'b1;
            plaintext = 128'h3243f6a8885a308d313198a2e0370734 + i; 
            $display("[%0t] INPUT: Encryption no %0d | PT: %h", $time, i+1, plaintext);
        end
        @(negedge clk);
        valid_in = 1'b0; 
    end
    
    initial begin
        out_count = 0;
        wait(rst_n == 1); 
        while (out_count < NUM_TESTS) begin
            @(posedge clk);
            if (valid_out) begin
                out_count = out_count + 1;
                $display("[%0t] OUTPUT: Cipher no %0d | CT: %h", $time, out_count, ciphertext);
            end
        end
        $display("================ TEST HOÀN T?T ================");
        #100;
        $stop;
    end
endmodule

//`timescale 1ns/1ps

//module tb_aes_core();
//    reg clk, rst_n, valid_in;
//    reg [127:0] plaintext;
//    reg [127:0] primekey;
//    wire [127:0] ciphertext;
//    wire valid_out;

//    aes_core dut(
//        .clk(clk), 
//        .rst_n(rst_n), 
//        .valid_in(valid_in),
//        .plaintext(plaintext), 
//        .primekey(primekey),
//        .ciphertext(ciphertext), 
//        .valid_out(valid_out)
//    );

//    initial clk = 0;
//    always #5 clk = ~clk;
//    localparam NUM_TESTS = 10;
//    integer i, out_count;

//    initial begin
//        rst_n = 0;
//        valid_in = 0;
//        plaintext = 128'h0;
//        primekey  = 128'h2b7e151628aed2a6abf7158809cf4f3c; // fixed key for easier testing
//        #20;
//        @(negedge clk);
//        rst_n = 1;

//        $display("================ B?T ??U TEST PIPELINE ================");

//        fork
//            begin
//                for(i = 0; i < NUM_TESTS; i = i + 1) begin
//                    @(negedge clk);
//                    valid_in = 1'b1;
//                    plaintext = 128'h3243f6a8885a308d313198a2e0370734 + i; 
//                    $display("[%0t] INPUT: G?i gói th? %0d | PT: %h", $time, i+1, plaintext);
//                end
//                @(negedge clk);
//                valid_in = 1'b0; 
//            end
//            begin
//                out_count = 0;
//                while (out_count < NUM_TESTS) begin
//                    @(posedge clk);
//                    if (valid_out) begin
//                        out_count = out_count + 1;
//                        $display("[%0t] OUTPUT: Nh?n k?t qu? %0d | CT: %h", $time, out_count, ciphertext);
//                    end
//                end
//            end
//        join

//        $display("================ TEST HOÀN T?T ================");
//        #100;
//        $stop;
//    end
//endmodule