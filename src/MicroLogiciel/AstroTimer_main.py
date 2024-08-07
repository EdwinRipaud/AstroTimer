#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 25 11:19:59 2024

@author: edwinripaud
"""

import os
import json
import logging
import logging.config
from PIL import Image, ImageFont

from lib import LCD_display
from lib.UI_generator import PageManager

abspath = os.path.abspath(__file__)
dirname = os.path.dirname(abspath)
os.chdir(dirname)

OPERATING_SYSTEM = os.uname()
RUN_ON_RPi = (OPERATING_SYSTEM.sysname == 'Linux') and (OPERATING_SYSTEM.machine in ['aarch64', 'armv6l'])

if RUN_ON_RPi:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
else:
    from pynput import keyboard

PATH_GENERAL_CONFIG = 'config_general.json'

logging.config.fileConfig('logging.conf')
app_logger = logging.getLogger('appLogger')
app_logger.info("New execution of the AstroTimer program")

# TODO: Add a settings for the loggings depth and max age
# TODO: Check the log at init to delete older logs


class MainApp:
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, UI_config_path:str)->None:
        self.class_logger.debug("initalise MainApp",
                                extra={'className':f"{self.__class__.__name__}:"})
        # read config_general.json file to initialise parameters
        with open(PATH_GENERAL_CONFIG, 'r') as f:
            self.general_config =  json.load(f)
        
        # Set default path for assets, fonts, wifi and website
        self._general_config = {key:path for key, path in self.general_config["paths"].items()}
        
        # Set default icon for bad icon request
        self._general_config['default_icon'] = Image.open(f"{self._general_config['PATH_ASSETS']}Icon_Empty.png")
        
        # Set update times
        self._general_config["UPDATE_TIMES"] = {key:data for key, data in self.general_config['update_times'].items()}
        
        # Set fonts dictionary
        self._general_config['FONTS'] = {key: ImageFont.truetype(self._general_config['PATH_FONTS'] + data['path'], data['size']) for key, data in self.general_config["fonts"].items()}
        
        # Set battery icon dictionary
        self._general_config['BATTERY_DICT'] = {data: f"{self._general_config['PATH_ASSETS']}{key}" for key, data in self.general_config["battery_icons"].items()}
        
        # Initialise LCD class
        self._general_config['LCD'] = LCD_display.LCD_1inch47(**self.general_config["display"])
        
        self.page_manager = PageManager(UI_config_path, self._general_config)
        self.page_manager.show_page("main_menu_page")#"sequence_parameter_page")#
        
        if RUN_ON_RPi:
            self.general_config['GPIO_5_way_switch'] = {value:key for key, value in self.general_config['GPIO_5_way_switch'].items()}
            for pin in self.general_config['GPIO_5_way_switch'].keys():
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.add_event_detect(pin, GPIO.FALLING, callback=self.on_press)
        else:
            self.listener = keyboard.Listener(on_press=self.on_press)
            self.listener.start()
        return None
    
    def on_press(self, key_name)->None:
        self.class_logger.debug("handle keys callbacks",
                                extra={'className':f"{self.__class__.__name__}:"})
        key = self.general_config['GPIO_5_way_switch'][key_name] if RUN_ON_RPi else key_name.name
        try:
            if self.page_manager.current_page._config['class'] == "MainMenuPage":
                if key == "left":
                    if self.page_manager.current_page:
                        self.page_manager.page_stack.append(self.page_manager.current_page)
                    self.page_manager.current_page = self.page_manager.pages["shutdown_page"]
                    self.page_manager.current_page.display()
                    return None
            self.page_manager.current_page.navigate(key)
        except AttributeError:
            pass
        return None
    
    def run(self)->None:
        self.class_logger.debug("Running the MainApp",
                                extra={'className':f"{self.__class__.__name__}:"})
        while not self.page_manager.QUIT:
            continue
        return None
    
    def clean_stop(self)->None:
        self.class_logger.debug("Cleanning MainApp",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.page_manager.current_page.LCD.ClearScreen()
        if RUN_ON_RPi:
            GPIO.cleanup()
        else:
            self.listener.stop()
        # tmp_file = self.page_manager.pages["sequence_running_page"].tmp_param_file
        # if os.path.isfile(tmp_file):
        #     os.remove(tmp_file)
        return None


if __name__ == '__main__':
    try:
        app_logger.debug("Instanciate App")
        Intervallometer_V5_app = MainApp("config_UI_struct.json")
        app_logger.debug("Run App")
        Intervallometer_V5_app.run()
        
        app_logger.debug("Quit App")
        Intervallometer_V5_app.clean_stop()
        
    except KeyError as e:
        app_logger.error(f"KeyError: {e}")
        Intervallometer_V5_app.clean_stop()
    except KeyboardInterrupt:
        app_logger.warning("KeyboardInterrupt")
        Intervallometer_V5_app.clean_stop()