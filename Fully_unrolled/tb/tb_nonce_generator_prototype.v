module tb_nonce_generator();
    reg clk;    
    reg rst_n;
    reg btn_record;
    wire [95:0] nonce_out;
    wire nonce_ready;
    nonce_generator nonce_gen(
        .clk(clk),      
        .rst_n(rst_n),    
        .btn_record(btn_record),
        .nonce_out(nonce_out),
        .nonce_ready(nonce_ready)
    );
    initial clk = 0;
    always #5 clk = ~clk;

    initial begin
        rst_n = 0;
        btn_record = 0;
        repeat(4)@(negedge clk);
        rst_n = 1;
        repeat(4)@(negedge clk);
        btn_record = 1;
        #30;
        btn_record = 0; 
        #20;@(negedge clk);
        btn_record = 1;
        @(negedge clk);
        btn_record = 0;
        #100;
        $stop;
    end
    


endmodule