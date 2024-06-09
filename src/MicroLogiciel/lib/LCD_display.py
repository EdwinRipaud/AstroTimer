import os
import time
import logging
import logging.config
import numpy as np
from PIL import Image

OPERATING_SYSTEM = os.uname()
RUN_ON_RPi = (OPERATING_SYSTEM.sysname == 'Linux') and (OPERATING_SYSTEM.machine in ['aarch64', 'armv6l'])



SCRIPT_NAME = __file__.split('/')[-1]

logging.config.fileConfig('logging.conf')
lib_logger = logging.getLogger('libLogger')
lib_logger.debug("Imported file")

# PIL Image Transpose configuration
FLIP_LEFT_RIGHT = 0
FLIP_TOP_BOTTOM = 1
ROTATE_90       = 2
ROTATE_180      = 3
ROTATE_270      = 4
TRANSPOSE       = 5
TRANSVERSE     	= 6


# TODO: add night vision mode to LCD with this code:
#   black_img = Image.new(mode="RGB", size=self.LCD.size[::-1], color=(0)).split()[0]
#   alpha_img = Image.new(mode="RGB", size=self.LCD.size[::-1], color=(255)).split()[0]
#   red_frame = Image.merge('RGBA', (self.LCD.screen_img.split()[0], black_img, black_img, alpha_img))
#   self.LCD.screen_img = Image.blend(self.LCD.screen_img, red_frame, alpha=0.6)

if RUN_ON_RPi:
    import spidev
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


class LCD_1inch47():
    class_logger = logging.getLogger('displayLogger')
    def __init__(self, spi_bus=0, spi_device=0, spi_freq=40000000, rst=27, dc=25, bl=18, bl_freq=1000):
        self.class_logger.info("initialise LCD_1inch47 display",
                               extra={'className':f"{self.__class__.__name__}:"})
        if RUN_ON_RPi:
            self.instance = RaspberryPi(spi_bus, spi_device, spi_freq, rst, dc, bl, bl_freq)
            self.Init()
        
        self.width = 172
        self.height = 320
        self.size = (self.width, self.height)
        self.__black_frame = Image.new(mode="RGBA", size=(self.height, self.width), color=(0, 0, 0, 255))
        self.screen_img = self.__black_frame
        return None
    
    def __getattr__(self, name):
        self.class_logger.debug("attribute not found",
                                extra={'className':f"{self.__class__.__name__}:"})
        # assume it is implemented by self.instance
        return self.instance.__getattribute__(name)
    
    def _command(self, cmd):
        self.class_logger.debug("send command to display via SPI",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.digital_write(self.DC_PIN, self.GPIO.LOW)
        self.spi_writebyte([cmd])
        return None
        
    def _data(self, val):
        self.class_logger.debug("send data to display via SPI",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.digital_write(self.DC_PIN, self.GPIO.HIGH)
        self.spi_writebyte([val])
        return None
    
    def _reset(self):
        self.class_logger.debug("reset display",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.GPIO.output(self.RST_PIN, self.GPIO.HIGH)
        time.sleep(0.01)
        self.GPIO.output(self.RST_PIN, self.GPIO.LOW)
        time.sleep(0.01)
        self.GPIO.output(self.RST_PIN, self.GPIO.HIGH)
        time.sleep(0.01)
        return None
    
    def Init(self):
        self.class_logger.info("initialise display",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.instance.module_init()
        self._reset()
        
        self._command(0x36)
        self._data(0x00)
        
        self._command(0x3A)
        self._data(0x05)
        
        self._command(0xB2)
        self._data(0x0C)
        self._data(0x0C)
        self._data(0x00)
        self._data(0x33)
        self._data(0x33)
        
        self._command(0xB7)
        self._data(0x35)
        
        self._command(0xBB)
        self._data(0x35)
        
        self._command(0xC0)
        self._data(0x2C)
        
        self._command(0xC2)
        self._data(0x01)
        
        self._command(0xC3)
        self._data(0x13)
        
        self._command(0xC4)
        self._data(0x20)
        
        self._command(0xC6)
        self._data(0x0F)
        
        self._command(0xD0)
        self._data(0xA4)
        self._data(0xA1)
        
        self._command(0xE0)
        self._data(0xF0)
        self._data(0xF0)
        self._data(0x00)
        self._data(0x04)
        self._data(0x04)
        self._data(0x04)
        self._data(0x05)
        self._data(0x29)
        self._data(0x33)
        self._data(0x3E)
        self._data(0x38)
        self._data(0x12)
        self._data(0x12)
        self._data(0x28)
        self._data(0x30)
        
        self._command(0xE1)
        self._data(0xF0)
        self._data(0x07)
        self._data(0x0A)
        self._data(0x0D)
        self._data(0x0B)
        self._data(0x07)
        self._data(0x28)
        self._data(0x33)
        self._data(0x3E)
        self._data(0x36)
        self._data(0x14)
        self._data(0x14)
        self._data(0x29)
        self._data(0x32)
        
        self._command(0x21)
        
        self._command(0x11)
        
        self._command(0x29)
        return None
    
    def SetWindows(self, Xstart, Ystart, Xend, Yend):
        self.class_logger.info("set display view windows",
                               extra={'className':f"{self.__class__.__name__}:"})
        #set the X coordinates
        self._command(0x2A)
        self._data((Xstart)>>8& 0xff)     #Set the horizontal starting point to the high octet
        self._data((Xstart+34)   & 0xff)  #Set the horizontal starting point to the low octet
        self._data((Xend-1+34)>>8& 0xff)  #Set the horizontal end to the high octet
        self._data((Xend-1+34)   & 0xff)  #Set the horizontal end to the low octet 
        
        #set the Y coordinates
        self._command(0x2B)
        self._data((Ystart)>>8& 0xff)
        self._data((Ystart)   & 0xff)
        self._data((Yend-1)>>8& 0xff)
        self._data((Yend-1)   & 0xff)
        
        self._command(0x2C)
        return None
        
    def _reset_frame(self):
        self.class_logger.debug("reset current frame",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.screen_img = self.__black_frame
        return None
    
    def _imagePreProcessing(self, image):
        self.class_logger.info("pre_process frame to fit display",
                               extra={'className':f"{self.__class__.__name__}:"})
        if image.size != (self.size):
            self.class_logger.debug(f"Image need to be corrected: {image.size} != {self.size}",
                                   extra={'className':f"{self.__class__.__name__}:"})
            if (image.width in self.size) and (image.height in self.size):
                self.class_logger.debug("Image has the good shape but needs to be rotated",
                                       extra={'className':f"{self.__class__.__name__}:"})
                image = image.transpose(ROTATE_270)
            else:
                self.class_logger.debug("Image hasn't the right shape...",
                                       extra={'className':f"{self.__class__.__name__}:"})
                if (image.width == self.width):
                    self.class_logger.debug("Image need to be cut along the height",
                                           extra={'className':f"{self.__class__.__name__}:"})
                    image = image.crop((0, 0, self.width, self.height))
                elif (image.width == self.height):
                    self.class_logger.debug("Image need to be transpose and cut along the height",
                                           extra={'className':f"{self.__class__.__name__}:"})
                    image = image.transpose(ROTATE_270)
                    img_width, img_height = image.width, image.height
                    image = image.crop((img_width-self.width, img_height-self.height, img_width, img_height))
                elif (image.height == self.width):
                    self.class_logger.debug("Image need to be transpose and cut along the width",
                                           extra={'className':f"{self.__class__.__name__}:"})
                    image = image.transpose(ROTATE_270)
                    img_width, img_height = image.width, image.height
                    image = image.crop((img_width-self.width, img_height-self.height, img_width, img_height))
                elif (image.height == self.height):
                    self.class_logger.debug("Image need to be cut along the width",
                                           extra={'className':f"{self.__class__.__name__}:"})
                    img_width, img_height = image.width, image.height
                    image = image.crop((img_width-self.width, img_height-self.height, img_width, img_height))
                else:
                    self.class_logger.warning("This message shouldn't appear...",
                                              extra={'className':f"{self.__class__.__name__}:"})
        return image
    
    def ShowImage(self, image=None, show=False):
        self.class_logger.info("display frame on screen",
                               extra={'className':f"{self.__class__.__name__}:"})
        if not image:
            image = self.screen_img
        
        image = self._imagePreProcessing(image)
        
        imwidth, imheight = image.size
        if imwidth != self.width or imheight != self.height:
            self.class_logger.error(f"Image must be same dimensions as display ({self.width}x{self.height}).",
                                    extra={'className':f"{self.__class__.__name__}:"})
            raise ValueError(f"Image must be same dimensions as display ({self.width}x{self.height}).")
        if show:
                image.transpose(ROTATE_90).show()
        
        if RUN_ON_RPi:
            img = np.asarray(image)
            pix = np.zeros((self.height,self.width,2), dtype = np.uint8)
            
            pix[...,[0]] = np.add(np.bitwise_and(img[...,[0]],0xF8),np.right_shift(img[...,[1]],5))
            pix[...,[1]] = np.add(np.bitwise_and(np.left_shift(img[...,[1]],3),0xE0),np.right_shift(img[...,[2]],3))
            
            pix = pix.flatten().tolist()
            self.SetWindows ( 0, 0, self.width, self.height)
            self.digital_write(self.DC_PIN,self.GPIO.HIGH)
            for i in range(0,len(pix),4096):
                self.spi_writebyte(pix[i:i+4096])
        return None
    
    def ClearScreen(self):
        self.class_logger.info("clear display and reset current frame",
                               extra={'className':f"{self.__class__.__name__}:"})
        self._reset_frame()
        if RUN_ON_RPi:
            self.clear(val=0x00)
            self.module_exit()
        return None
    
    def clear(self, val=0xff):
        self.class_logger.debug("clear frame buffer content",
                                extra={'className':f"{self.__class__.__name__}:"})
        _buffer = [val]*(self.width * self.height * 2)
        self.SetWindows ( 0, 0, self.width, self.height)
        self.digital_write(self.DC_PIN,self.GPIO.HIGH)
        for i in range(0,len(_buffer),4096):
            self.spi_writebyte(_buffer[i:i+4096])
        return None
