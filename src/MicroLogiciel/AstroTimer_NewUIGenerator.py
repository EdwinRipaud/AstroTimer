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
    def __init__(self, title:str, options:list, keys:dict, callbacks:list):
        self.title = title
        self.options = options
        self.keys = keys
        self.keys_callbacks = {'menu_up':self.menu_up, 'menu_down': self.menu_down, 'select': self.select}
        self.menu_callbacks = callbacks["menu_callbacks"]
        
        self.current_option = 0
        self.default_icon = Image.open("assets/Icon_Empty.png")
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {
            key: self.keys_callbacks[key] if key in self.keys_callbacks else callbacks["keys_callbacks"][key]
            for key in list(self.keys_callbacks.keys())+list(callbacks["keys_callbacks"].keys())
            }
        
        # read config_general.json file to initialise parameters
        with open('config_general.json', 'r') as f:
            self.config =  json.load(f)
        
        # Set fonts dictionary
        self.FONTS = {key: ImageFont.truetype(self.PATH_FONTS + data['path'], data['size']) for key, data in self.config["fonts"].items()}
        
        # Set battery icon dictionary
        self.BATTERY_DICT = {data: f"{self.PATH_ASSETS}{key}" for key, data in self.config["battery_icons"].items()}
        
        # Initialise LCD class
        self.LCD = LCD_1inch47.LCD_1inch47(**self.config["display"])
        
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
            
            option_font = self.FONTS["PixelOperator_M"] if i != 1 else self.FONTS["PixelOperatorBold_M"]
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
        
        option_font = self.FONTS["PixelOperatorBold_M"]
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
        draw.text((8, 0), f"{self.STATUS_TXT}", fill=(255,255,255), font=self.FONTS["PixelOperatorMonoBold_M"])
        
        draw.rectangle([(254,0),(320,32)], fill=(64, 64, 64))
        asset_battery = Image.open(self._get_battery_icon())
        img_out.paste(asset_battery, (254, 2), asset_battery.convert("RGBA"))
        return img_out

    def navigate(self, direction):
        if direction in list(self.keys.keys()):
            if self.keys[direction] not in ['', 'none']:
                print(f"Callback function: {self.keys[direction]}")
                self.keys_callbacks[self.keys[direction]]()
        return None
    
    def menu_up(self):
        self.current_option = (self.current_option - 1) % len(self.options)
        self.display()
        return None
    
    def menu_down(self):
        self.current_option = (self.current_option + 1) % len(self.options)
        self.display()
        return None
    
    def select(self):
        action = self.options[self.current_option]["action"]
        if action not in ['', 'none']:
            print(f"Action: {action}")
            self.menu_callbacks[action](action)
        else:
            print("No action yet")
        return None
    
    def trigger_action(self, key):
        for option in self.options:
            if key in option.get("keys", []):
                action = option["action"]
                print(action)
                self.menu_callbacks[action]()
                break
        return None


class ParameterPage(Menu):
    def __init__(self, title, options, keys, callbacks, parameters):
        super().__init__(title, options, keys, callbacks)
        self.parameters = parameters
        return None
    
    def display(self):
        super().display()
        print("!!!!!!!!!! DISPLAYING !!!!!!!!!!!!")
        # Additional logic to display parameters
        img = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0, 0, 0, 255))
        draw = ImageDraw.Draw(img)
        y_position = 50 + len(self.options) * 30
        for param, value in self.parameters.items():
            draw.text((10, y_position), f"{param}: {value}", font=self.FONTS["PixelOperator_M"], fill=(255, 255, 255))
            y_position += 30
        
        self.LCD.screen_img = self.__draw_status_bar(img)
        self.LCD.ShowImage(show=True)
        return None
    
    def set_parameter(self, param, value):
        self.parameters[param] = value
        self.display()
        return None


class MenuManager:
    def __init__(self, UI_config_path):
        with open(UI_config_path, 'r') as f:
            self.menu_structure = json.load(f)
        
        self.menus = {}
        self.keys_callbacks = {
            "go_back": self.go_back,
            }
        self.menu_callbacks = {
            "main_menu": self.show_menu,
            "sequence_menu": self.show_menu,
            "shutdown_menu": self.show_menu,
            "coming_soon": self.show_menu
            }
        
        self.callbacks = {
            "keys_callbacks": self.keys_callbacks,
            "menu_callbacks": self.menu_callbacks
            }
        
        self.current_menu = None
        self.menu_stack = []
        self.load_menus()
        return None
    
    def load_menus(self):
        for menu_key, menu_data in self.menu_structure.items():
            if "parameters" in menu_data:
                print("jdebmfveibdhvbhefbhbbvsfhdqblhvbhfbdzehvbhbdz", menu_key)
                self.menus[menu_key] = ParameterPage(
                    menu_data["title"],
                    menu_data["options"],
                    menu_data["keys"],
                    self.callbacks,
                    menu_data["parameters"]
                )
            else:
                self.menus[menu_key] = Menu(
                    menu_data["title"],
                    menu_data["options"],
                    menu_data["keys"],
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
    def __init__(self, UI_config_path):
        self.menu_manager = MenuManager(UI_config_path)
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
        
        Intervallometer_V5_app = MainApp("config_UI_struct.json")
        Intervallometer_V5_app.run()
        
        logging.info(f"{SCRIPT_NAME}: Add shutdown script call")
        Intervallometer_V5_app.clean_stop()
        
    except KeyError:
        logging.info(f"{SCRIPT_NAME}: KeyError")
        Intervallometer_V5_app.clean_stop()
    except KeyboardInterrupt:
        logging.info(f"{SCRIPT_NAME}: KeyboardInterrupt")
        Intervallometer_V5_app.clean_stop()