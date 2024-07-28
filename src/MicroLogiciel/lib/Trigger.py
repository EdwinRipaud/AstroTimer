#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jun 15 14:33:31 2024

@author: Er-berry
"""

import os
import re
import time
import json
import logging
import logging.config
import filelock

OPERATING_SYSTEM = os.uname()
RUN_ON_RPi = (OPERATING_SYSTEM.sysname == 'Linux') and (OPERATING_SYSTEM.machine in ['aarch64', 'armv6l'])

SCRIPT_NAME = __file__.split('/')[-1]

logging.config.fileConfig('logging.conf')
lib_logger = logging.getLogger('libLogger')
lib_logger.debug("Imported file")

PIN_SHUTTER = 21
PIN_FOCUS = 20

UNIT_CONVERTER = {'s':1, 'ms':1e-3, 'us':1e-6}

tmp_file = "../tmp/running_parameters.tmp"
tmp_locker = "../tmp/tmp.lock"
lock = filelock.FileLock(tmp_locker)

def _keep_track(taken=-1, remaining=-1):
    lib_logger.info("Saving current parameters")
    keep_track_dict = {"taken":taken, "remaining":remaining}
    with lock:
        with open(tmp_file, 'w') as f:
            json.dump(keep_track_dict, f)
    return None

def _check_pattern(fmt, unit):
    patterns = [f'({unit})', f'({unit}{unit})', f'(*{unit})', f'(*{unit}{unit})']
    return any([pattern in fmt for pattern in patterns])

def time2str(seconds:float, fmt='(hh):(mm):(ss)'):
    """
    Generate a time formated string of the input timedelta

    Parameters
    ----------
    seconds : float
        Timedelta in seconds
    fmt : TYPE, optional
        Output string format type description.
            Example for seconds=5025.678
                 '(h):(m):(ss)' -> '1:23:45'
                 
                 '(hh)h (mm)min (ss)s' -> '01h 23min 45s'
                 
                 '(*hh)h (mm)min (ss.S)s' -> '1h 23min 45.678s'
            Example for seconds=78.9
                 '(h):(m):(ss)' -> '0:1:28.900'
                 
                 '(hh)h (mm)min (ss)s' -> '00h 01min 29s'
                 
                 '(*hh)h (mm)min (ss.S)s' -> '01min 28.900s'
        The default is '(hh):(mm):(ss)'.

    Returns
    -------
    out : TYPE
        DESCRIPTION.

    """
    time_dict = {
        'h': seconds//3600,
        'm': seconds%3600//60 if _check_pattern(fmt, 'h') else seconds//60,
        's': (seconds%60)%60 if _check_pattern(fmt, 'm') else seconds,
    }
    
    out = ''
    for frmt in fmt.split('(')[1:]:
        unit, separator = frmt.split(')')
        
        n = re.findall('h|m|s', unit)
        t = time_dict[n[0]]
        if n:
            if not unit.find('*')>=0 or t!=0:
                leading = len(n) if len(n)<=2 else 5
                trailing = 0 if len(n)<=2 else 3
                out += f"{t:0{leading}.{trailing}f}{separator}"
    lib_logger.debug(f"({seconds}, {fmt}) -> {out}")
    return out


if RUN_ON_RPi:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN_SHUTTER, GPIO.OUT)
    GPIO.setup(PIN_FOCUS, GPIO.OUT)
    
    def execute_sequence(parameters:dict):
        os.makedirs(os.path.dirname(tmp_file), exist_ok=True)
        try:
            offset_time = parameters['offset']['value'] * UNIT_CONVERTER[parameters['offset']['unit']]
            
            exposure_time = parameters['exposure']['value'] * UNIT_CONVERTER[parameters['exposure']['unit']]
            exposure_time += offset_time
            
            nb_shots = parameters['shots']['value']
            
            interval_time = parameters['interval']['value'] * UNIT_CONVERTER[parameters['interval']['unit']]
        except KeyError as e:
            lib_logger.error(f"key error: unknown key '{e}'")
            return None
        
        lib_logger.info(f"Sequence parameters: exposure={parameters['exposure']['value']}{parameters['exposure']['unit']}, \
shots={parameters['shots']['value']}, interval={parameters['interval']['value']}{parameters['interval']['unit']}")
    
        _keep_track(taken=0, remaining=nb_shots)
        
        # Wake-up the camera
        GPIO.output(PIN_FOCUS, GPIO.HIGH)
        time.sleep(0.5*offset_time)
        GPIO.output(PIN_FOCUS, GPIO.LOW)
        time.sleep(0.5*offset_time)
        
        k=1
        for k in range(1, max(1, nb_shots)):
            lib_logger.info(f"Picture n°{k}/{nb_shots}")
            # Set pin high to take picture
            GPIO.output([PIN_FOCUS, PIN_SHUTTER],
                        [GPIO.HIGH, GPIO.HIGH])
            time.sleep(exposure_time)
            # Set pin low to save the picture
            GPIO.output([PIN_FOCUS, PIN_SHUTTER],
                        [GPIO.LOW, GPIO.LOW])
            _keep_track(taken=k, remaining=nb_shots-k)
            lib_logger.debug("sleep")
            time.sleep(interval_time)
        
        lib_logger.info(f"Picture n°{k+1}/{nb_shots}")
        # Take the last picture outside the loop to bypass the endding interval time
        GPIO.output([PIN_FOCUS, PIN_SHUTTER],
                    [GPIO.HIGH, GPIO.HIGH])
        time.sleep(exposure_time)
        # Leave pin low
        GPIO.output([PIN_FOCUS, PIN_SHUTTER],
                    [GPIO.LOW, GPIO.LOW])
        time.sleep(offset_time)
        return None
    
    def _release_gpio():
        lib_logger.debug("release GPIO pins")
        # Set pin state
        GPIO.output(PIN_FOCUS, GPIO.HIGH)
        GPIO.output(PIN_SHUTTER, GPIO.HIGH)
        time.sleep(50e-3)
        # Release pin
        GPIO.output(PIN_FOCUS, GPIO.LOW)
        GPIO.output(PIN_SHUTTER, GPIO.LOW)
        time.sleep(50e-3)
        return None
else:
    lib_logger.warning("Cannot trigger sequence on a non-RaspberryPi board")
    def execute_sequence(parameters:dict):
        lib_logger.error("Impossible to run execute_sequence()")
        lib_logger.info(f"Input parameters: {parameters}")
        return None
    
    def _release_gpio():
        lib_logger.error("Impossible to run _release_gpio()")
        return None