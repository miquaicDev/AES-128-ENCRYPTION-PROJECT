//(không đặt iv_load và valid_in cùng chu kỳ)
module aes_ctr_mode #(
    parameter AES_LATENCY = 21 // aes_core latency (sample valid_in -> valid_out=1)
)(
    input clk,
    input rst_n,
    input iv_load,
    input [127:0] iv,
    input [127:0] key,
    input valid_in,
    input [127:0] data_in, // plaintext (encrypt) or ciphertext (decrypt)
    output reg [127:0] data_out,
    output reg valid_out
);
    reg  [127:0] ctr_reg;
    wire [127:0] ctr_next = ctr_reg + 128'd1; // increase 128-bit counter
    // GCM mode (only increment 32 bit low):
    // wire [127:0] ctr_next = {ctr_reg[127:32], ctr_reg[31:0] + 32'd1};
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)
            ctr_reg <= 128'd0;
        else if (iv_load)
            ctr_reg <= iv;
        else if (valid_in)
            ctr_reg <= ctr_next;
    end

    wire [127:0] keystream;
    wire         ks_valid;
    aes_core u_aes_core (
        .clk       (clk),
        .rst_n     (rst_n),
        .valid_in  (valid_in),
        .plaintext (ctr_reg),
        .primekey  (key),
        .ciphertext(keystream),
        .valid_out (ks_valid)
    );
    reg [127:0] dly [0:AES_LATENCY-1];
    integer k;
    always @(posedge clk) begin
        dly[0] <= data_in;
        for (k = 1; k < AES_LATENCY; k = k + 1)
            dly[k] <= dly[k-1];
    end
    
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            data_out  <= 128'd0;
            valid_out <= 1'b0;
        end else begin
            valid_out <= ks_valid;
            data_out  <= keystream ^ dly[AES_LATENCY-1];
        end
    end

endmodule
