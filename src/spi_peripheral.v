`default_nettype none

module spi_peripheral #(
    parameter SYNC = 2
    )
    (
    input wire        clk,      // internal sys. clock
    input wire        rst_n,    // reset
    input wire        nCS,      // chip select
    input wire        COPI,     // input from controller
    input wire        SCLK,     // clock from controller

    output reg [7:0] en_reg_out_7_0,
    output reg [7:0] en_reg_out_15_8,
    output reg [7:0] en_reg_pwm_7_0,
    output reg [7:0] en_reg_pwm_15_8,
    output reg [7:0] pwm_duty_cycle
);

    reg [15:0] transaction;         // 16 bits per transaction -- 1 r/w bit + 7 addr bits + 8 data bits --
    reg [4:0] clk_edge_counter;     // track number of posedges -- ensure transaction lasts exactly 16 cycles --

    reg [SYNC-1:0] ff_sync_nCS;     // 2-ff synchronizers -- CDC --
    reg [SYNC-1:0] ff_sync_COPI;
    reg [SYNC-1:0] ff_sync_SCLK;

    always @(posedge clk or negedge rst_n) begin

        // reset state
        if(!rst_n) begin

            transaction <= 16'b0;
            clk_edge_counter <= 5'b0;

            ff_sync_nCS <= 0;
            ff_sync_COPI <= 0;
            ff_sync_SCLK <=0;

            en_reg_out_7_0 <= 8'b0;
            en_reg_out_15_8 <= 8'b0;
            en_reg_pwm_7_0 <= 8'b0;
            en_reg_pwm_15_8 <= 8'b0;

        end else begin

            // capture data -- {old bit, incoming bit} --
            ff_sync_nCS <= {ff_sync_nCS[SYNC-2:0], nCS};
            ff_sync_COPI <= {ff_sync_COPI[SYNC-2:0], COPI};
            ff_sync_SCLK <= {ff_sync_SCLK[SYNC-2:0], SCLK};

            // start transaction -- only on negedge of nCS --
            if(ff_sync_nCS == 2'b10) begin
                
                transaction <= 16'b0;
                clk_edge_counter <= 5'b0;

            end 

            // update transaction data -- only on posedge of SCLK & nCS still low --
            else if(ff_sync_nCS == 2'b00 && ff_sync_SCLK == 2'b01) begin

                if(clk_edge_counter != 5'b10000) begin
                    transaction[15-clk_edge_counter] <= ff_sync_COPI[SYNC-1]; 
                    clk_edge_counter <=  clk_edge_counter + 1;
                end
            end

            
            // set outputs -- if write bit enabled & transaction finished --
            if(clk_edge_counter == 5'b10000 && transaction[15] == 1'b1) begin

                // check addresses
                case (transaction[14:8])

                    7'h00: en_reg_out_7_0 <= transaction[7:0];
                    7'h01: en_reg_out_15_8 <= transaction[7:0];
                    7'h02: en_reg_pwm_7_0 <= transaction[7:0];
                    7'h03: en_reg_pwm_15_8 <= transaction[7:0];
                    7'h04: pwm_duty_cycle <= transaction[7:0];

                    // ignore invalid addresses
                    default: ;
                endcase
            end 
        end
    end

endmodule