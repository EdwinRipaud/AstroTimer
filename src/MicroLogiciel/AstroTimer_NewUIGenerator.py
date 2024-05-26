#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat May 25 11:19:59 2024

@author: edwinripaud
"""

import os
import json
import qrcode
import logging
import subprocess
import numpy as np
from lib import LCD_1inch47
from PIL import Image, ImageDraw, ImageFont

abspath = os.path.abspath(__file__)
dirname = os.path.dirname(abspath)
os.chdir(dirname)

OPERATING_SYSTEM = os.uname()
RUN_ON_RPi = (OPERATING_SYSTEM.sysname == 'Linux') and (OPERATING_SYSTEM.machine in ['aarch64', 'armv6l'])

if RUN_ON_RPi:
    import RPi.GPIO as GPIO
    GPIO.setmode(GPIO.BCM)
    USE_SCREEN = False
else:
    from pynput import keyboard
    USE_SCREEN = True


class Menu:
    # TODO: charge the config from a JSON file
    PATH_FONTS  = "fonts/"
    PATH_ASSETS = "assets/"
    def __init__(self, title:str, options:list, callbacks:list):
        self.title = title
        self.options = options
        self.callbacks = callbacks
        self.current_option = 0
        self.default_icon = Image.open("assets/Icon_Empty.png")
        # TODO: charge the config from a JSON file
        self.Font_PixelOperator_small           = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperator.ttf", 24)
        self.Font_PixelOperatorBold_small       = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperator-Bold.ttf", 24)
        self.Font_PixelOperatorMono_small       = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperatorMono.ttf", 24)
        self.Font_PixelOperatorMonoBold_small   = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperatorMono-Bold.ttf", 24)
        	
        self.Font_PixelOperator             = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperator.ttf", 32)
        self.Font_PixelOperatorBold         = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperator-Bold.ttf", 32)
        self.Font_PixelOperatorMono         = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperatorMono.ttf", 32)
        self.Font_PixelOperatorMonoBold     = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperatorMono-Bold.ttf", 32)
        # TODO: charge the config from a JSON file
        self.BATTERY_DICT = {90.:f"{self.PATH_ASSETS}Icon_battery_90.png",
                             75.:f"{self.PATH_ASSETS}Icon_battery_75.png",
                             55.:f"{self.PATH_ASSETS}Icon_battery_55.png",
                             35.:f"{self.PATH_ASSETS}Icon_battery_35.png",
                             25.:f"{self.PATH_ASSETS}Icon_battery_25.png",
                             15.:f"{self.PATH_ASSETS}Icon_battery_15.png",
                             7.5:f"{self.PATH_ASSETS}Icon_battery_7.5.png",
                             }
        # TODO: charge the config from a JSON file
        self.DISPLAY_DICT   = {'spi_bus'    : 0,
                               'spi_device' : 0,
                               'spi_freq'   : 40000000,
                               'rst'        : 27,
                               'dc'         : 25,
                               'bl'         : 18,
                               'bl_freq'    : 90,
                               }
        self.LCD = LCD_1inch47.LCD_1inch47(**self.DISPLAY_DICT)
        # TODO: charge the config from a JSON file
        self.BATTERY_LEVEL          = 47
        self.STATUS_TXT             = "Ready to GO !"
        return None
    
    def _get_battery_icon(self):
        auth_level = np.array(list(self.BATTERY_DICT.keys()))
        auth_level[::-1].sort()
        
        if self.BATTERY_LEVEL>auth_level[-1]:
            arg = np.argmax(auth_level<self.BATTERY_LEVEL)
        else:
            arg = -1
        return self.BATTERY_DICT[auth_level[arg]]
    
    def display(self):
        # Generate an image representing the menu
        img = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        
        # Add options with icons
        for i in range(min(3, len(self.options))):
            idx = (i-1+self.current_option)%len(self.options)
            option = self.options[idx]
            icon_path = option.get("icon", "assets/Icon_Empty.png")
            try:
                icon = Image.open(icon_path)
            except:
                icon = self.default_icon
            
            img.paste(icon, (4, 20 + i * 60))
            
            option_font = self.Font_PixelOperator_small if i != 1 else self.Font_PixelOperatorBold
            option_pos = (64, 30 + i * 60) if i != 1 else (64, 27 + i * 60)
            option_text = option["title"] if option["title"] != "" else "[empty title]"
            draw.text(option_pos, option_text, font=option_font, fill=(255, 255, 255))
        
        asset_selection = Image.open(f"{self.PATH_ASSETS}Selection.png")
        img.paste(asset_selection, (1, 76), asset_selection.convert("RGBA"))
        
        self.LCD.screen_img = self.__draw_status_bar(img)
        self.LCD.ShowImage(show=True)
        print(f"{self.title}: display()")
        return None
    
    def display_comming_soon(self):
        # Generate an image representing the menu
        img = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        
        icon = self.default_icon
        img.paste(icon, (120, 65))
        
        option_font = self.Font_PixelOperatorBold
        option_pos = (64, 120)
        option_text = "Comming soon"
        draw.text(option_pos, option_text, font=option_font, fill=(255, 255, 255))
        
        self.LCD.screen_img = self.__draw_status_bar(img)
        self.LCD.ShowImage(show=True)
        print(f"{self.title}: display_comming_soon()")
        return None
    
    def __draw_status_bar(self, img_in=None):
        if not img_in:
            logging.debug(f"{self.id_name}:Intervalometre(class):__draw_status_bar(): Create new black background image")
            img_out = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0, 0, 0, 255))
        else:
            img_out = img_in
        draw = ImageDraw.Draw(img_out)
        
        draw.rectangle([(0,0),(320,34)], fill=(0, 0, 0))
        draw.rectangle([(0,0),(320,32)], fill=(64, 64, 64))
        draw.text((8, 0), f"{self.STATUS_TXT}", fill=(255,255,255), font=self.Font_PixelOperatorMonoBold)
        
        draw.rectangle([(254,0),(320,32)], fill=(64, 64, 64))
        asset_battery = Image.open(self._get_battery_icon())
        img_out.paste(asset_battery, (254, 2), asset_battery.convert("RGBA"))
        return img_out

    def navigate(self, direction):
        # TODO: add keys and callbacks to JSON file
        if direction == "up":
            self.current_option = (self.current_option - 1) % len(self.options)
            self.display()
        elif direction == "down":
            self.current_option = (self.current_option + 1) % len(self.options)
            self.display()
        elif direction == "right":
            self.select()
        elif direction == "left":
            self.callbacks.get("back", lambda: None)()
        elif direction == "enter":
            self.select()
        elif direction in self.options[self.current_option]["keys"]:
            print("Callback special action: typicaly go to the selected menu")
            self.display()
        return None
    
    def select(self):
        action = self.options[self.current_option]["action"]
        print(f"Action: {action}")
        self.callbacks[action](action)
        return None
    
    def trigger_action(self, key):
        for option in self.options:
            if key in option.get("keys", []):
                action = option["action"]
                print(action)
                self.callbacks[action]()
                break
        return None


class ParameterPage(Menu):
    def __init__(self, name, options, callbacks, parameters):
        super().__init__(name, options, callbacks)
        self.parameters = parameters
        return None
    
    def display(self):
        super().display()
        # Additional logic to display parameters
        img = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        y_position = 50 + len(self.options) * 30
        for param, value in self.parameters.items():
            draw.text((10, y_position), f"{param}: {value}", font=self.Font_PixelOperator, fill=(255, 255, 255))
            y_position += 30
        
        self.LCD.screen_img = self.__draw_status_bar(img)
        self.LCD.ShowImage(show=True)
        return None
    
    def set_parameter(self, param, value):
        self.parameters[param] = value
        self.display()
        return None


class MenuManager:
    def __init__(self, config_path):
        with open(config_path, 'r') as f:
            self.menu_structure = json.load(f)
        
        self.menus = {}
        self.callbacks = {
            "main_menu": self.show_menu,
            "sequence_menu": self.show_menu,
            "shutdown_menu": self.show_menu,
            "coming_soon": self.show_menu,
            "back": self.go_back
        }
        
        self.current_menu = None
        self.menu_stack = []
        self.load_menus()
        return None
    
    def load_menus(self):
        for menu_key, menu_data in self.menu_structure.items():
            self.menus[menu_key] = Menu(
                menu_data["title"],
                menu_data["options"],
                self.callbacks
            )
        return None
    
    def show_menu(self, menu_key=None):
        if self.current_menu:
            self.menu_stack.append(self.current_menu)
        self.current_menu = self.menus[menu_key]
        if menu_key == "coming_soon":
            self.current_menu.display_comming_soon()
        else:
            self.current_menu.display()
        return None
    
    def save_parameters(self, _):
        # Logic to save parameters
        print("Parameters saved!")
        self.show_menu("submenu")
        return None
    
    def go_back(self):
        if self.menu_stack:
            self.current_menu = self.menu_stack.pop()
            self.current_menu.display()
        return None
    
    def exit(self):
        print("Exiting application")
        self.current_menu = None
        return None


class MainApp:
    def __init__(self, config_path):
        self.menu_manager = MenuManager(config_path)
        self.menu_manager.show_menu("main_menu")
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()
        # self.listener.join()
        self.QUIT = False
        return None
    
    def on_press(self, key):
        try:
            if self.menu_manager.current_menu.title == "Shutdown":
                if key.name == "enter":
                    self.QUIT = True
                    return None
            elif self.menu_manager.current_menu.title == "Main Menu":
                if key.name == "left":
                    if self.menu_manager.current_menu:
                        self.menu_manager.menu_stack.append(self.menu_manager.current_menu)
                    self.menu_manager.current_menu = self.menu_manager.menus["shutdown_menu"]
                    self.menu_manager.current_menu.display()
                    return None
            self.menu_manager.current_menu.navigate(key.name)
        except AttributeError:
            pass
        return None
    
    def run(self):
        logging.info("MainApp(class):run(): Running the MainApp(class)")
        while not self.QUIT:
            continue
        
        return None
    
    def clean_stop(self):
        logging.info("MainApp(class):clean_stop(): Cleanning MainApp(class)")
        self.menu_manager.current_menu.LCD.ClearScreen()
        self.QUIT = True
        self.listener.stop()
        return None


if __name__ == '__main__':
    SCRIPT_NAME = __file__.split('/')[-1]
    print(__file__)
    try:
        
        Intervallometer_V5_app = MainApp("menu_structure.json")
        Intervallometer_V5_app.run()
        
        logging.info(f"{SCRIPT_NAME}: Add shutdown script call")
        Intervallometer_V5_app.clean_stop()
        
    except KeyError:
        logging.info(f"{SCRIPT_NAME}: KeyError")
        Intervallometer_V5_app.clean_stop()
    except KeyboardInterrupt:
        logging.info(f"{SCRIPT_NAME}: KeyboardInterrupt")
        Intervallometer_V5_app.clean_stop()