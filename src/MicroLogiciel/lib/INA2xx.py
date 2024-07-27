#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jul 27 17:42:54 2024

@author: Er-berry
"""

import os
import time
import logging
import logging.config
from smbus import SMBus

OPERATING_SYSTEM = os.uname()
RUN_ON_RPi = (OPERATING_SYSTEM.sysname == 'Linux') and (OPERATING_SYSTEM.machine in ['aarch64', 'armv6l'])

SCRIPT_NAME = __file__.split('/')[-1]

logging.config.fileConfig('logging.conf')
lib_logger = logging.getLogger('libLogger')
lib_logger.debug("Imported file")


class INA219:
    """Class containing the INA219 functionality."""
    class_logger = logging.getLogger('classLogger')
    
    RANGE_16V = 0  # Range 0-16 volts
    RANGE_32V = 1  # Range 0-32 volts
    
    GAIN_1_40MV  = 0  # Maximum shunt voltage 40mV
    GAIN_2_80MV  = 1  # Maximum shunt voltage 80mV
    GAIN_4_160MV = 2  # Maximum shunt voltage 160mV
    GAIN_8_320MV = 3  # Maximum shunt voltage 320mV
    GAIN_AUTO    = -1  # Determine gain automatically
    
    ADC_9BIT    = 0  # 9-bit conversion time  84us.
    ADC_10BIT   = 1  # 10-bit conversion time 148us.
    ADC_11BIT   = 2  # 11-bit conversion time 2766us.
    ADC_12BIT   = 3  # 12-bit conversion time 532us.
    ADC_2SAMP   = 9  # 2 samples at 12-bit, conversion time 1.06ms.
    ADC_4SAMP   = 10  # 4 samples at 12-bit, conversion time 2.13ms.
    ADC_8SAMP   = 11  # 8 samples at 12-bit, conversion time 4.26ms.
    ADC_16SAMP  = 12  # 16 samples at 12-bit,conversion time 8.51ms
    ADC_32SAMP  = 13  # 32 samples at 12-bit, conversion time 17.02ms.
    ADC_64SAMP  = 14  # 64 samples at 12-bit, conversion time 34.05ms.
    ADC_128SAMP = 15  # 128 samples at 12-bit, conversion time 68.10ms.
    
    __REG_CONFIG       = 0x00
    __REG_SHUNTVOLTAGE = 0x01
    __REG_BUSVOLTAGE   = 0x02
    __REG_POWER        = 0x03
    __REG_CURRENT      = 0x04
    __REG_CALIBRATION  = 0x05
    
    __RST   = 15
    __BRNG  = 13
    __PG1   = 12
    __PG0   = 11
    __BADC4 = 10
    __BADC3 = 9
    __BADC2 = 8
    __BADC1 = 7
    __SADC4 = 6
    __SADC3 = 5
    __SADC2 = 4
    __SADC1 = 3
    __MODE3 = 2
    __MODE2 = 1
    __MODE1 = 0
    
    __OVF  = 1
    __CNVR = 2
    
    __BUS_RANGE  = [16, 32]
    __GAIN_VOLTS = [0.04, 0.08, 0.16, 0.32]
    
    __CONT_SH_BUS = 7
    
    __SHUNT_MILLIVOLTS_LSB  = 0.01  # 10uV
    __BUS_MILLIVOLTS_LSB    = 4  # 4mV
    __CALIBRATION_FACTOR    = 0.04096
    __MAX_CALIBRATION_VALUE = 0xFFFE  # Max value supported (65534 decimal)
    # In the spec (p17) the current LSB factor for the minimum LSB is
    # documented as 32767, but a larger value (100.1% of 32767) is used
    # to guarantee that current overflow can always be detected.
    __CURRENT_LSB_FACTOR    = 32800
    
    def __init__(self, busnum=1, address=0x42, max_expected_amps=None, shunt_ohms=10e-3):
        """Construct the class.
        
        Pass in the resistance of the shunt resistor and the maximum expected
        current flowing through it in your system.
        
        Arguments:
        shunt_ohms -- value of shunt resistor in Ohms (mandatory).
        max_expected_amps -- the maximum expected current in Amps (optional).
        busnum -- the I2C bus number for the device platform, defaults
            to 1 (optional)
        address -- the I2C address of the INA219, defaults
            to *0x42* (optional).
        """
        self.class_logger.debug("Initialise INA219 module",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._address = address
        self._i2c = SMBus(busnum)
        self._shunt_ohms = shunt_ohms
        self._max_expected_amps = max_expected_amps
        self._min_device_current_lsb = self._calculate_min_current_lsb()
        self._gain = None
        self._auto_gain_enabled = False
    
    def configure(self, voltage_range=RANGE_32V, gain=GAIN_AUTO,
                  bus_adc=ADC_12BIT, shunt_adc=ADC_12BIT):
        """Configure and calibrate how the INA219 will take measurements.
        
        Arguments:
        voltage_range -- The full scale voltage range, this is either 16V
            or 32V represented by one of the following constants;
            RANGE_16V, RANGE_32V (default).
        gain -- The gain which controls the maximum range of the shunt
            voltage represented by one of the following constants;
            GAIN_1_40MV, GAIN_2_80MV, GAIN_4_160MV,
            GAIN_8_320MV, GAIN_AUTO (default).
        bus_adc -- The bus ADC resolution (9, 10, 11, or 12-bit) or
            set the number of samples used when averaging results
            represent by one of the following constants; ADC_9BIT,
            ADC_10BIT, ADC_11BIT, ADC_12BIT (default),
            ADC_2SAMP, ADC_4SAMP, ADC_8SAMP, ADC_16SAMP,
            ADC_32SAMP, ADC_64SAMP, ADC_128SAMP
        shunt_adc -- The shunt ADC resolution (9, 10, 11, or 12-bit) or
            set the number of samples used when averaging results
            represent by one of the following constants; ADC_9BIT,
            ADC_10BIT, ADC_11BIT, ADC_12BIT (default),
            ADC_2SAMP, ADC_4SAMP, ADC_8SAMP, ADC_16SAMP,
            ADC_32SAMP, ADC_64SAMP, ADC_128SAMP
        """
        self.class_logger.debug("Configuring module",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.__validate_voltage_range(voltage_range)
        self._voltage_range = voltage_range
        
        if self._max_expected_amps is not None:
            if gain == self.GAIN_AUTO:
                self._auto_gain_enabled = True
                self._gain = self._determine_gain(self._max_expected_amps)
            else:
                self._gain = gain
        else:
            if gain != self.GAIN_AUTO:
                self._gain = gain
            else:
                self._auto_gain_enabled = True
                self._gain = self.GAIN_1_40MV
        
        self.class_logger.debug(f"Gain set to {self.__GAIN_VOLTS[self._gain]:.2f}V",
                                extra={'className':f"{self.__class__.__name__}:"})
        
        self.class_logger.debug(f'shunt ohms: {self._shunt_ohms:.3f}, '
                                f'bus max volts: {self.__BUS_RANGE[voltage_range]:.1f}, '
                                f'shunt volts max: {self.__GAIN_VOLTS[self._gain]:.2f}'
                                f'{self._max_expected_amps if self._max_expected_amps else 0:.3f}, '
                                f'VBUSCT BIT: {bus_adc:d}, VSHSCT BIT: {shunt_adc:d}',
                                extra={'className':f"{self.__class__.__name__}:"})
        
        self._calibrate(
            self.__BUS_RANGE[voltage_range], self.__GAIN_VOLTS[self._gain],
            self._max_expected_amps)
        self._configure(voltage_range, self._gain, bus_adc, shunt_adc)
    
    def voltage(self):
        """Return the bus voltage in volts."""
        self.class_logger.debug("Get bus voltage",
                                extra={'className':f"{self.__class__.__name__}:"})
        value = self._voltage_register()
        return float(value) * self.__BUS_MILLIVOLTS_LSB / 1000
    
    def supply_voltage(self):
        """Return the bus supply voltage in volts.
        
        This is the sum of the bus voltage and shunt voltage. A
        DeviceRangeError exception is thrown if current overflow occurs.
        """
        self.class_logger.debug("Get supply voltage",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.voltage() + (float(self.shunt_voltage()) / 1000)
    
    def current(self):
        """Return the bus current in milliamps.
        
        A DeviceRangeError exception is thrown if current overflow occurs.
        """
        self.class_logger.debug("Get bus current",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._handle_current_overflow()
        return self._current_register() * self._current_lsb * 1000
    
    def power(self):
        """Return the bus power consumption in milliwatts.
        
        A DeviceRangeError exception is thrown if current overflow occurs.
        """
        self.class_logger.debug("get bus power consumption",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._handle_current_overflow()
        return self._power_register() * self._power_lsb * 1000
    
    def shunt_voltage(self):
        """Return the shunt voltage in millivolts.
        
        A DeviceRangeError exception is thrown if current overflow occurs.
        """
        self.class_logger.debug("Get shunt voltage",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._handle_current_overflow()
        return self._shunt_voltage_register() * self.__SHUNT_MILLIVOLTS_LSB
    
    def sleep(self):
        """Put the INA219 into power down mode."""
        self.class_logger.debug("Put module into power down mode",
                                extra={'className':f"{self.__class__.__name__}:"})
        configuration = self._read_configuration()
        self._configuration_register(configuration & 0xFFF8)
        
    def wake(self):
        """Wake the INA219 from power down mode."""
        self.class_logger.debug("Wake module from power down mode",
                                extra={'className':f"{self.__class__.__name__}:"})
        configuration = self._read_configuration()
        self._configuration_register(configuration | 0x0007)
        # 40us delay to recover from powerdown (p14 of spec)
        time.sleep(0.00004)
        
    def current_overflow(self):
        """Return true if the sensor has detect current overflow.
        
        In this case the current and power values are invalid.
        """
        self.class_logger.debug("Get overlow flag value",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self._has_current_overflow()
    
    def reset(self):
        """Reset the INA219 to its default configuration."""
        self.class_logger.debug("Reset module to default configuration",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._configuration_register(1 << self.__RST)
    
    def is_conversion_ready(self):
        """Check if conversion of a new reading has occured."""
        self.class_logger.debug("Check if conversion of a new reading has occured",
                                extra={'className':f"{self.__class__.__name__}:"})
        cnvr = self._read_voltage_register() & self.__CNVR
        return (cnvr == self.__CNVR)
    
    def _handle_current_overflow(self):
        self.class_logger.debug("Handle current overflow",
                                extra={'className':f"{self.__class__.__name__}:"})
        if self._auto_gain_enabled:
            while self._has_current_overflow():
                self._increase_gain()
        else:
            if self._has_current_overflow():
                raise DeviceRangeError(self.__GAIN_VOLTS[self._gain])
    
    def _determine_gain(self, max_expected_amps):
        self.class_logger.debug("Detemine gain",
                                extra={'className':f"{self.__class__.__name__}:"})
        shunt_v = max_expected_amps * self._shunt_ohms
        if shunt_v > self.__GAIN_VOLTS[3]:
            raise ValueError(f'Expected amps {max_expected_amps:.2f}A, out of range, '
                             'use a lower value shunt resistor')
            
        gain = min(v for v in self.__GAIN_VOLTS if v > shunt_v)
        return self.__GAIN_VOLTS.index(gain)
    
    def _increase_gain(self):
        self.class_logger.debug('Current overflow detected - attempting to increase gain',
                                extra={'className':f"{self.__class__.__name__}:"})
        gain = self._read_gain()
        if gain < len(self.__GAIN_VOLTS) - 1:
            gain = gain + 1
            self._calibrate(self.__BUS_RANGE[self._voltage_range],
                            self.__GAIN_VOLTS[gain])
            self._configure_gain(gain)
            # 1ms delay required for new configuration to take effect,
            # otherwise invalid current/power readings can occur.
            time.sleep(0.001)
        else:
            self.logger.info('Device limit reach, gain cannot be increased')
            raise DeviceRangeError(self.__GAIN_VOLTS[gain], True)
    
    def _configure(self, voltage_range, gain, bus_adc, shunt_adc):
        self.class_logger.debug("Configuration values",
                                extra={'className':f"{self.__class__.__name__}:"})
        configuration = (
            voltage_range << self.__BRNG | gain << self.__PG0 |
            bus_adc << self.__BADC1 | shunt_adc << self.__SADC1 |
            self.__CONT_SH_BUS)
        self._configuration_register(configuration)
    
    def _calibrate(self, bus_volts_max, shunt_volts_max,
                   max_expected_amps=None):
        """
        Example of calibration which uses the highest precision
        for current measurement (0.1mA), at the expense of
        only supporting 16V at 5000mA max.
        
        VBUS_MAX = 16V
        VSHUNT_MAX = 0.16          (Assumes Gain 3, 160mV)
        RSHUNT = 0.02              (Resistor value in ohms)
        
        1. Determine max possible current
            MaxPossible_I = VSHUNT_MAX / RSHUNT
            MaxPossible_I = 8.0A
        
        2. Determine max expected current
            MaxExpected_I = 5.0A
        
        3. Calculate possible range of LSBs (Min = 15-bit, Max = 12-bit)
            MinimumLSB = MaxExpected_I/32767
            MinimumLSB = 0.0001529              (uA per bit)
            MaximumLSB = MaxExpected_I/4096
            MaximumLSB = 0.0012207              (uA per bit)
        
        4. Choose an LSB between the min and max values
            (Preferrably a roundish number close to MinLSB)
            CurrentLSB = 0.00016 (uA per bit)
        
        5. Compute the calibration register
            Cal = trunc (0.04096 / (Current_LSB * RSHUNT))
            Cal = 13434 (0x347a)
        
        6. Calculate the power LSB
            PowerLSB = 20 * CurrentLSB
            PowerLSB = 0.003 (3.048mW per bit
        
        7. Compute the maximum current and shunt voltage values before overflow
        
        8. Compute the Maximum Power
        """
        
        self.class_logger.info(f'calibrate called with: bus max volts: {bus_volts_max:.1f}V, '
                                f'max shunt volts: {shunt_volts_max:.2f}V, '
                                f'{max_expected_amps if max_expected_amps else 0:.3f}',
                                extra={'className':f"{self.__class__.__name__}:"})
        
        max_possible_amps = shunt_volts_max / self._shunt_ohms
        self.class_logger.info(f"max possible current: {max_possible_amps:.3f}",
                                extra={'className':f"{self.__class__.__name__}:"})
        
        self._current_lsb = self._determine_current_lsb(max_expected_amps, max_possible_amps)
        self.class_logger.info(f"current LSB: {self._current_lsb:.3e} A/bit",
                                extra={'className':f"{self.__class__.__name__}:"})
        
        self._power_lsb = self._current_lsb * 20
        self.class_logger.info(f"power LSB: {self._power_lsb:.3e} W/bit",
                                extra={'className':f"{self.__class__.__name__}:"})
        
        max_current = self._current_lsb * 32767
        self.class_logger.info(f"max current before overflow: {max_current:.4f}A",
                                extra={'className':f"{self.__class__.__name__}:"})
        
        max_shunt_voltage = max_current * self._shunt_ohms
        self.class_logger.info(f"max shunt voltage before overflow: {(max_shunt_voltage * 1000):.4f}mV",
                                extra={'className':f"{self.__class__.__name__}:"})
        
        calibration = int(self.__CALIBRATION_FACTOR / (self._current_lsb * self._shunt_ohms))
        self.class_logger.info(f"calibration: 0x{calibration:04x} ({calibration:d})",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._calibration_register(calibration)
        
    def _determine_current_lsb(self, max_expected_amps, max_possible_amps):
        self.class_logger.debug("Determine current LSB",
                                extra={'className':f"{self.__class__.__name__}:"})
        if max_expected_amps is not None:
            if max_expected_amps > round(max_possible_amps, 3):
                raise ValueError(f'Expected current {max_expected_amps:.3f}A is greater '
                                 f'than max possible current {max_possible_amps:.3f}A')
            self.class_logger.debug(f"max expected current: {max_expected_amps:.3f}A",
                                    extra={'className':f"{self.__class__.__name__}:"})
            if max_expected_amps < max_possible_amps:
                current_lsb = max_expected_amps / self.__CURRENT_LSB_FACTOR
            else:
                current_lsb = max_possible_amps / self.__CURRENT_LSB_FACTOR
        else:
            current_lsb = max_possible_amps / self.__CURRENT_LSB_FACTOR
            
        if current_lsb < self._min_device_current_lsb:
            current_lsb = self._min_device_current_lsb
        return current_lsb
    
    def _configuration_register(self, register_value):
        self.class_logger.debug(f"configuration: 0x{register_value:04x}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.__write_register(self.__REG_CONFIG, register_value)
        
    def _read_configuration(self):
        self.class_logger.debug("read configuration register",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__read_register(self.__REG_CONFIG)
    
    def _calculate_min_current_lsb(self):
        self.class_logger.debug("calculate minimum current LSB",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__CALIBRATION_FACTOR / (self._shunt_ohms * self.__MAX_CALIBRATION_VALUE)
        
    def _read_gain(self):
        configuration = self._read_configuration()
        gain = (configuration & 0x1800) >> self.__PG0
        self.class_logger.debug(f"gain is currently: {self.__GAIN_VOLTS[gain]:.2f}V",
                                extra={'className':f"{self.__class__.__name__}:"})
        return gain
    
    def _configure_gain(self, gain):
        configuration = self._read_configuration()
        configuration = configuration & 0xE7FF
        self._configuration_register(configuration | (gain << self.__PG0))
        self._gain = gain
        self.class_logger.debug(f"gain set to: {self.__GAIN_VOLTS[gain]:.2f}V",
                                extra={'className':f"{self.__class__.__name__}:"})
    
    def _calibration_register(self, register_value):
        self.class_logger.debug(f"calibration: 0x{register_value:04x}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.__write_register(self.__REG_CALIBRATION, register_value)
    
    def _has_current_overflow(self):
        self.class_logger.debug("get current overflow value",
                                extra={'className':f"{self.__class__.__name__}:"})
        ovf = self._read_voltage_register() & self.__OVF
        return (ovf == 1)
    
    def _voltage_register(self):
        self.class_logger.debug("voltage register",
                                extra={'className':f"{self.__class__.__name__}:"})
        register_value = self._read_voltage_register()
        return register_value >> 3
    
    def _read_voltage_register(self):
        self.class_logger.debug("read voltage register",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__read_register(self.__REG_BUSVOLTAGE)
    
    def _current_register(self):
        self.class_logger.debug("current register",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__read_register(self.__REG_CURRENT, True)
    
    def _shunt_voltage_register(self):
        self.class_logger.debug("shunt voltage register",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__read_register(self.__REG_SHUNTVOLTAGE, True)
    
    def _power_register(self):
        self.class_logger.debug("power register",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__read_register(self.__REG_POWER)
    
    def __validate_voltage_range(self, voltage_range):
        self.class_logger.debug("validate voltage register",
                                extra={'className':f"{self.__class__.__name__}:"})
        if voltage_range > len(self.__BUS_RANGE) - 1:
            raise ValueError('Invalid voltage range, must be one of: RANGE_16V, RANGE_32V')
            
    def __write_register(self, register, register_value):
        register_bytes = self.__to_bytes(register_value)
        self.class_logger.debug(f"write register 0x{register:02x}: 0x{register_value:04x} "
                                f"0b{f'{register_value:b}':0>16}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._i2c.write_i2c_block_data(self._address, register, register_bytes)
    
    def __read_register(self, register, negative_value_supported=False):
        value = self._i2c.read_word_data(self._address, register) & 0xFFFF
        # Convert as big endian (see p14 of the spec)
        value = ((value << 8) & 0xFF00) + (value >> 8)
        if negative_value_supported and value > 32767:
            value -= 65536
        self.class_logger.debug(f"read register 0x{register:02x}: 0x{value:04x} "
                                f"0b{f'{value:b}':0>16}",
                                extra={'className':f"{self.__class__.__name__}:"})
        return value
    
    def __to_bytes(self, register_value):
        return [(register_value >> 8) & 0xFF, register_value & 0xFF]


class INA226:
    """Class containing the INA226 functionality."""
    class_logger = logging.getLogger('classLogger')
    
    AVG_1BIT    = 0  # 1 samples at 16-bit
    AVG_4BIT    = 1
    AVG_16BIT   = 2
    AVG_64BIT   = 3
    AVG_128BIT  = 4
    AVG_256BIT  = 5
    AVG_512BIT  = 6
    AVG_1024BIT = 7
    
    VCT_140us_BIT  = 0
    VCT_204us_BIT  = 1
    VCT_332us_BIT  = 2
    VCT_588us_BIT  = 3
    VCT_1100us_BIT = 4
    VCT_2116us_BIT = 5
    VCT_4156us_BIT = 6
    VCT_8244us_BIT = 7
    
    __REG_CONFIG          = 0x00
    __REG_SHUNTVOLTAGE    = 0x01
    __REG_BUSVOLTAGE      = 0x02
    __REG_POWER           = 0x03
    __REG_CURRENT         = 0x04
    __REG_CALI            = 0x05
    __REG_MASK            = 0x06
    __REG_LIMIT           = 0x07
    __REG_MANUFACTURER_ID = 0XFE
    __REG_DIE_ID          = 0XFF
    
    __RST         = 15
    __AVG0        = 9
    __VBUSCT0     = 6
    __VSHCT0      = 3
    __MODE3       = 2
    __MODE2       = 1
    __MODE1       = 0
    __CONT_SH_BUS = 7
    
    __SOL  = 15  # Shunt Voltage Over-Voltage
    __SUL  = 14  # Shunt Voltage Under-Voltage
    __BOL  = 13  # Bus Voltage Over-Voltage
    __BUL  = 12  # Bus Voltage Under-Voltage
    __POL  = 11  # Power Over-Limit : invalid current and power data
    __CNVR = 10  # Conversion Ready : Alert pin to be asserted when the __CVRF is asserted
    __AFF  = 4  # Alert Function Flag :
    # determine if the Alert Function was the source
    # when an alert function and the Conversion Ready are both enabled
    # When the Alert Latch Enable bit is set to Latch mode, the Alert Function Flag bit clears only when the Mask/Enable
    # Register is read. When the Alert Latch Enable bit is set to Transparent mode, the Alert Function Flag bit is
    # cleared following the next conversion that does not result in an Alert condition
    
    __CVRF = 3  # Conversion Ready Flag : SET after complete, clear when write __REG_CONFIG or Read __REG_MASK
    # help coordinate one-shot or triggered conversions
    
    __OVF  = 2  # Math Overflow Flag
    __APOL = 1  # Alert Polarity bit; sets the Alert pin polarity
    __LEN  = 0  # Alert Latch Enable; configures the latching feature of the Alert pin and Alert Flag bit:
    # When the Alert Latch Enable bit is set to Transparent mode, the Alert pin and Flag bit
    # resets to the idle states when
    # the fault has been cleared. When the Alert Latch Enable bit is set to Latch mode, the Alert pin and Alert Flag bit
    # remains active following a fault until the Mask/Enable Register has been rea
    
    __BUS_RANGE             = 40.96  # HEX = 7FFF, LSB = 1.25 mV, Must to positive
    __GAIN_VOLTS            = 0.08192  # HEX = 7FFF, LSB = 2.5 uV, An MSB = '1' denotes a negative number.
    __SHUNT_MILLIVOLTS_LSB  = 0.0025
    __BUS_MILLIVOLTS_LSB    = 1.25
    __CALIBRATION_FACTOR    = 0.00512
    __MAX_CALIBRATION_VALUE = 0x7FFF  # Max value supported (32767 decimal)
    __MAX_CURRENT_VALUE     = 0x7FFF
    __CURRENT_LSB_FACTOR    = 32768

    def __init__(self, busnum=1, address=0x40, max_expected_amps=None, shunt_ohms=30e-3):
        """Construct the class.
        
        Pass in the resistance of the shunt resistor and the maximum expected
        current flowing through it in your system.
        
        Arguments:
        shunt_ohms -- value of shunt resistor in Ohms (mandatory).
        max_expected_amps -- the maximum expected current in Amps (optional).
        address -- the I2C address of the INA226, defaults
            to *0x40* (optional).
        """
        self.class_logger.debug("initialise INA226 module",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._address = address
        self._i2c = SMBus(busnum)
        self._shunt_ohms = shunt_ohms
        self._max_expected_amps = max_expected_amps
        self._min_device_current_lsb = self._calculate_min_current_lsb()
        
    def configure(self, avg_mode=AVG_1BIT, bus_ct=VCT_8244us_BIT, shunt_ct=VCT_8244us_BIT):
        """Configure and calibrate how the INA226 will take measurements.
        """
        self.class_logger.debug(f'shunt ohms: {self._shunt_ohms:.3f}, bus max volts: {self.__BUS_RANGE:.1f}, '
                                f'shunt volts max: {self.__GAIN_VOLTS:.2f}'
                                f'{self._max_expected_amps if self._max_expected_amps else 0:.3f}, '
                                f'VBUSCT BIT: {bus_ct:d}, VSHSCT BIT: {shunt_ct:d}',
                                extra={'className':f"{self.__class__.__name__}:"})
        
        self._calibrate(
            self.__BUS_RANGE, self.__GAIN_VOLTS,
            self._max_expected_amps)
        configuration = (
            avg_mode << self.__AVG0 | bus_ct << self.__VBUSCT0 |
            shunt_ct << self.__VSHCT0 | self.__CONT_SH_BUS | 1 << 14)
        self._configuration_register(configuration)
        
    def voltage(self):
        """Return the bus voltage in volts."""
        self.class_logger.debug("Get bus voltage",
                                extra={'className':f"{self.__class__.__name__}:"})
        value = self._voltage_register()
        return float(value) * self.__BUS_MILLIVOLTS_LSB / 1000
    
    def supply_voltage(self):
        """Return the bus supply voltage in volts.
        
        This is the sum of the bus voltage and shunt voltage. A
        DeviceRangeError exception is thrown if current overflow occurs.
        """
        self.class_logger.debug("Get supply voltage",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.voltage() + (float(self.shunt_voltage()) / 1000)
    
    def current(self):
        """Return the bus current in milliamps.
        
        A DeviceRangeError exception is thrown if current overflow occurs.
        """
        self.class_logger.debug("Get bus current",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._handle_current_overflow()
        return self._current_register() * self._current_lsb * 1000
    
    def power(self):
        """Return the bus power consumption in milliwatts.
        
        A DeviceRangeError exception is thrown if current overflow occurs.
        """
        self.class_logger.debug("Get bus power consumption",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._handle_current_overflow()
        return self._power_register() * self._power_lsb * 1000
    
    def shunt_voltage(self):
        """Return the shunt voltage in millivolts.
        
        A DeviceRangeError exception is thrown if current overflow occurs.
        """
        self.class_logger.debug("Get shunt voltage drop",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._handle_current_overflow()
        return self._shunt_voltage_register() * self.__SHUNT_MILLIVOLTS_LSB
    
    def sleep(self):
        """Put the INA226 into power down mode."""
        self.class_logger.debug("Put module into power down mode",
                                extra={'className':f"{self.__class__.__name__}:"})
        configuration = self._read_configuration()
        self._configuration_register(configuration & 0xFFF8)
        
    def wake(self, mode=__CONT_SH_BUS):
        """Wake the INA226 from power down mode."""
        self.class_logger.debug("Wake the module from power down",
                                extra={'className':f"{self.__class__.__name__}:"})
        configuration = self._read_configuration()
        self._configuration_register(configuration & 0xFFF8 | mode)
        
    def current_overflow(self):
        """Return true if the sensor has detect current overflow.
        
        In this case the current and power values are invalid.
        """
        self.class_logger.debug("Get current overflow flag",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self._has_current_overflow()
    
    def reset(self):
        """Reset the INA226 to its default configuration."""
        self._configuration_register(1 << self.__RST)
        
        self.class_logger.info(f"config register: 0x{self.__REG_CONFIG:02x}, "
                               f"value: 0x{self._read_configuration():04x}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.class_logger.info(f"Calibration: 0x{self.__REG_CALI:02x}, "
                               f"value: 0x{self.__read_register(self.__REG_CALI):04x}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.class_logger.info(f"mask register: 0x{self.__REG_MASK:02x}, "
                               f"value: 0x{self._read_mask_register():04x}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.class_logger.info(f"limit register: 0x{self.__REG_LIMIT:02x}, "
                               f"value: 0x{self._read_limit_register():04x}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.class_logger.info(f"manufacturer id: 0x{self.__REG_MANUFACTURER_ID:02x}, "
                               f"value: 0x{self._manufacture_id():04x}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.class_logger.info(f"die id: 0x{self.__REG_DIE_ID:02x}, "
                               f"value: 0x{self._die_id():04x}",
                                extra={'className':f"{self.__class__.__name__}:"})
        
    def set_low_battery(self, low_limit=3, high_level_trigger=True):
        self.class_logger.debug("Set low battery level",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._limit_register(int(low_limit * 1000 / self.__BUS_MILLIVOLTS_LSB))
        if high_level_trigger:
            self._mask_register(1 << 12 | 3)
        else:
            self._mask_register(1 << 12 | 1)
            
    def _calibrate(self, bus_volts_max, shunt_volts_max, max_expected_amps=None):
        self.class_logger.debug(f'calibrate called with: bus max volts: {bus_volts_max:.1f}V, '
                                f'max shunt volts: {shunt_volts_max:.2f}V, '
                                f'{max_expected_amps if max_expected_amps else 0:.3f}',
                                extra={'className':f"{self.__class__.__name__}:"})
        
        max_possible_amps = shunt_volts_max / self._shunt_ohms
        self.class_logger.debug(f"max possible current: {max_possible_amps:.2f}A",
                                extra={'className':f"{self.__class__.__name__}:"})
        
        self._current_lsb = self._determine_current_lsb(max_expected_amps, max_possible_amps)
        self.class_logger.debug(f"current LSB: {self._current_lsb:.3e} A/bit",
                                extra={'className':f"{self.__class__.__name__}:"})
        
        self._power_lsb = self._current_lsb * 25.2
        self.class_logger.debug(f"power LSB: {self._power_lsb:.3e} W/bit",
                                extra={'className':f"{self.__class__.__name__}:"})
        
        max_current = self._current_lsb * self.__MAX_CURRENT_VALUE
        self.class_logger.debug(f"max current before overflow: {max_current:.4f}A",
                                extra={'className':f"{self.__class__.__name__}:"})
        
        max_shunt_voltage = max_current * self._shunt_ohms
        self.class_logger.debug(f"max shunt voltage before overflow: {(max_shunt_voltage * 1000):.4f}mV",
                                extra={'className':f"{self.__class__.__name__}:"})
        
        calibration = int(self.__CALIBRATION_FACTOR / (self._current_lsb * self._shunt_ohms))
        self.class_logger.debug(f"calibration: {calibration:04x} ({calibration})",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._calibration_register(calibration)
    
    def _determine_current_lsb(self, max_expected_amps, max_possible_amps):
        self.class_logger.debug("Determine current LSB",
                                extra={'className':f"{self.__class__.__name__}:"})
        if max_expected_amps is not None:
            if max_expected_amps > round(max_possible_amps, 3):
                raise ValueError(f'Expected current {max_expected_amps:.3f}A is greater '
                                 f'than max possible current {max_possible_amps:.3f}A')
                
            self.class_logger.debug(f"max expected current: {max_expected_amps:.3f}A",
                                    extra={'className':f"{self.__class__.__name__}:"})
            if max_expected_amps < max_possible_amps:
                current_lsb = max_expected_amps / self.__CURRENT_LSB_FACTOR
            else:
                current_lsb = max_possible_amps / self.__CURRENT_LSB_FACTOR
        else:
            current_lsb = max_possible_amps / self.__CURRENT_LSB_FACTOR
        self.class_logger.debug(f"expected current LSB base on max_expected_amps: {current_lsb:.3e} A/bit",
                                extra={'className':f"{self.__class__.__name__}:"})
        if current_lsb < self._min_device_current_lsb:
            current_lsb = self._min_device_current_lsb
            self.class_logger.debug("current_lsb is less equal than min_device_current_lsb, use the latter",
                                    extra={'className':f"{self.__class__.__name__}:"})
        return current_lsb
    
    def _calculate_min_current_lsb(self):
        self.class_logger.debug("Calculate minimum current LSB",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__CALIBRATION_FACTOR / (self._shunt_ohms * self.__MAX_CALIBRATION_VALUE)
               
    def _has_current_overflow(self):
        self.class_logger.debug("Get overflow flag value",
                                extra={'className':f"{self.__class__.__name__}:"})
        ovf = self._read_mask_register() >> self.__OVF & 1
        return ovf
    
    def is_conversion_ready(self):
        """Check if conversion of a new reading has occured."""
        self.class_logger.debug("Check if conversion of a new reading has occured.",
                                extra={'className':f"{self.__class__.__name__}:"})
        cnvr = self._read_mask_register() >> self.__CVRF & 1
        return cnvr
    
    def is_low_battery(self):
        self.class_logger.debug("Check if battery is low",
                                extra={'className':f"{self.__class__.__name__}:"})
        bul = self._read_mask_register() >> self.__BUL & 1
        return bul
    
    def _handle_current_overflow(self):
        self.class_logger.debug("Handle current overflow",
                                extra={'className':f"{self.__class__.__name__}:"})
        if self._has_current_overflow():
            raise DeviceRangeError(self.__GAIN_VOLTS)
            
    def _configuration_register(self, register_value):
        self.class_logger.debug(f"configuration: 0x{register_value:04x}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.__write_register(self.__REG_CONFIG, register_value)
        
    def _read_configuration(self):
        self.class_logger.debug("Read configuration",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__read_register(self.__REG_CONFIG)
    
    def _voltage_register(self):
        self.class_logger.debug("Read voltage register",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__read_register(self.__REG_BUSVOLTAGE)
    
    def _current_register(self):
        self.class_logger.debug("read current register",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__read_register(self.__REG_CURRENT, True)
    
    def _shunt_voltage_register(self):
        self.class_logger.debug("Read shunt voltage register",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__read_register(self.__REG_SHUNTVOLTAGE, True)
    
    def _power_register(self):
        self.class_logger.debug("Read power consumption register",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__read_register(self.__REG_POWER)
    
    def _calibration_register(self, register_value):
        self.class_logger.debug(f"calibration: 0x{register_value:04x}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.__write_register(self.__REG_CALI, register_value)
        
    def _read_mask_register(self):
        self.class_logger.debug("Read mask register",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__read_register(self.__REG_MASK)
    
    def _mask_register(self, register_value):
        self.class_logger.debug(f"mask/enable: 0x{register_value:04x}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.__write_register(self.__REG_MASK, register_value)
        
    def _read_limit_register(self):
        return self.__read_register(self.__REG_LIMIT)
    
    def _limit_register(self, register_value):
        self.class_logger.debug(f"limit value: 0x{register_value:04x}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.__write_register(self.__REG_LIMIT, register_value)
        
    def _manufacture_id(self):
        self.class_logger.debug("Get manufacturer ID",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__read_register(self.__REG_MANUFACTURER_ID)
    
    def _die_id(self):
        self.class_logger.debug("Get die ID",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__read_register(self.__REG_DIE_ID)
    
    def to_bytes(self, register_value):
        return [(register_value >> 8) & 0xFF, register_value & 0xFF]
    
    def __write_register(self, register, register_value):
        register_bytes = self.to_bytes(register_value)
        self.class_logger.debug(f"write register 0x{register:02x}: 0x{register_value:04x} "
                                f"0b{f'{register_value:b}':0>16}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self._i2c.write_i2c_block_data(self._address, register, register_bytes)
        
    def __read_register(self, register, negative_value_supported=False):
        result = self._i2c.read_word_data(self._address, register) & 0xFFFF
        register_value = ((result << 8) & 0xFF00) + (result >> 8)
        if negative_value_supported:
            if register_value > 32767:
                register_value -= 65536
        self.class_logger.debug(f"read register 0x{register:02x}: 0x{register_value:04x} "
                                f"0b{f'{register_value:b}':0>16}",
                                extra={'className':f"{self.__class__.__name__}:"})
        return register_value


class DeviceRangeError(Exception):
    """Class containing the INA219 error functionality."""

    __DEV_RNG_ERR = ('Current out of range (overflow), '
                     'for gain %.2fV')
    
    def __init__(self, gain_volts, device_max=False):
        """Construct a DeviceRangeError."""
        msg = self.__DEV_RNG_ERR % gain_volts
        if device_max:
            msg = msg + ', device limit reached'
        super(DeviceRangeError, self).__init__(msg)
        self.gain_volts = gain_volts
        self.device_limit_reached = device_max
