# /*****************************************************************************
# * | File        :	  lpdconfig.py
# * | Author      :   Waveshare team
# * | Function    :   Hardware underlying interface
# * | Info        :
# *----------------
# * | This version:   V1.0
# * | Date        :   2019-06-21
# * | Info        :   
# ******************************************************************************
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documnetation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to  whom the Software is
# furished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS OR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import time
import spidev
import logging
import logging.config

SCRIPT_NAME = __file__.split('/')[-1]

logging.config.fileConfig('logging.conf')
lib_logger = logging.getLogger('libLogger')
lib_logger.debug("Imported file")

class RaspberryPi:
    class_logger = logging.getLogger('displayLogger')
    def __init__(self, spi_bus=0, spi_device=0, spi_freq=40000000, rst=27, dc=25, bl=18, bl_freq=1000):
        self.class_logger.debug("initialise display interface with RaspberryPi",
                                extra={'className':f"{self.__class__.__name__}:"})
        import RPi.GPIO
        self.RST_PIN    = rst
        self.DC_PIN     = dc
        self.BL_PIN     = bl
        self.SPEED      = spi_freq
        self.BL_freq    = bl_freq
        self.GPIO       = RPi.GPIO
        
        self.GPIO.setmode(self.GPIO.BCM)
        self.GPIO.setwarnings(False)
        self.GPIO.setup(self.RST_PIN, self.GPIO.OUT)
        self.GPIO.setup(self.DC_PIN, self.GPIO.OUT)
        self.GPIO.setup(self.BL_PIN, self.GPIO.OUT)
        self.GPIO.output(self.BL_PIN, self.GPIO.HIGH)
        #Initialize SPI
        self.SPI = spidev.SpiDev(spi_bus, spi_device)
        if self.SPI!=None :
            self.SPI.max_speed_hz = spi_freq
            self.SPI.mode = 0b00
        return None
    
    def digital_write(self, pin, value):
        self.class_logger.info("set GPIO pin state",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.GPIO.output(pin, value)
        return None
    
    def digital_read(self, pin):
        self.class_logger.info("read GPIO pin state",
                               extra={'className':f"{self.__class__.__name__}:"})
        return self.GPIO.input(pin)

    def delay_ms(self, delaytime):
        self.class_logger.info("wait delay",
                               extra={'className':f"{self.__class__.__name__}:"})
        time.sleep(delaytime / 1000.0)
        return None
    
    def spi_writebyte(self, data):
        self.class_logger.info("write data to SPI bus",
                               extra={'className':f"{self.__class__.__name__}:"})
        if self.SPI!=None :
            self.SPI.writebytes(data)
        return None
    
    def set_bl_DutyCycle(self, duty):
        self.class_logger.info("set display backlight brightness",
                               extra={'className':f"{self.__class__.__name__}:"})
        self._pwm.ChangeDutyCycle(duty)
        return None
    
    def set_bl_Frequency(self,freq):
        self.class_logger.info("set display response time",
                               extra={'className':f"{self.__class__.__name__}:"})
        self._pwm.ChangeFrequency(freq)
        return None
    
    def module_init(self):
        self.class_logger.debug("initialise display backlight and SPI communication",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.GPIO.setup(self.RST_PIN, self.GPIO.OUT)
        self.GPIO.setup(self.DC_PIN, self.GPIO.OUT)
        self.GPIO.setup(self.BL_PIN, self.GPIO.OUT)
        self._pwm=self.GPIO.PWM(self.BL_PIN, self.BL_freq)
        self._pwm.start(100)
        if self.SPI!=None :
            self.SPI.max_speed_hz = self.SPEED
            self.SPI.mode = 0b00
        return None
    
    def module_exit(self):
        self.class_logger.debug("SPI end and GPIO cleanup",
                                extra={'className':f"{self.__class__.__name__}:"})
        if self.SPI!=None :
            self.SPI.close()
        
        self.GPIO.output(self.RST_PIN, 1)
        self.GPIO.output(self.DC_PIN, 0)
        self._pwm.stop()
        time.sleep(0.001)
        self.GPIO.output(self.BL_PIN, 1)
        return None
