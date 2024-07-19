#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Jul 19 00:05:51 2024

@author: Er-berry
"""

import os
import logging
import logging.config
from smbus import SMBus

OPERATING_SYSTEM = os.uname()
RUN_ON_RPi = (OPERATING_SYSTEM.sysname == 'Linux') and (OPERATING_SYSTEM.machine in ['aarch64', 'armv6l'])

SCRIPT_NAME = __file__.split('/')[-1]

logging.config.fileConfig('logging.conf')
lib_logger = logging.getLogger('libLogger')
lib_logger.debug("Imported file")


class max17043:
    class_logger = logging.getLogger('classLogger')
    
    REGISTER_VCELL = 0X02
    REGISTER_SOC = 0X04
    REGISTER_MODE = 0X06
    REGISTER_VERSION = 0X08
    REGISTER_CONFIG = 0X0C
    REGISTER_COMMAND = 0XFE

    def __init__(self, busnum=1, address=0x36):
        self.class_logger.debug("initialise MAX17043 module",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.busnum = busnum
        self.i2c = SMBus(self.busnum)
        self.max17043Address = address

    def __str__(self):
        self.class_logger.debug("String representation of the MAX17043 values",
                                extra={'className':f"{self.__class__.__name__}:"})
        rs  = "i2c address is {}\n".format( self.max17043Address )
        rs += "i2c bus is {}\n".format( self.busnum )
        rs += "version is {}\n".format( self.getVersion() )
        rs += "vcell is {} v\n".format( self.getVCell() )
        rs += "soc is {} %\n".format( self.getSoc() )
        rs += "compensatevalue is {}\n".format( self.getCompensateValue() )
        rs += "alert threshold is {} %\n".format( self.getAlertThreshold() )
        rs += "in alert is {}".format( self.inAlert() )
        return rs

    def address(self):
        self.class_logger.debug(f"Return I2C address: {self.max17043Address}",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.max17043Address

    def reset(self):
        self.class_logger.debug("Reset module",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.__writeRegister(self.REGISTER_COMMAND,0x0054)

    def getVCell(self):
        self.class_logger.debug("Get voltage of the cell",
                                extra={'className':f"{self.__class__.__name__}:"})
        buf = self.__readRegister(self.REGISTER_VCELL)
        return (buf[0] << 4 | buf[1] >> 4) /1000.0

    def getSoc(self):
        self.class_logger.debug("Get state of charge of the cell",
                                extra={'className':f"{self.__class__.__name__}:"})
        buf = self.__readRegister(self.REGISTER_SOC)
        return (buf[0] + (buf[1] / 256.0) )

    def getVersion(self):
        self.class_logger.debug("Get version of the module",
                                extra={'className':f"{self.__class__.__name__}:"})
        buf = self.__readRegister(self.REGISTER_VERSION)
        return (buf[0] << 8 ) | (buf[1])

    def getCompensateValue(self):
        self.class_logger.debug("Get the compensation value",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__readConfigRegister()[0]

    def getAlertThreshold(self):
        self.class_logger.debug("Get alert level",
                                extra={'className':f"{self.__class__.__name__}:"})
        return ( 32 - (self.__readConfigRegister()[1] & 0x1f) )

    def setAlertThreshold(self, threshold):
        self.class_logger.debug("Set alert level",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.threshold = 32 - threshold if threshold < 32 else 32
        buf = self.__readConfigRegister()
        buf[1] = (buf[1] & 0xE0) | self.threshold
        self.__writeConfigRegister(buf)

    def inAlert(self):
        self.class_logger.debug("Check if module is in alert",
                                extra={'className':f"{self.__class__.__name__}:"})
        return (self.__readConfigRegister())[1] & 0x20

    def clearAlert(self):
        self.class_logger.debug("Clear the alert",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.__readConfigRegister()

    def quickStart(self):
        self.class_logger.debug("Quick restart the module",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.__writeRegister(self.REGISTER_MODE,0x4000)

    def __readRegister(self,address):
        self.class_logger.debug("Read register, return 2 bytearray of char",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.i2c.read_i2c_block_data(self.max17043Address, address, 2)

    def __readConfigRegister(self):
        self.class_logger.debug("Read config register, return 2 bytearray of char",
                                extra={'className':f"{self.__class__.__name__}:"})
        return self.__readRegister(self.REGISTER_CONFIG)

    def __writeRegister(self,address,buf):
        self.class_logger.debug("Write to register",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.i2c.write_word_data(self.max17043Address, address, buf)

    def __writeConfigRegister(self,buf):
        self.class_logger.debug("Write to config register",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.__writeRegister(self.REGISTER_CONFIG,buf)

    def deinit(self):
        self.class_logger.debug("Turn off module",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.i2c.close()
