# SPDX-FileCopyrightText: © 2024 Tiny Tapeout
# SPDX-License-Identifier: Apache-2.0

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge
from cocotb.triggers import ClockCycles
from cocotb.types import Logic
from cocotb.types import LogicArray

async def await_half_sclk(dut):
    """Wait for the SCLK signal to go high or low."""
    start_time = cocotb.utils.get_sim_time(units="ns")
    while True:
        await ClockCycles(dut.clk, 1)
        # Wait for half of the SCLK period (10 us)
        if (start_time + 100*100*0.5) < cocotb.utils.get_sim_time(units="ns"):
            break
    return

def ui_in_logicarray(ncs, bit, sclk):
    """Setup the ui_in value as a LogicArray."""
    return LogicArray(f"00000{ncs}{bit}{sclk}")

async def send_spi_transaction(dut, r_w, address, data):
    """
    Send an SPI transaction with format:
    - 1 bit for Read/Write
    - 7 bits for address
    - 8 bits for data
    
    Parameters:
    - r_w: boolean, True for write, False for read
    - address: int, 7-bit address (0-127)
    - data: LogicArray or int, 8-bit data
    """
    # Convert data to int if it's a LogicArray
    if isinstance(data, LogicArray):
        data_int = int(data)
    else:
        data_int = data
    # Validate inputs
    if address < 0 or address > 127:
        raise ValueError("Address must be 7-bit (0-127)")
    if data_int < 0 or data_int > 255:
        raise ValueError("Data must be 8-bit (0-255)")
    # Combine RW and address into first byte
    first_byte = (int(r_w) << 7) | address
    # Start transaction - pull CS low
    sclk = 0
    ncs = 0
    bit = 0
    # Set initial state with CS low
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 1)
    # Send first byte (RW + Address)
    for i in range(8):
        bit = (first_byte >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # Send second byte (Data)
    for i in range(8):
        bit = (data_int >> (7-i)) & 0x1
        # SCLK low, set COPI
        sclk = 0
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
        # SCLK high, keep COPI
        sclk = 1
        dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
        await await_half_sclk(dut)
    # End transaction - return CS high
    sclk = 0
    ncs = 1
    bit = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    await ClockCycles(dut.clk, 600)
    return ui_in_logicarray(ncs, bit, sclk)

@cocotb.test()
async def test_spi(dut):
    dut._log.info("Start SPI test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)

    dut._log.info("Test project behavior")
    dut._log.info("Write transaction, address 0x00, data 0xF0")
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0xF0)  # Write transaction
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 1000) 

    dut._log.info("Write transaction, address 0x01, data 0xCC")
    ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0xCC)  # Write transaction
    assert dut.uio_out.value == 0xCC, f"Expected 0xCC, got {dut.uio_out.value}"
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x30 (invalid), data 0xAA")
    ui_in_val = await send_spi_transaction(dut, 1, 0x30, 0xAA)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Read transaction (invalid), address 0x00, data 0xBE")
    ui_in_val = await send_spi_transaction(dut, 0, 0x30, 0xBE)
    assert dut.uo_out.value == 0xF0, f"Expected 0xF0, got {dut.uo_out.value}"
    await ClockCycles(dut.clk, 100)
    
    dut._log.info("Read transaction (invalid), address 0x41 (invalid), data 0xEF")
    ui_in_val = await send_spi_transaction(dut, 0, 0x41, 0xEF)
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x02, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 100)

    dut._log.info("Write transaction, address 0x04, data 0xCF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xCF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0xFF")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x00")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("Write transaction, address 0x04, data 0x01")
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x01)  # Write transaction
    await ClockCycles(dut.clk, 30000)

    dut._log.info("SPI test completed successfully")


# ----------------------------------------------------------------------------------
# Write your tests here

async def sample_pwm_signal(dut, signal, channel, cycles = 2):

    """
    Parameters:
    - signal: Signal being measured (e.g. dut.uo_out).
    - channel: PWM channel bit to measure (0-7).
    - cycles: Number of PWM cycles to sample.
    """

    # Get current bit value of signal channel
    def bit_val():
        return (int(signal.value) >> channel) & 1

    rising_edges = 0
    timeout_ns = 1e6
    start_time = cocotb.utils.get_sim_time(units='ns')

    # Check for HIGH signal; wait until LOW
    while bit_val() == 1:
            await RisingEdge(dut.clk)
            if cocotb.utils.get_sim_time(units="ns") - start_time > timeout_ns:
                return 0.0, 100.0   # signal never goes LOW

    # Check for LOW signal; start sampling on next edge
    while bit_val() == 0:
        await RisingEdge(dut.clk)
        if cocotb.utils.get_sim_time(units="ns") - start_time > timeout_ns:
            return 0.0, 0.0   # signal never goes HIGH


    # Always start sampling on rising edge
    t_0 = cocotb.utils.get_sim_time(units='ns')

    while rising_edges < cycles:

        # Check for HIGH signal
        while bit_val() == 1:
            await RisingEdge(dut.clk)
            if cocotb.utils.get_sim_time(units="ns") - t_0 > timeout_ns:
                return 0.0, 100.0   # signal never goes LOW
        
        # Measure falling edge for HIGH time
        t_falling_edge = cocotb.utils.get_sim_time(units='ns')


        # Check for LOW signal
        while bit_val() == 0:
            await RisingEdge(dut.clk)
            if cocotb.utils.get_sim_time(units="ns") - t_0 > timeout_ns:
                return 0.0, 0.0   # signal never goes HIGH
    
        # Measure rising edge for period time
        t_rising_edge = cocotb.utils.get_sim_time(units='ns')
        rising_edges += 1

        high_time = t_falling_edge - t_0        # Time between posedge/negedge
        period = t_rising_edge - t_0            # Time between two posedges


        tot_high_time += high_time
        tot_period += period

        t_0 = cocotb.utils.get_sim_time(units="ns")

    
    avg_high = tot_high_time / cycles
    avg_period = tot_period / cycles


    return 1e9/avg_period, (avg_high/avg_period) * 100




@cocotb.test()
async def test_pwm_freq(dut):

    # Measure time delay between posedges to find period within 1% error

    
    # Output Structure: 16-bit output: {uio_out[7:0], uo_out[7:0]}
    # Each bit/channel can be independently enabled for static output or PWM

    # Output Enable Bit | PWM Bit | Result Output
    #         0         |    x    |       0
    #         1         |    0    |       1
    #         1         |    1    |      PWM
    

    dut._log.info("Start PWM Frequency test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)


    # Set 50% duty cycle for sampling PWM freq.
    ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x80)


    # Set output enable & PWM bits for each channel on uo_out
    for i in range(8):

        ui_in_val = await send_spi_transaction(dut, 1, 0x00, 1 << i)
        ui_in_val = await send_spi_transaction(dut, 1, 0x02, 1 << i)
        freq, duty = await sample_pwm_signal(dut, dut.uo_out, i, 4)

        assert 2970 <= freq <= 3030, f"Expected freq. between 2970Hz - 3030Hz, got {freq} on channel {i}"

    # Reset uo_out registers
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0x00)
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x00)

    # Set output enable & PWM bits for each channel on uio_out
    for i in range(8):

        ui_in_val = await send_spi_transaction(dut, 1, 0x01, 1 << i)
        ui_in_val = await send_spi_transaction(dut, 1, 0x03, 1 << i)
        freq, duty = await sample_pwm_signal(dut, dut.uio_out, i, 4)
        
        assert 2970 <= freq <= 3030, f"Expected freq. between 2970Hz - 3030Hz, got {freq} on channel {i + 8}"

    # Reset uio_out registers
    ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0x00)
    ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x00)

    dut._log.info("PWM Frequency test completed successfully")


@cocotb.test()
async def test_pwm_duty(dut):

    # Measure time delay between posedge/negedge to find high time
    # Measure time delay between posedges to find period within 1% error

    dut._log.info("Start PWM Duty Cycle test")

    # Set the clock period to 100 ns (10 MHz)
    clock = Clock(dut.clk, 100, units="ns")
    cocotb.start_soon(clock.start())

    # Reset
    dut._log.info("Reset")
    dut.ena.value = 1
    ncs = 1
    bit = 0
    sclk = 0
    dut.ui_in.value = ui_in_logicarray(ncs, bit, sclk)
    dut.rst_n.value = 0
    await ClockCycles(dut.clk, 5)
    dut.rst_n.value = 1
    await ClockCycles(dut.clk, 5)
   

    # Set output enable & PWM bits for each channel on uio_out
    for i in range(8):

        ui_in_val = await send_spi_transaction(dut, 1, 0x00, 1 << i)
        ui_in_val = await send_spi_transaction(dut, 1, 0x02, 1 << i)

        # 0% duty cycle
        ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)
        freq, duty = await sample_pwm_signal(dut, dut.uo_out, i, 4)
        assert duty == 0.0, f"Expected duty cycle @ 0%, got {duty}% on channel {i}"

        # 50% duty cycle
        ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x80)
        freq, duty = await sample_pwm_signal(dut, dut.uo_out, i, 4)
        assert duty == 50.0, f"Expected duty cycle @ 50%, got {duty}% on channel {i}"

        # 100% duty cycle
        ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)
        freq, duty = await sample_pwm_signal(dut, dut.uo_out, i, 4)
        assert duty == 100.0, f"Expected duty cycle @ 100%, got {duty}% on channel {i}"

        # Reset
        ui_in_val = await send_spi_transaction(dut, 1, 0x00, 0x00)
        ui_in_val = await send_spi_transaction(dut, 1, 0x02, 0x00)


    # Set output enable & PWM bits for each channel on uio_out
    for i in range(8):

        ui_in_val = await send_spi_transaction(dut, 1, 0x01, 1 << i)
        ui_in_val = await send_spi_transaction(dut, 1, 0x03, 1 << i)

        # 0% duty cycle
        ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x00)
        freq, duty = await sample_pwm_signal(dut, dut.uio_out, i, 4)
        assert duty == 0.0, f"Expected duty cycle @ 0%, got {duty}% on channel {i+8}"

        # 50% duty cycle
        ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0x80)
        freq, duty = await sample_pwm_signal(dut, dut.uio_out, i, 4)
        assert duty == 50.0, f"Expected duty cycle @ 50%, got {duty}% on channel {i+8}"

        # 100% duty cycle
        ui_in_val = await send_spi_transaction(dut, 1, 0x04, 0xFF)
        freq, duty = await sample_pwm_signal(dut, dut.uio_out, i, 4)
        assert duty == 100.0, f"Expected duty cycle @ 100%, got {duty}% on channel {i+8}"

        # Reset
        ui_in_val = await send_spi_transaction(dut, 1, 0x01, 0x00)
        ui_in_val = await send_spi_transaction(dut, 1, 0x03, 0x00)
        

    dut._log.info("PWM Duty Cycle test completed successfully")


    
# ----------------------------------------------------------------------------------