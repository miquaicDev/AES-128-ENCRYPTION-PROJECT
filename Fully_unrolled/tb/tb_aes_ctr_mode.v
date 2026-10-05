`timescale 1ns/1ps
// Test 1: encrypt 4 block liên tiếp (1 block/chu kỳ)  -> so với ciphertext
// Test 2: decrypt (đưa ciphertext vào) có chèn bubble  -> so với plaintext
// Test 3: load lại IV và encrypt tiếp tục từ test 2
module tb_aes_ctr_mode;
    parameter CLK_PERIOD = 10;
    parameter NBLK = 4;
    reg clk;
    reg rst_n;
    reg iv_load;
    reg [127:0] iv;
    reg [127:0] key;
    reg valid_in;
    reg [127:0] data_in;
    wire [127:0] data_out;
    wire valid_out;

    aes_ctr_mode dut (
        .clk      (clk),
        .rst_n    (rst_n),
        .iv_load  (iv_load),
        .iv       (iv),
        .key      (key),
        .valid_in (valid_in),
        .data_in  (data_in),
        .data_out (data_out),
        .valid_out(valid_out)
    );
    initial clk = 0;
    always #(CLK_PERIOD/2) clk = ~clk;

    reg [127:0] pt   [0:NBLK-1];
    reg [127:0] ct   [0:NBLK-1];
    reg [127:0] KEY_V;
    reg [127:0] IV_V;
    reg [127:0] in_mem  [0:NBLK-1];
    reg [127:0] exp_mem [0:NBLK-1];

    initial begin
        KEY_V = 128'h2b7e151628aed2a6abf7158809cf4f3c;
        IV_V  = 128'hf0f1f2f3f4f5f6f7f8f9fafbfcfdfeff;

        pt[0] = 128'h6bc1bee22e409f96e93d7e117393172a;
        pt[1] = 128'hae2d8a571e03ac9c9eb76fac45af8e51;
        pt[2] = 128'h30c81c46a35ce411e5fbc1191a0a52ef;
        pt[3] = 128'hf69f2445df4f9b17ad2b417be66c3710;

        ct[0] = 128'h874d6191b620e3261bef6864990db6ce;
        ct[1] = 128'h9806f66b7970fdff8617187bb9fffdff;
        ct[2] = 128'h5ae4df3edbd5d35e5b4f09020db03eab;
        ct[3] = 128'h1e031dda2fbe03d1792170a0f3009cee;
    end

    integer out_cnt;
    integer err_cnt;
    integer total_checked;
    always @(posedge clk) begin
        if (rst_n && valid_out) begin
            if (out_cnt < NBLK) begin
                total_checked = total_checked + 1;
                if (data_out !== exp_mem[out_cnt]) begin
                    err_cnt = err_cnt + 1;
                    $display("[%0t] ERROR blk %0d: got %032h, exp %032h", $time, out_cnt, data_out, exp_mem[out_cnt]);
                end
                else begin
                    $display("[%0t] OK    blk %0d: %032h", $time, out_cnt, data_out);
                end
            end
            else begin
                err_cnt = err_cnt + 1;
                $display("[%0t] ERROR: valid_out thừa (blk %0d)", $time, out_cnt);
            end
            out_cnt = out_cnt + 1;
        end
    end


    task do_reset;
        begin
            rst_n    = 1'b0;
            iv_load  = 1'b0;
            iv       = 128'd0;
            key      = 128'd0;
            valid_in = 1'b0;
            data_in  = 128'd0;
            repeat (4) @(posedge clk);
            #1 rst_n = 1'b1;
            repeat (2) @(posedge clk);
        end
    endtask

    task load_iv;
        input [127:0] v;
        begin
            @(posedge clk); #1;
            iv_load = 1'b1;
            iv      = v;
            @(posedge clk); #1;
            iv_load = 1'b0;
            iv      = 128'd0;
        end
    endtask

    task send_blk;
        input [127:0] d;
        begin
            @(posedge clk); #1;
            valid_in = 1'b1;
            data_in  = d;
            key = KEY_V;
        end
    endtask

    task send_idle; //for bubble test
        begin
            @(posedge clk); #1;
            valid_in = 1'b0;
            data_in  = 128'hDEAD_BEEF_DEAD_BEEF_DEAD_BEEF_DEAD_BEEF; //trash
        end
    endtask

    // Đợi pipeline xả hết
    task drain;
        begin
            @(posedge clk); #1;
            valid_in = 1'b0;
            repeat (40) @(posedge clk);
        end
    endtask

    task check_phase;
        input [8*24-1:0] name;
        begin
            if (out_cnt != NBLK) begin
                err_cnt = err_cnt + 1;
                $display("ERROR %0s: nhận %0d block, kỳ vọng %0d", name, out_cnt, NBLK);
            end
        end
    endtask



    integer i;
    initial begin
        err_cnt       = 0;
        out_cnt       = 0;
        total_checked = 0;

        do_reset;

        //--------------------------------------------------------------
        // Test 1: Encrypt, 4 block liên tiếp
        //--------------------------------------------------------------
        $display("=== Test 1: encrypt back-to-back ===");
        for (i = 0; i < NBLK; i = i + 1) begin
            in_mem[i]  = pt[i];
            exp_mem[i] = ct[i];
        end
        out_cnt = 0;
        load_iv(IV_V);
        for (i = 0; i < NBLK; i = i + 1) begin
            send_blk(in_mem[i]);
        end
        drain;
        check_phase("Test1");

        //--------------------------------------------------------------
        // Test 2: Decrypt (ciphertext -> plaintext), có bubble
        //--------------------------------------------------------------
        $display("=== Test 2: decrypt với bubble ===");
        for (i = 0; i < NBLK; i = i + 1) begin
            in_mem[i]  = ct[i];
            exp_mem[i] = pt[i];
        end
        out_cnt = 0;
        load_iv(IV_V);
        send_blk(in_mem[0]);
        send_idle;
        send_idle;
        send_blk(in_mem[1]);
        send_blk(in_mem[2]);
        send_idle;
        send_blk(in_mem[3]);
        drain;
        check_phase("Test2");

        //--------------------------------------------------------------
        // Test 3: load IV giữa 2 test rồi encrypt liền sau đó
        //--------------------------------------------------------------
        $display("=== Test 3: load IV lại, encrypt ===");
        for (i = 0; i < NBLK; i = i + 1) begin
            in_mem[i]  = pt[i];
            exp_mem[i] = ct[i];
        end
        out_cnt = 0;
        load_iv(IV_V);
        for (i = 0; i < NBLK; i = i + 1) send_blk(in_mem[i]);
        drain;
        check_phase("Test3");

        //--------------------------------------------------------------
        // Kết quả
        //--------------------------------------------------------------
        $display("------------------------------------------");
        if (err_cnt == 0)
            $display("PASS: %0d block đúng, 0 lỗi", total_checked);
        else
            $display("FAIL: %0d lỗi", err_cnt);
        $display("------------------------------------------");
        $finish;
    end

    // Watchdog
    initial begin
        #(CLK_PERIOD * 5000);
        $display("TIMEOUT");
        $finish;
    end

    // Waveform
    initial begin
        $dumpfile("tb_aes_ctr_mode.vcd");
        $dumpvars(0, tb_aes_ctr_mode);
    end

endmodule



// // Test Vector của NIST (AES-128 CTR):

// // Key: 2b7e151628aed2a6abf7158809cf4f3c

// // IV ban đầu: f0f1f2f3f4f5f6f7f8f9fafbfcfdfeff

// // Block 1 Plaintext: 6bc1bee22e409f96e93d7e117393172a

// // -> Block 1 Ciphertext (Kỳ vọng): 874d6191b620e3261bef6864990db6ce

// // Block 2 Plaintext: ae2d8a571e03ac9c9eb76fac45af8e51

// // -> Block 2 Ciphertext (Kỳ vọng): 9806f66b7970fdff8617187bb9fffdff
//https://www.codertools.net/tools/aes.php