// each session = each button pressing on de2
// each session generate one new nonce
// each nonce is combined with {session_counter, free_timer}
// session counter is increased after each button pressing
// free timer will be incremented every clk cycle
module nonce_generator (
    input  clk,      
    input  rst_n,    
    input  btn_record,
    output reg [95:0] nonce_out,
    output reg nonce_ready
);
    reg [31:0] session_count;
    reg [63:0] free_timer;
    reg prev_btn;
    wire [95:0] nonce_data = {session_count, free_timer};
    // rise detector
    wire btn_rise_detect = btn_record && !prev_btn;
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            nonce_out <= 0;
            nonce_ready <= 0;
            prev_btn <= 0;
            free_timer <= 0;
            session_count <= 0;
        
        end
        else begin
            prev_btn <= btn_record;
            nonce_ready <= 0;
            free_timer <= free_timer + 1;
            if(btn_rise_detect) begin  
                session_count <= session_count + 1;
                nonce_out <= nonce_data;
                nonce_ready <= 1;
            end // implicitly: else nonce_out <= nonce_out;
        end
    end

endmodule