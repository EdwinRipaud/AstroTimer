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
    BYPASS_BUILTIN_SCREEN = False
else:
    from pynput import keyboard
    BYPASS_BUILTIN_SCREEN = True

PATH_GENERAL_CONFIG = 'config_general.json'

logging.basicConfig(level=logging.INFO)


# TODO: add night vision mode to LCD with this code:
#   black_img = Image.new(mode="RGB", size=self.LCD.size[::-1], color=(0)).split()[0]
#   alpha_img = Image.new(mode="RGB", size=self.LCD.size[::-1], color=(255)).split()[0]
#   red_frame = Image.merge('RGBA', (self.LCD.screen_img.split()[0], black_img, black_img, alpha_img))
#   self.LCD.screen_img = Image.blend(self.LCD.screen_img, red_frame, alpha=0.6)


# TODO: Move all high level class to an other .py to keep main.py clear

# TODO: Make class Page() a generic class with only high level methodes
class Page:
    def __init__(self, page_config:dict):
        logging.info("Page.__init__(): initialise utils attributes for the page")
        
        self.title = page_config["title"]
        
        self.keys = page_config["keys"]
        
        # Set callbacks for navigation
        self.page_callbacks = {}
        
        # read config_general.json file to initialise parameters
        with open(PATH_GENERAL_CONFIG, 'r') as f:
            self.general_config =  json.load(f)
        
        for key, path in self.general_config["paths"].items():
            setattr(self, key, path)
        
        # Set default icon for bad icon request
        self.default_icon = Image.open(f"{self.PATH_ASSETS}Icon_Empty.png")
        
        # Set fonts dictionary
        self.FONTS = {key: ImageFont.truetype(self.PATH_FONTS + data['path'], data['size']) for key, data in self.general_config["fonts"].items()}
        
        # Set battery icon dictionary
        self.BATTERY_DICT = {data: f"{self.PATH_ASSETS}{key}" for key, data in self.general_config["battery_icons"].items()}
        
        # Initialise LCD class
        self.LCD = LCD_1inch47.LCD_1inch47(**self.general_config["display"])
        
        self.BATTERY_LEVEL          = 47
        self.STATUS_TXT             = "Ready to GO !"
    
    def _get_battery_icon(self):
        logging.info("Page._get_battery_icon(): get the appropriate battery icon")
        auth_level = np.array(list(self.BATTERY_DICT.keys()))
        auth_level[::-1].sort()
        
        if self.BATTERY_LEVEL>auth_level[-1]:
            arg = np.argmax(auth_level<self.BATTERY_LEVEL)
        else:
            arg = -1
        return self.BATTERY_DICT[auth_level[arg]]
    
    def _draw_status_bar(self):
        logging.info("Page._draw_status_bar(): add status bar to the display")
        
        draw = ImageDraw.Draw(self.LCD.screen_img)
        
        draw.rectangle([(0,0),(320,34)], fill=(0, 0, 0))
        draw.rectangle([(0,0),(320,32)], fill=(64, 64, 64))
        draw.text((6, 6), f"{self.STATUS_TXT}", fill=(255,255,255), font=self.FONTS["PixelOperatorMonoBold_L"], anchor='lt')
        
        draw.rectangle([(254,0),(320,32)], fill=(64, 64, 64))
        asset_battery = Image.open(self._get_battery_icon())
        self.LCD.screen_img.paste(asset_battery, (254, 2), asset_battery.convert("RGBA"))
        return None
    
    def display(self):
        logging.info("Page.display(): initialise new LCD image")
        # Generate an image representing the page
        self.LCD.screen_img = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0, 0, 0, 255))
        return None
    
    def navigate(self, direction):
        logging.info("Page.navigate(): navigate in the page")
        if direction in self.keys.keys():
            if self.keys[direction] not in ['', 'none']:
                logging.info(f"Page.navigate({direction}): callback function '{self.keys[direction]}'")
                self.action = self.keys_callbacks[self.keys[direction]]
        return None


class Menu(Page):
    def __init__(self, config):
        logging.info("Menu.__init__(): initialise menu specific options")
        super().__init__(config)
        self._config = config
        
        self.menu_options = self._config["menus"]
        self.current_menu = 0
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {
            'menu_up'     : self.menu_up,
            'menu_down'   : self.menu_down,
            'menu_select' : self.menu_select,
            }
        return None
    
    def menu_up(self):
        logging.info("Menu.menu_up(): move menu up")
        self.current_menu = (self.current_menu - 1) % len(self.menu_options)
        self.display()
        return None
    
    def menu_down(self):
        logging.info("Menu.menu_down(): move menu down")
        self.current_menu = (self.current_menu + 1) % len(self.menu_options)
        self.display()
        return None
    
    def menu_select(self):
        logging.info("Menu.menu_select(): handle menu selection callbacks")
        action = self.menu_options[self.current_menu]["action"]
        if action not in ['', 'none']:
            logging.info(f"Menu.menu_select(): action '{action}'")
            self.page_callbacks[action](action)
        else:
            logging.info("Menu.menu_select(): no action to trigger")
        return None
    
    def display(self):
        logging.info("Menu.display(): add menu elements to the display")
        super().display()
        draw = ImageDraw.Draw(self.LCD.screen_img)
        # Add menus with icons
        for i in range(min(3, len(self.menu_options))):
            idx = (i-1+self.current_menu)%len(self.menu_options)
            menu = self.menu_options[idx]
            icon_path = menu.get("icon", f"{self.PATH_ASSETS}Icon_Empty.png")
            try:
                icon = Image.open(f"{self.PATH_ASSETS}{icon_path}")
            except:
                icon = self.default_icon
            
            self.LCD.screen_img.paste(icon, (4, 20 + i * 60))
            
            option_font = self.FONTS["PixelOperator_L"] if i != 1 else self.FONTS["PixelOperatorBold_L"]
            option_pos = (64, 42 + i * 60)
            option_text = menu["name"] if menu["name"] != "" else "[empty name]"
            draw.text(option_pos, option_text, font=option_font, fill=(255, 255, 255), anchor='lm')
        
        asset_selection = Image.open("assets/Selection.png")
        self.LCD.screen_img.paste(asset_selection, (1, 76), asset_selection.convert("RGBA"))
        return None


class Button(Page):
    def __init__(self, config):
        logging.info("Button.__init__(): initialise menu specific options")
        super().__init__(config)
        self._config = config
        
        self.button_options = self._config["buttons"]
        self.current_button = 0 if len(self.button_options) > 1 else -1
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {
            'button_up'     : self.button_up,
            'button_down'   : self.button_down,
            'button_select' : self.button_select,
            }
        return None
    
    def button_up(self):
        logging.info("Button.button_up(): move to the next button")
        self.current_button = (self.current_button - 1) % len(self.button_options)
        self.display()
        return None
    
    def button_down(self):
        logging.info("Button.button_down(): move to the previous button")
        self.current_button = (self.current_button + 1) % len(self.button_options)
        self.display()
        return None
    
    def button_select(self):
        logging.info("Button.button_select(): handle menu selection callbacks")
        action = self.menu_options[self.current_button]["action"]
        if action not in ['', 'none']:
            logging.info(f"Button.button_select(): action '{action}'")
            self.page_callbacks[action](action)
        else:
            print("No action yet")
        return None
    
    def display(self):
        logging.info("Button.display(): add menu elements to the display")
        super().display()
        draw = ImageDraw.Draw(self.LCD.screen_img)
        # Add buttons
        for i in range(len(self.button_options)):
            idx = (i+self.current_button)%len(self.button_options)
            button = self.button_options[idx]
            
            option_font = self.FONTS["PixelOperator_M"] if i != 0 else self.FONTS["PixelOperatorBold_M"]
            option_pos = tuple(button['position'])
            option_text = button["name"] if button["name"] != "" else "[empty name]"
            textbbox = draw.textbbox(option_pos, option_text, font=option_font, anchor='mm')
            
            pad = 10
            box_pose = (textbbox[0]-pad, textbbox[1]-pad, textbbox[2]+pad, textbbox[3]+pad)
            draw.rounded_rectangle(box_pose, radius=8,
                                   fill=(0, 0, 0) if i != 0 else (64, 64, 64),
                                   outline=(0, 0, 0) if i != 0 else (255, 255, 255),
                                   width=0 if i != 0 else 2)
            
            draw.text(option_pos, option_text, font=option_font, fill=(255, 255, 255), anchor='mm')
        
        return None


class Parameter(Page):
    def __init__(self, config):
        logging.info("Parameter.__init__(): initialise parameter specific options")
        super().__init__(config)
        self._config = config
        
        self.parameter_options = self._config["parameters"]
        self.current_parameter = 0
        self.parameter_seleceted = 0
        
        self.pose = {
            'left' : 12,
            'top' : 52,
            'step' : 36,
            'pad' : 14,
            'offset' : 8,
            'radius' : 8,
            'length' : 90,
            'right' : max([
                ImageDraw.Draw(self.LCD.screen_img).textbbox((12, 0), param['name'],
                               font=self.FONTS["PixelOperatorBold_M"], anchor='lm')[2]
                for param in self.parameter_options
                ])
            }
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {
            'up'     : [self.parameter_up, self.parameter_increment],
            'down'   : [self.parameter_down, self.parameter_decrement],
            }
        return None
    
    def parameter_up(self):
        logging.info("Parameter.parameter_up(): move current parameter up")
        self.current_parameter = (self.current_parameter - 1) % len(self.parameter_options)
        self.display()
        return None
    
    def parameter_down(self):
        logging.info("Parameter.parameter_down(): move current parameter down")
        self.current_parameter = (self.current_parameter + 1) % len(self.parameter_options)
        self.display()
        return None
    
    def parameter_select(self):
        logging.info("Parameter.parameter_select(): handle parameter selection callbacks")
        self.parameter_seleceted = (self.parameter_seleceted+1)%2
        logging.info(f"Parameter.parameter_select(): Selected {bool(self.parameter_seleceted)}")
        self.display()
        return None
    
    def parameter_increment(self):
        logging.info("Parameter.parameter_increment(): increase current parameter value")
        parameter = self.parameter_options[self.current_parameter]
        value = parameter['value']
        step = parameter['step']
        parameter['value'] = max(0, value + step)
        self.display()
        return None
    
    def parameter_decrement(self):
        logging.info("Parameter.parameter_decrement(): decrease current parameter value")
        parameter = self.parameter_options[self.current_parameter]
        value = parameter['value']
        step = parameter['step']
        parameter['value'] = max(0, value - step)
        self.display()
        return None
    
    def navigate(self, direction):
        logging.info("Parameter.navigate(): navigate in the parameters")
        if direction in self.keys.keys():
            if self.keys[direction] not in ['', 'none']:
                if type(self.keys_callbacks[self.keys[direction]]) is list:
                    self.action = self.keys_callbacks[self.keys[direction]][self.parameter_seleceted]
                else:
                    self.action = self.keys_callbacks[self.keys[direction]]
        return None
    
    def display(self):
        logging.info("Parameter.display(): add parameter elements to the display")
        super().display()
        draw = ImageDraw.Draw(self.LCD.screen_img)
        # Add parameters with values
        for i in range(len(self.parameter_options)):
            parameter = self.parameter_options[i]
            
            font = self.FONTS["PixelOperator_M"] if i != self.current_parameter else self.FONTS["PixelOperatorBold_M"]
            
            # TODO: modify to make easier adjustement of the elements position, sepcificaly based on the name position
            # TODO: maybe add a position field in the JSON for horizontal position of elements 'name', 'value' and 'unit'
            
            name_pos = (self.pose['left'], self.pose['top'] + i * self.pose['step'])
            name_text = parameter["name"] if parameter["name"] != "" else "[empty name]"
            draw.text(name_pos, name_text, font=font, fill=(255, 255, 255), anchor='lm')
            
            box_pose = (self.pose['right']+self.pose['offset'],
                        self.pose['top']-self.pose['pad'] + i * self.pose['step'],
                        self.pose['right']+self.pose['offset']+self.pose['length'],
                        self.pose['top']+self.pose['pad'] + i * self.pose['step'])
            if i == self.current_parameter:
                if self.parameter_seleceted:
                    draw.rounded_rectangle(box_pose, radius=self.pose['radius'], fill=(64, 64, 64), outline=(255, 255, 255), width=2)
                    draw.text((self.pose['right']+2*self.pose['offset'], self.pose['top'] + i * self.pose['step']), "<>", font=self.FONTS["PixelOperatorBold_M"], fill=(255, 255, 255), anchor='lm')
                else:
                    draw.rounded_rectangle(box_pose, radius=self.pose['radius'], fill=(0, 0, 0), outline=(255, 255, 255), width=2)
            else:
                draw.rounded_rectangle(box_pose, radius=self.pose['radius'], fill=(0, 0, 0), outline=(64, 64, 64), width=1)
            
            param_pos = (box_pose[2]-self.pose['offset'], self.pose['top'] + i * self.pose['step'])
            param_text = str(parameter["value"])
            draw.text(param_pos, param_text, font=font, fill=(255, 255, 255), anchor='rm')
            
            unit_pos = (box_pose[2]+self.pose['offset'], self.pose['top'] + i * self.pose['step'])
            unit_text = parameter["unit"]
            draw.text(unit_pos, unit_text, font=font, fill=(255, 255, 255), anchor='lm')
        return None

# TODO: Create a class Info() to handle general information display

# TODO: Create a class Image() to handle image display


class ComingSoonPage(Page):
    def __init__(self, config, callbacks):
        logging.info("ComingSoonPage.__init__(): initialise ComingSoonPage")
        super().__init__(config)
        self._config = config
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {**callbacks["keys_callbacks"]}
        return None
    
    def display(self):
        logging.info("ComingSoonPage.display(): display ComingSoonPage")
        super().display()
        draw = ImageDraw.Draw(self.LCD.screen_img)
        
        icon = self.default_icon
        self.LCD.screen_img.paste(icon, (120, 65))
        
        option_font = self.FONTS["PixelOperatorBold_M"]
        option_pos = (64, 120)
        option_text = "Comming soon"
        draw.text(option_pos, option_text, font=option_font, fill=(255, 255, 255))
        
        self._draw_status_bar()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def navigate(self, direction):
        super().navigate(direction)
        logging.info(f"ComingSoonPage.navigate({direction}): execute '{self.action.__name__}'")
        self.action()
        return None


class MainMenuPage(Menu):
    def __init__(self, config, callbacks):
        logging.info("MainMenuPage.__init__(): initialise MainMenuPage")
        super().__init__(config)
        self._config = config
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {**self.keys_callbacks, **callbacks["keys_callbacks"]}
        
        # Set callbacks for navigation
        self.page_callbacks = {**self.page_callbacks, **callbacks["page_callbacks"]}
        
        self.action = lambda: None
        return None
    
    def display(self):
        logging.info("MainMenuPage.display(): display MainMenuPage")
        super().display()
        self._draw_status_bar()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def navigate(self, direction):
        super().navigate(direction)
        logging.info(f"MainMenuPage.navigate({direction}): execute '{self.action.__name__}'")
        self.action()
        return None


class ShutdownPage(Button):
    def __init__(self, config, callbacks):
        logging.info("ShutdownPage.__init__(): initialise ShutdownPage")
        super().__init__(config)
        self._config = config
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {**self.keys_callbacks, 'select': self.select, **callbacks["keys_callbacks"]}
        
        # Set callbacks for navigation
        self.page_callbacks = {**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        return None
    
    def display(self):
        logging.info("ShutdownPage.display(): display ShutdownPage")
        super().display()
        draw = ImageDraw.Draw(self.LCD.screen_img)
        
        icon = Image.open(f"{self.PATH_ASSETS}{self._config['icon']}")
        icon_pose = (int((self.LCD.size[1] - icon.size[0])/2), 40)
        self.LCD.screen_img.paste(icon, icon_pose)
        
        text_font = self.FONTS["PixelOperator_L"]
        text_pose = (int((self.LCD.size[1])/2), 105)
        draw.text(text_pose, "Shutdown now ?", fill=(255,255,255), font=text_font, anchor='mm')
        
        self._draw_status_bar()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def select(self):
        logging.info("ShutdownPage.select(): handle shutdown button selection")
        action = self.button_options[self.current_button]['action']
        
        if action in self.page_callbacks.keys():
            logging.info(f"ShutdownPage.select(): action '{action}'")
            self.page_callbacks[action](action)
        elif action in self.keys_callbacks.keys():
            logging.info(f"ShutdownPage.select(): action '{action}'")
            self.keys_callbacks[action]()
        else:
            logging.info("ShutdownPage.select(): no action to trigger")
        return
    
    def navigate(self, direction):
        super().navigate(direction)
        logging.info(f"ShutdownPage.navigate({direction}): execute '{self.action.__name__}'")
        self.action()
        return None


class SequenceParameterPage(Parameter, Button):
    def __init__(self, config, callbacks):
        logging.info("SequenceParameterPage.__init__(): initialise SequenceParameterPage")
        super().__init__(config)
        self._config = config
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {
            **self.keys_callbacks,
            'select' : self.parameter_select,
            'back' : [callbacks["keys_callbacks"]['go_back'], self.parameter_select],
            'run' : [self.parameter_select, lambda:print("Run function not implemented yet!")],
            **callbacks["keys_callbacks"],
            }
        
        # Set callbacks for navigation
        self.page_callbacks = {**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        return None
    
    def display(self):
        logging.info("SequenceParameterPage.display(): display SequenceParameterPage")
        super().display()
        
        self._draw_status_bar()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def select(self):
        logging.info("SequenceParameterPage.select(): handle selection action")
        action = self.button_options[self.current_button]['action']
        
        if action in self.page_callbacks.keys():
            logging.info(f"SequenceParameterPage.select(): action '{action}'")
            self.page_callbacks[action](action)
        elif action in self.keys_callbacks.keys():
            logging.info(f"SequenceParameterPage.select(): action '{action}'")
            self.keys_callbacks[action]()
        else:
            logging.info("SequenceParameterPage.select(): no action to trigger")
        return
    
    def navigate(self, direction):
        if direction == 'left':
            self.action = self.keys_callbacks[self.keys[direction]][self.parameter_seleceted]
        else:
            super().navigate(direction)
        logging.info(f"SequenceParameterPage.navigate({direction}): execute '{self.action.__name__}'")
        self.action()
        return None


# TODO: Create class SettingPage() to handle setting modification page

# TODO: Create class BatteryPage() to handle battery information display

# TODO: Create class WifiPage() to handle wify connection

# TODO: Create class SmartphonePage() to handle web site conection


# TODO: Modify the class assignation depending on JSON, unsing existing fields or adding a class filed
class PageManager:
    def __init__(self, UI_config_path):
        logging.info("PageManager.__init__(): initialise PageManager")
        
        self.quit = False
        
        with open(UI_config_path, 'r') as f:
            self.pages_structure = json.load(f)
        
        self.pages = {}
        self.current_page = None
        self.page_stack = []
        
        # Set class correspondance
        self.class_dict = {
            "MainMenuPage": MainMenuPage,
            "ComingSoonPage": ComingSoonPage,
            "ShutdownPage": ShutdownPage,
            "SequenceParameterPage": SequenceParameterPage,
            }
        
        # Define interface level callback function
        self.keys_callbacks = {
            "go_back": self.go_back,
            "shutdown": self.shutdown,
            }
        #
        self.page_callbacks = {
            "main_menu_page": self.show_page,
            "sequence_parameter_page": self.show_page,
            "shutdown_page": self.show_page,
            "coming_soon_page": self.show_page,
            }
        
        self.callbacks = {
            "keys_callbacks": self.keys_callbacks,
            "page_callbacks": self.page_callbacks,
            }
        
        self.load_pages()
        return None
    
    def load_pages(self):
        logging.info("PageManager.load_page(): generate pages based on config file")
        for page_key, page_data in self.pages_structure.items():
            self.pages[page_key] = self.class_dict[page_data["class"]](page_data, self.callbacks)
        return None
    
    def show_page(self, page_key=None):
        logging.info("PageManager.show_page(): keep track of page history and display current page")
        if self.current_page:
            self.page_stack.append(self.current_page)
        
        self.current_page = self.pages[page_key]
        self.current_page.display()
        return None
    
    def go_back(self):
        logging.info("PageManager.go_back(): actualise page to previous page history and display current it")
        if self.page_stack:
            self.current_page = self.page_stack.pop()
            self.current_page.display()
        return None
    
    def shutdown(self):
        logging.info("PageManager.shutdown(): shutdown PageManager")
        self.quit = True
        return


class MainApp:
    def __init__(self, UI_config_path):
        self.page_manager = PageManager(UI_config_path)
        self.page_manager.show_page("main_menu_page")
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()
        self.QUIT = False
        return None
    
    def on_press(self, key):
        try:
            if self.page_manager.current_page._config['class'] == "MainMenuPage":
                if key.name == "left":
                    if self.page_manager.current_page:
                        self.page_manager.page_stack.append(self.page_manager.current_page)
                    self.page_manager.current_page = self.page_manager.pages["shutdown_page"]
                    self.page_manager.current_page.display()
                    return None
            self.page_manager.current_page.navigate(key.name)
        except AttributeError:
            pass
        return None
    
    def run(self):
        logging.info("MainApp(class):run(): Running the MainApp(class)")
        while (not self.QUIT) and (not self.page_manager.quit):
            continue
        
        return None
    
    def clean_stop(self):
        logging.info("MainApp(class):clean_stop(): Cleanning MainApp(class)")
        self.page_manager.current_page.LCD.ClearScreen()
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