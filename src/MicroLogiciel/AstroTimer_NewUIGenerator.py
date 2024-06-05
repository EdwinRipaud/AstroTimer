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
        draw.text((6, 6),
                  f"{self.STATUS_TXT}",
                  fill=(255,255,255),
                  font=self.FONTS["PixelOperatorMonoBold_L"],
                  anchor='lt')
        
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
        try:
            self.keys_callbacks = {
                **self.keys_callbacks,
                'menu_up'     : self.menu_up,
                'menu_down'   : self.menu_down,
                'menu_select' : self.menu_select,
                }
        except AttributeError:
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
            draw.text(option_pos,
                      option_text,
                      font=option_font,
                      fill=(255, 255, 255),
                      anchor='lm')
        
        asset_selection = Image.open("assets/Selection.png")
        self.LCD.screen_img.paste(asset_selection, (1, 76), asset_selection.convert("RGBA"))
        return None


class Button(Page):
    def __init__(self, config):
        logging.info("Button.__init__(): initialise menu specific options")
        super().__init__(config)
        self._config = config
        
        self.button_config = self._config["buttons"]
        self.button_parameters = self.button_config["parameters"]
        self.button_options = self.button_config["options"]
        
        self.current_button = 0
        self.button_active = True
        
        # TODO: initilaize from JSON parameter
        bboxs = [ImageDraw.Draw(self.LCD.screen_img).textbbox(tuple(button['position']),
                                                              button["name"] if button["name"] != "" else "[empty name]",
                                                              font=self.FONTS["PixelOperatorBold_M"],
                                                              anchor='mm'
                                                              ) for button in self.button_options]
        self.button_pose = {
            'left'   : [bbox[0] for bbox in bboxs],
            'right'  : [bbox[2] for bbox in bboxs],
            'top'    : [bbox[1] for bbox in bboxs],
            'bottom' : [bbox[3] for bbox in bboxs],
            'pad_x'  : self.button_parameters['pad_x'],
            'pad_y'  : self.button_parameters['pad_y'],
            'radius' : self.button_parameters['radius'],
            }
        
        # Set callbacks for navigation keys
        try:
            self.keys_callbacks = {
                **self.keys_callbacks,
                'button_up'     : self.button_up,
                'button_down'   : self.button_down,
                'button_select' : self.button_select,
                }
        except AttributeError:
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
            logging.info("Button.button_select(): No action yet !")
        return None
    
    def display(self):
        logging.info("Button.display(): add menu elements to the display")
        super().display()
        draw = ImageDraw.Draw(self.LCD.screen_img)
        # Add buttons
        for i in range(len(self.button_options)):
            button = self.button_options[i]
            
            option_font = self.FONTS["PixelOperator_M"] if i != self.current_button else self.FONTS["PixelOperatorBold_M"]
            option_pos = tuple(button['position'])
            option_text = button["name"] if button["name"] != "" else "[empty name]"
            
            if (i == self.current_button) and (self.button_active):
                draw.rounded_rectangle((self.button_pose['left'][i]-self.button_pose['pad_x'],
                                        self.button_pose['top'][i]-self.button_pose['pad_y'],
                                        self.button_pose['right'][i]+self.button_pose['pad_x'],
                                        self.button_pose['bottom'][i]+self.button_pose['pad_y']),
                                       radius=self.button_pose['radius'],
                                       fill=(64, 64, 64),
                                       outline=(255, 255, 255),
                                       width=2)
            else:
                draw.rounded_rectangle((self.button_pose['left'][i]-self.button_pose['pad_x'],
                                        self.button_pose['top'][i]-self.button_pose['pad_y'],
                                        self.button_pose['right'][i]+self.button_pose['pad_x'],
                                        self.button_pose['bottom'][i]+self.button_pose['pad_y']),
                                       radius=self.button_pose['radius'],
                                       fill=(0, 0, 0),
                                       outline=(64, 64, 64),
                                       width=1)
            draw.text(option_pos,
                      option_text,
                      font=option_font,
                      fill=(255, 255, 255),
                      anchor='mm')
        
        return None


class Parameter(Page):
    def __init__(self, config):
        logging.info("Parameter.__init__(): initialise parameter specific options")
        super().__init__(config)
        self._config = config
        
        self.parameter_config = self._config["parameters"]
        self.parameter_parameters = self.parameter_config["parameters"]
        self.parameter_options = self.parameter_config["options"]
        
        self.current_parameter = 0
        self.parameter_seleceted = 0
        self.parameter_active = True
        
        # TODO: initilaize from JSON parameter
        self.parameters_pose = {
            'left'   : 12,
            'top'    : 52,
            'step'   : self.parameter_parameters['step'],
            'pad_x'  : self.parameter_parameters['pad_x'],
            'pad_y'  : self.parameter_parameters['pad_y'],
            'offset' : self.parameter_parameters['offset'],
            'radius' : self.parameter_parameters['radius'],
            'box_length' : self.parameter_parameters['box_length'],
            'right'  : max([
                ImageDraw.Draw(self.LCD.screen_img).textbbox((12, 0), param['name'],
                               font=self.FONTS[f"PixelOperatorBold_{self.parameter_parameters['font_size']}"], anchor='lm')[2]
                for param in self.parameter_options]),
            }
        
        # Set callbacks for navigation keys
        try:
            self.keys_callbacks = {
                **self.keys_callbacks,
                'parameter_up'   : [self.parameter_up, self.parameter_increment],
                'parameter_down' : [self.parameter_down, self.parameter_decrement],
                }
        except AttributeError:
            self.keys_callbacks = {
                'parameter_up'   : [self.parameter_up, self.parameter_increment],
                'parameter_down' : [self.parameter_down, self.parameter_decrement],
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
            
            if i == self.current_parameter:
                font = self.FONTS[f"PixelOperatorBold_{self.parameter_parameters['font_size']}"]
            else:
                font = self.FONTS[f"PixelOperator_{self.parameter_parameters['font_size']}"]
            
            name_pos = (self.parameters_pose['left'], self.parameters_pose['top'] + i * self.parameters_pose['step'])
            name_text = parameter["name"] if parameter["name"] != "" else "[empty name]"
            draw.text(name_pos,
                      name_text,
                      font=font,
                      fill=(255, 255, 255),
                      anchor='lm')
            
            box_pose = (self.parameters_pose['right']+self.parameters_pose['offset'],
                        self.parameters_pose['top']-self.parameters_pose['pad_y'] + i * self.parameters_pose['step'],
                        self.parameters_pose['right']+self.parameters_pose['offset']+self.parameters_pose['box_length'],
                        self.parameters_pose['top']+self.parameters_pose['pad_y'] + i * self.parameters_pose['step'])
            if (i == self.current_parameter) and self.parameter_active:
                if self.parameter_seleceted:
                    draw.rounded_rectangle(box_pose,
                                           radius=self.parameters_pose['radius'],
                                           fill=(64, 64, 64),
                                           outline=(255, 255, 255),
                                           width=2)
                    # TODO: replace this text by a top-bottom chevron custom icon
                    draw.text((self.parameters_pose['right']+2*self.parameters_pose['offset'], self.parameters_pose['top'] + i * self.parameters_pose['step']),
                              "<>",
                              font=self.FONTS[f"PixelOperatorBold_{self.parameter_parameters['font_size']}"],
                              fill=(255, 255, 255),
                              anchor='lm')
                else:
                    draw.rounded_rectangle(box_pose,
                                           radius=self.parameters_pose['radius'],
                                           fill=(0, 0, 0),
                                           outline=(255, 255, 255),
                                           width=2)
            else:
                draw.rounded_rectangle(box_pose,
                                       radius=self.parameters_pose['radius'],
                                       fill=(0, 0, 0),
                                       outline=(64, 64, 64),
                                       width=1)
            
            param_pos = (box_pose[2]-self.parameters_pose['offset'], self.parameters_pose['top'] + i * self.parameters_pose['step'])
            param_text = str(parameter["value"])
            draw.text(param_pos,
                      param_text,
                      font=font,
                      fill=(255, 255, 255),
                      anchor='rm')
            
            unit_pos = (box_pose[2]+self.parameters_pose['offset'], self.parameters_pose['top'] + i * self.parameters_pose['step'])
            unit_text = parameter["unit"]
            draw.text(unit_pos,
                      unit_text,
                      font=font,
                      fill=(255, 255, 255),
                      anchor='lm')
        return None


class Picture(Page):
    def __init__(self, config):
        logging.info("Picture.__init__(): initialise Picture specific options")
        super().__init__(config)
        self._config = config
        
        self.picture_options = self._config["pictures"]
        
        if 'image' in self.picture_options.keys():
            self.picture = Image.open(f"{self.PATH_ASSETS}{self.picture_options['image']}")
        else:
            self.picture = Image.open(f"{self.PATH_ASSETS}Icon_Empty.png")
        
        self._set_pose()
        
        # Set callbacks for navigation keys
        try:
            self.keys_callbacks = {
                **self.keys_callbacks,
                }
        except AttributeError:
            self.keys_callbacks = {}
        return None
    
    def _set_pose(self):
        logging.info("Picture._set_pose(): compute image position in screen")
        if 'position' in self.picture_options.keys():
            self.pose = self.picture_options['position']
        else:
            self.pose = (int((self.LCD.screen_img.width-self.picture.height)/2),
                         int((self.LCD.screen_img.height-self.picture.height)/2))
        return None
    
    def _generate_QRCode(self, text=""):
        logging.info("Picture.get_QRCode(): generate QRCode")
        if len(text)>50:
            box_size = 4
        else:
            box_size = 5
        qr = qrcode.QRCode(box_size=box_size, border=2)
        qr.add_data(text)
        self.picture = qr.make_image()
        self._set_pose()
        return None
    
    def display(self):
        logging.info("Picture.display(): add picture to the display")
        super().display()
        
        self.LCD.screen_img.paste(self.picture, self.pose)
        return None

# TODO: Create a class Info() to handle general information display


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
            'up' : self.option_up,
            'down' : self.option_down,
            **callbacks["keys_callbacks"], # TODO: key_callbacks didn't have button callbacks !!!
            }
        
        # Set callbacks for navigation
        self.page_callbacks = {**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        
        self.options_list = [
            *['parameter']*len(self.parameter_options),
            *['button']*len(self.button_options)
            ]
        self.options_callbacks = {
            'parameter' : {'up': self.keys_callbacks['parameter_up'], 'down': self.keys_callbacks['parameter_down']},
            'button' : {'up': self.keys_callbacks['button_up'], 'down': self.keys_callbacks['button_down']}
            }
        self.current_option = 0
        self.activate_options()
        return None
    
    def activate_options(self):
        logging.info("SequenceParameterPage.activate_options(): activate usefull options")
        if self.options_list[self.current_option] == 'parameter':
            self.parameter_active = True
            self.button_active = False
        elif self.options_list[self.current_option] == 'button':
            self.parameter_active = False
            self.button_active = True
        else:
            self.parameter_active = False
            self.button_active = False
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
    
    def option_up(self):
        logging.info("SequenceParameterPage.option_up(): move current option up")
        if not self.parameter_seleceted:
            self.current_option = (self.current_option-1)%len(self.options_list)
        self.action = self.options_callbacks[self.options_list[self.current_option]]['up']
        if type(self.action) == list:
            self.action = self.action[self.parameter_seleceted]
        self.activate_options()
        self.action()
        return None
    
    def option_down(self):
        logging.info("SequenceParameterPage.option_down(): move current option down")
        if not self.parameter_seleceted:
            self.current_option = (self.current_option+1)%len(self.options_list)
        self.action = self.options_callbacks[self.options_list[self.current_option]]['down']
        if type(self.action) == list:
            self.action = self.action[self.parameter_seleceted]
        self.activate_options()
        self.action()
        return None
    
    def navigate(self, direction):
        logging.info("SequenceParameterPage.navigate(): navigate into sequence parameter page options")
        if direction in self.keys.keys():
            if direction == 'left':
                self.action = self.keys_callbacks[self.keys[direction]][self.parameter_seleceted]
            elif self.keys[direction] not in ['', 'none']:
                if type(self.keys_callbacks[self.keys[direction]]) is list:
                    self.action = self.keys_callbacks[self.keys[direction]][self.parameter_seleceted]
                else:
                    self.action = self.keys_callbacks[self.keys[direction]]
            logging.info(f"SequenceParameterPage.navigate({direction}): execute '{self.action.__name__}'")
            self.action()
        return None


class WifiPage(Picture):
    def __init__(self, config, callbacks):
        logging.info("WifiPage.__init__(): initialise WifiPage")
        super().__init__(config)
        self._config = config
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {**self.keys_callbacks, **callbacks["keys_callbacks"]}
        
        # Set callbacks for navigation
        self.page_callbacks = {**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        return None
    
    def get_wifi_QRCode(self):
        logging.info("WifiPage.get_wifi_QRCode(): generate wifi connection QRCode")
        if os.path.exists(self.PATH_WIFI):
            file_values = subprocess.check_output(f"sudo cat {self.PATH_WIFI}", shell=True).decode('utf-8')
            WIFI_CONFIG = {line.split('=')[0]:line.split('=')[1] for line in file_values.split('\n')[:-1]}
            
            if 'ignore_broadcast_ssid' not in WIFI_CONFIG.keys():
                WIFI_CONFIG['ignore_broadcast_ssid'] = 'false'
            else:
                if WIFI_CONFIG['ignore_broadcast_ssid']:
                    WIFI_CONFIG['ignore_broadcast_ssid'] = 'true'
                else:
                    WIFI_CONFIG['ignore_broadcast_ssid'] = 'false'
        else:
            WIFI_CONFIG = {'ssid'                 :'WifiHelloWorld',
                           'wpa_passphrase'       :'HelloWorld!',
                          'ignore_broadcast_ssid' :'true',
                           'wpa'                  :'WPA2',
                          }
        self._generate_QRCode("WIFI:T:{};S:{};P:{};H:{};;".format(WIFI_CONFIG['wpa'],
                                                                  WIFI_CONFIG['ssid'],
                                                                  WIFI_CONFIG['wpa_passphrase'],
                                                                  WIFI_CONFIG['ignore_broadcast_ssid']))
        return None
    
    def display(self):
        logging.info("WifiPage.display(): display WifiPage")
        self.get_wifi_QRCode()
        super().display()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def navigate(self, direction):
        super().navigate(direction)
        logging.info(f"WifiPage.navigate({direction}): execute '{self.action.__name__}'")
        self.action()
        return None


class SmartphonePage(Picture):
    def __init__(self, config, callbacks):
        logging.info("SmartphonePage.__init__(): initialise SmartphonePage")
        super().__init__(config)
        self._config = config
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {**self.keys_callbacks, **callbacks["keys_callbacks"]}
        
        # Set callbacks for navigation
        self.page_callbacks = {**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        return None
    
    def get_website_QRCode(self):
        logging.info("SmartphonePage.get_website_QRCode(): generate website connection QRCode")
        if os.path.exists(self.PATH_WEBSITE['path']):
            file_values = subprocess.check_output(f"sudo cat {self.PATH_WEBSITE['path']}", shell=True).decode('utf-8')
            id_paragraphe = file_values.find('#static IP')
            paragraphe = file_values[id_paragraphe:]
            self.WEBSITE_CONFIG = {'ip'   : paragraphe[paragraphe.find('=')+1:paragraphe.find('=')+11],
                                   'port' : self.PATH_WEBSITE['port']}
        else:
            self.WEBSITE_CONFIG = {'ip'   :'255.255.255.255',
                                   'port' :'65535',
                                   }
        
        self._generate_QRCode(f"HTTP:{self.WEBSITE_CONFIG['ip']}:{self.WEBSITE_CONFIG['port']}")
        return None
    
    def display(self):
        logging.info("SmartphonePage.display(): display SmartphonePage")
        self.get_website_QRCode()
        super().display()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def navigate(self, direction):
        super().navigate(direction)
        logging.info(f"SmartphonePage.navigate({direction}): execute '{self.action.__name__}'")
        self.action()
        return None


# TODO: Create class SettingPage() to handle setting modification page

# TODO: Create class BatteryPage() to handle battery information display



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
            "WifiPage": WifiPage,
            "SmartphonePage": SmartphonePage,
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
            "wifi_page": self.show_page,
            "smartphone_page": self.show_page,
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
        logging.info("PageManager.show_page(): keep track of page history")
        if self.current_page:
            self.page_stack.append(self.current_page)
        
        self.current_page = self.pages[page_key]
        self.current_page.display()
        return None
    
    def go_back(self):
        logging.info("PageManager.go_back(): move to previous history page")
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
        self.page_manager.show_page("main_menu_page")#"smartphone_page")#
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