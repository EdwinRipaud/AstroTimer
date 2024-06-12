#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sun Jun  9 11:17:20 2024

@author: Er-berry
"""

import os
import time
import json
import logging
import logging.config

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

def keep_track(taken=-1, remaining=-1):
    lib_logger.warning("Saving current parameters")
    keep_track_dict = {"taken":taken, "remaining":remaining}
    with open(tmp_file, 'w') as f:
        json.dump(keep_track_dict, f)
    return None


if RUN_ON_RPi:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PIN_SHUTTER, GPIO.OUT)
    GPIO.setup(PIN_FOCUS, GPIO.OUT)
    
    def run_sequence(exposure:dict, shots:dict, interval:dict, offset:dict):
        os.makedirs(os.path.dirname(tmp_file), exist_ok=True)
        try:
            offset_time = offset['value'] * UNIT_CONVERTER[offset['unit']]
            
            exposure_time = exposure['value'] * UNIT_CONVERTER[exposure['unit']]
            exposure_time += offset_time
            
            nb_shots = shots['value']
            
            interval_time = interval['value'] * UNIT_CONVERTER[interval['unit']]
        except KeyError as e:
            lib_logger.error(f"key error: unknown key '{e}'")
            return None
        
        lib_logger.info(f"Sequence parameters: exposure={exposure['value']}{exposure['unit']}, \
    shots={shots['value']}, interval={interval['value']}{interval['unit']}")
    
        keep_track(taken=0, remaining=nb_shots)
        
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
            keep_track(taken=k, remaining=nb_shots-k)
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
        keep_track(taken=k+1, remaining=0)
        time.sleep(offset_time)
        os.remove(tmp_file)
        return None
else:
    lib_logger.warning("Cannot run on a non-RaspberryPi board")
    def run_sequence(exposure:dict, shots:dict, interval:dict, offset:dict):
        lib_logger.error("Impossible to call run_sequence")
        return None


if __name__ == '__main__':
    tmp_param_file = "../tmp/sequence_parameters.tmp"
    if RUN_ON_RPi and os.path.isfile(tmp_param_file):
        lib_logger.info("Execute a sequence")
        with open(tmp_param_file, 'r') as f:
            sequence = json.load(f)
        
        run_sequence(**sequence['sequence_parameters'])
        
        GPIO.cleanup()
    else:
        lib_logger.warning("Nothing to do...")