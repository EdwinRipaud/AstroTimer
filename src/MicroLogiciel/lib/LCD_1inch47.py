import os
import time
import logging
import numpy as np
from PIL import Image

OPERATING_SYSTEM = os.uname()

if OPERATING_SYSTEM.sysname == 'Linux' and OPERATING_SYSTEM.machine == 'aarch64':
    from . import lcdconfig


SCRIPT_NAME = __file__.split('/')[-1]

# PIL Image Transpose configuration
FLIP_LEFT_RIGHT = 0
FLIP_TOP_BOTTOM = 1
ROTATE_90       = 2
ROTATE_180      = 3
ROTATE_270      = 4
TRANSPOSE       = 5
TRANSVERSE     	= 6

class LCD_1inch47():
    
    
    def __init__(self, spi_bus=0, spi_device=0, spi_freq=40000000, rst=27, dc=25, bl=18, bl_freq=1000):
        if OPERATING_SYSTEM.sysname == 'Linux' and OPERATING_SYSTEM.machine == 'aarch64':
            self.instance = lcdconfig.RaspberryPi(spi_bus, spi_device, spi_freq, rst, dc, bl, bl_freq)
            self.Init()
        
        self.width = 172
        self.height = 320
        self.size = (self.width, self.height)
        self.__black_frame = Image.new(mode="RGBA", size=(self.height, self.width), color=(0, 0, 0, 255))
        self.screen_img = self.__black_frame
        return
    
    # called when an attribute is not found:
    def __getattr__(self, name):
        # assume it is implemented by self.instance
        return self.instance.__getattribute__(name)
    
    def _command(self, cmd):
        self.digital_write(self.DC_PIN, self.GPIO.LOW)
        self.spi_writebyte([cmd])
        return
        
    def _data(self, val):
        self.digital_write(self.DC_PIN, self.GPIO.HIGH)
        self.spi_writebyte([val])	
        return
    
    def _reset(self):
        """Reset the display"""
        self.GPIO.output(self.RST_PIN, self.GPIO.HIGH)
        time.sleep(0.01)
        self.GPIO.output(self.RST_PIN, self.GPIO.LOW)
        time.sleep(0.01)
        self.GPIO.output(self.RST_PIN, self.GPIO.HIGH)
        time.sleep(0.01)
        return
    
    def Init(self):
        """Initialize dispaly"""  
        self.module_init()
        self._reset()
        
        self._command(0x36)
        self._data(0x00)                 #self.data(0x00)
        
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
        return
    
    def SetWindows(self, Xstart, Ystart, Xend, Yend):
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
        self.screen_img = self.__black_frame
        return None
    
    def _imagePreProcessing(self, image):
        if image.size != (self.size):
            #print(f"Image need to be corrected: {image.size} != {self.size}")
            if (image.width in self.size) and (image.height in self.size):
                #print(f"Image has the good shape but needs to be rotated")
                image = image.transpose(ROTATE_270)
            else:
                #print(f"Image hasn't the right shape...")
                if (image.width == self.width):
                    #print(f"Image need to be cut along the height")
                    image = image.crop((0, 0, self.width, self.height))
                elif (image.width == self.height):
                    #print(f"Image need to be transpose and cut along the height")
                    image = image.transpose(ROTATE_270)
                    img_width, img_height = image.width, image.height
                    image = image.crop((img_width-self.width, img_height-self.height, img_width, img_height))
                elif (image.height == self.width):
                    #print(f"Image need to be transpose and cut along the width")
                    image = image.transpose(ROTATE_270)
                    img_width, img_height = image.width, image.height
                    image = image.crop((img_width-self.width, img_height-self.height, img_width, img_height))
                elif (image.height == self.height):
                    #print(f"Image need to be cut along the width")
                    img_width, img_height = image.width, image.height
                    image = image.crop((img_width-self.width, img_height-self.height, img_width, img_height))
                else:
                    logging.info(f"{SCRIPT_NAME}:class>>LCD_1inch47():_imagePreProcessing(): This message shouldn't appear...")
        #else:
            #print(f"Image can be display !")
        return image
    
    def ShowImage(self, image=None, show=False):
        """Set buffer to value of Python Imaging Library image."""
        """Write display buffer to physical display"""
        if not image:
            image = self.screen_img
        
        image = self._imagePreProcessing(image)
        
        imwidth, imheight = image.size
        if imwidth != self.width or imheight != self.height:
            raise ValueError('Image must be same dimensions as display \
                ({0}x{1}).' .format(self.width, self.height))
        if show:
                image.transpose(ROTATE_90).show()
        
        if OPERATING_SYSTEM.sysname == 'Linux' and OPERATING_SYSTEM.machine == 'aarch64':
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
        logging.info(f"{SCRIPT_NAME}:class>>LCD_1inch47():ClearScreen(): clear display and reset self.screen_img")
        self._reset_frame()
        if OPERATING_SYSTEM.sysname == 'Linux' and OPERATING_SYSTEM.machine == 'aarch64':
            self.clear(val=0x00)
            self.module_exit()
        return None
    
    def clear(self, val=0xff):
        """Clear contents of image buffer"""
        _buffer = [val]*(self.width * self.height * 2)
        self.SetWindows ( 0, 0, self.width, self.height)
        self.digital_write(self.DC_PIN,self.GPIO.HIGH)
        for i in range(0,len(_buffer),4096):
            self.spi_writebyte(_buffer[i:i+4096])
        return None
    

