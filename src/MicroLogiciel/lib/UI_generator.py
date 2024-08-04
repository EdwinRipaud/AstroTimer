#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Sat Jun  8 11:31:48 2024

@author: Er-berry
"""

import os
import json
import time
import qrcode
import logging
import filelock
import logging.config
import subprocess
import multiprocessing
import threading
import numpy as np
from PIL import Image, ImageDraw


OPERATING_SYSTEM = os.uname()
RUN_ON_RPi = (OPERATING_SYSTEM.sysname == 'Linux') and (OPERATING_SYSTEM.machine in ['aarch64', 'armv6l'])

if RUN_ON_RPi:
    BYPASS_BUILTIN_SCREEN = False
    from smbus import SMBus
    bus = SMBus(1)
    I2C_DEVICE = []
    for device in range(128):
        try:
            bus.read_byte(device)
            I2C_DEVICE.append(device)
        except: continue
    # TODO: get I2C device address from config file
    if 0x36 in I2C_DEVICE:
        from lib.MAX17043 import max17043
    if 0x40 in I2C_DEVICE:
        from lib.INA2xx import INA226 as INA2__
    elif 0x42 in I2C_DEVICE:
        from lib.INA2xx import INA219 as INA2__
    import lib.Trigger as trigger
else:
    BYPASS_BUILTIN_SCREEN = True


SCRIPT_NAME = __file__.split('/')[-1]

logging.config.fileConfig('logging.conf')
lib_logger = logging.getLogger('libLogger')
lib_logger.debug("Imported file")

UNIT_CONVERTER = {'s':1, 'ms':1e-3, 'us':1e-6}

BATTERY_SOC = -1
BATTERY_VOLTAGE = -1


class Page:
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, page_config:dict)->None:
        self.class_logger.info("initialise utils attributes for the page",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        self.title = page_config["title"]
        
        self.keys = page_config["keys"]
        
        # Set callbacks for navigation
        self.page_callbacks = {}
        
        self.STATUS_TXT    = "Ready to GO !"
        return None
    
    def _get_battery_icon(self)->None:
        self.class_logger.debug("get the appropriate battery icon",
                                extra={'className':f"{self.__class__.__name__}:"})
        auth_level = np.array(list(self.BATTERY_DICT.keys()))
        auth_level[::-1].sort()
        
        if BATTERY_SOC>auth_level[-1]:
            arg = np.argmax(auth_level<BATTERY_SOC)
        else:
            arg = -1
        return self.BATTERY_DICT[auth_level[arg]]
    
    def _draw_status_bar(self)->None:
        self.class_logger.debug("add status bar to the display",
                                extra={'className':f"{self.__class__.__name__}:"})
        
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
    
    def display(self)->None:
        self.class_logger.info("initialise new LCD image",
                               extra={'className':f"{self.__class__.__name__}:"})
        # Generate an image representing the page
        self.LCD.screen_img = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0, 0, 0, 255))
        return None
    
    def navigate(self, direction:str)->None:
        self.class_logger.info("navigate in the page",
                                extra={'className':f"{self.__class__.__name__}:"})
        if direction in self.keys.keys():
            if self.keys[direction] not in ['', 'none']:
                self.class_logger.debug(f"callback function '{self.keys[direction]}'",
                                        extra={'className':f"{self.__class__.__name__}:"})
                self.action = self.keys_callbacks[self.keys[direction]]
        return None


class Menu(Page):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict)->None:
        self.class_logger.info("initialise menu specific options",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().__init__(config)
        self._config = config
        
        self.menu_options = self._config["menus"]
        self.current_menu = 0
        
        self.menu_parameters = {}
        
        # Set callbacks for navigation keys
        try:
            self.keys_callbacks = {
                **self.keys_callbacks,
                'menu_up'     : self.menu_up,
                'menu_down'   : self.menu_down,
                'menu_select' : self.menu_select,
                }
        except AttributeError:
            self.class_logger.warning("keys_callbacks doesn't existe",
                                      extra={'className':f"{self.__class__.__name__}:"})
            self.keys_callbacks = {
                'menu_up'     : self.menu_up,
                'menu_down'   : self.menu_down,
                'menu_select' : self.menu_select,
                }
        return None
    
    def menu_up(self)->None:
        self.class_logger.info("move menu up",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_menu = (self.current_menu - 1) % len(self.menu_options)
        self.display()
        return None
    
    def menu_down(self)->None:
        self.class_logger.info("move menu down",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_menu = (self.current_menu + 1) % len(self.menu_options)
        self.display()
        return None
    
    def menu_select(self)->None:
        self.class_logger.info("handle menu selection callbacks",
                               extra={'className':f"{self.__class__.__name__}:"})
        action = self.menu_options[self.current_menu]["action"]
        if action not in ['', 'none']:
            self.class_logger.debug(f"action '{action}'",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.page_callbacks[action](action)
        else:
            self.class_logger.debug("no action to trigger",
                                    extra={'className':f"{self.__class__.__name__}:"})
        return None
    
    def display(self)->None:
        self.class_logger.info("add menu elements to the display",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        draw = ImageDraw.Draw(self.LCD.screen_img, 'RGBA')
        if self.menu_parameters['max_line'] > 0:
            max_line = self.menu_parameters['max_line']
        else:
            max_line = len(self.menu_options)
        
        # Add menus with icons
        for i in range(max_line):
            idx = (i-1+self.current_menu)%len(self.menu_options)
            menu = self.menu_options[idx]
            
            if self.menu_parameters['icon']:
                icon_path = menu.get("icon", f"{self.PATH_ASSETS}Icon_Empty.png")
                try:
                    icon = Image.open(f"{self.PATH_ASSETS}{icon_path}")
                except:
                    icon = self.default_icon
                icon_pose = (self.menu_parameters['icon_left'],
                             self.menu_parameters['top_offset'] + self.menu_parameters['icon_middle'] - int(icon.height/2) + i*self.menu_parameters['step'])
                self.LCD.screen_img.paste(icon, icon_pose)
            
            if i == 1:
                option_font = self.FONTS[f"PixelOperatorBold_{self.menu_parameters['font_size']}"]
            else:
                option_font = self.FONTS[f"PixelOperator_{self.menu_parameters['font_size']}"]
            option_text = menu["name"] if menu["name"] != "" else "[empty name]"
            option_pos = (self.menu_parameters['text_left'],
                          self.menu_parameters['top_offset'] + self.menu_parameters['text_middle'] + i * self.menu_parameters['step'])
            draw.text(option_pos,
                      option_text,
                      font=option_font,
                      fill=(255, 255, 255),
                      anchor='lm')
        
        img = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0))
        draw = ImageDraw.Draw(img, 'RGBA')
        bbox_pose = (self.menu_parameters['bbox_left'],
                     self.menu_parameters['top_offset'] + self.menu_parameters['bbox_middle'] - int(self.menu_parameters['bbox_height']/2),
                     self.menu_parameters['bbox_right']-1,
                     self.menu_parameters['top_offset'] + self.menu_parameters['bbox_middle'] + int(self.menu_parameters['bbox_height']/2)-1)
        draw.rounded_rectangle(bbox_pose,
                               radius=self.menu_parameters['bbox_radius'],
                               fill=(0, 0, 0, 0),
                               outline=(255, 255, 255, 255),
                               width=self.menu_parameters['bbox_lw'])
        self.LCD.screen_img = Image.alpha_composite(self.LCD.screen_img, img)
        return None


class Button(Page):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict)->None:
        self.class_logger.info("initialise menu specific options",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().__init__(config)
        self._config = config
        
        self.button_options = self._config["buttons"]
        
        self.current_button = 0
        self.button_active = True
        
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
            self.class_logger.warning("keys_callbacks doesn't existe",
                                      extra={'className':f"{self.__class__.__name__}:"})
            self.keys_callbacks = {
                'button_up'     : self.button_up,
                'button_down'   : self.button_down,
                'button_select' : self.button_select,
                }
        return None
    
    def button_up(self)->None:
        self.class_logger.info("move to the next button",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_button = (self.current_button - 1) % len(self.button_options)
        self.display()
        return None
    
    def button_down(self)->None:
        self.class_logger.info("move to the previous button",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_button = (self.current_button + 1) % len(self.button_options)
        self.display()
        return None
    
    def button_select(self)->None:
        self.class_logger.info("handle menu selection callbacks",
                               extra={'className':f"{self.__class__.__name__}:"})
        action = self.menu_options[self.current_button]["action"]
        if action not in ['', 'none']:
            self.class_logger.debug(f"action '{action}'",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.page_callbacks[action](action)
        else:
            self.class_logger.debug("No action yet !",
                                    extra={'className':f"{self.__class__.__name__}:"})
        return None
    
    def display(self)->None:
        self.class_logger.info("add menu elements to the display",
                               extra={'className':f"{self.__class__.__name__}:"})
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


class Parameter():
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict)->None:
        self.class_logger.info("initialise parameter specific options",
                               extra={'className':f"{self.__class__.__name__}:"})
        # super().__init__(config)
        self._config = config
        
        self.parameter_seleceted = 0
        self.parameter_active = True
        
        # self.parameters_pose = config['pose']
        
        # Set callbacks for navigation keys
        try:
            self.keys_callbacks = {
                **self.keys_callbacks,
                }
        except AttributeError:
            self.class_logger.warning("keys_callbacks doesn't existe",
                                      extra={'className':f"{self.__class__.__name__}:"})
            self.keys_callbacks = {}
        return None
    
    def display(self)->None:
        self.class_logger.info("add parameter elements to the display",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        return None


class Keyboard(Parameter):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict)->None:
        self.class_logger.info("initialise Info specific options",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().__init__(config)
        self._config = config
        
        # Set callbacks for navigation keys
        try:
            self.keys_callbacks = {
                **self.keys_callbacks,
                "keyboard_up": self.keyboard_up,
                "keyboard_down": self.keyboard_down,
                "keyboard_left": self.keyboard_left,
                "keyboard_right": self.keyboard_right,
                "keyboard_select": self.keyboard_select
                }
        except AttributeError:
            self.class_logger.warning("keys_callbacks doesn't existe",
                                      extra={'className':f"{self.__class__.__name__}:"})
            self.keys_callbacks = {
                "keyboard_up": self.keyboard_up,
                "keyboard_down": self.keyboard_down,
                "keyboard_left": self.keyboard_left,
                "keyboard_right": self.keyboard_right,
                "keyboard_select": self.keyboard_select
                }
        
        self.keyboard_keys = {'lower': [["0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "DEL", "DEL", "OK", "OK"],
                                        ["MAJ", "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m"],
                                        ["MAJ", "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z"]],
                              'upper': [["&", "(", "-", "_", ")", "=", "*", "+", ".", ",", "DEL", "DEL", "OK", "OK"],
                                        ["MAJ", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M"],
                                        ["MAJ", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z"]]}
        self.case = {True:'lower', False:'upper'}
        self._case = True
        self._keyboard_size = (len(self.keyboard_keys[self.case[self._case]]),
                               max([len(l) for l in self.keyboard_keys[self.case[self._case]]]))
        self._key_spe = {'MAJ': {'pos': (17, 116),
                                 'path': {False:f"{self.PATH_ASSETS}Key_MAJ.png",
                                          True:f"{self.PATH_ASSETS}Key_MAJ_selected.png"}},
                         'DEL': {'pos': (220, 92),
                                 'path': {False:f"{self.PATH_ASSETS}Key_DEL.png",
                                          True:f"{self.PATH_ASSETS}Key_DEL_selected.png"}},
                         'OK': {'pos': (262, 92),
                                'path': {False:f"{self.PATH_ASSETS}Key_OK.png",
                                         True:f"{self.PATH_ASSETS}Key_OK_selected.png"}}}
        self.init_pos = (30, 105)
        self.step = (20, 24)
        self.current_key = (1, 1)
        return None
    
    def keyboard_up(self)->None:
        self.class_logger.info("move current key selection up",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_key = (self.current_key[0], (self.current_key[1] - 1) % self._keyboard_size[0])
        self.display()
        return None
    
    def keyboard_down(self)->None:
        self.class_logger.info("move current key selection down",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_key = (self.current_key[0], (self.current_key[1] + 1) % self._keyboard_size[0])
        self.display()
        return None
    
    def keyboard_left(self)->None:
        self.class_logger.info("move current key selection left",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_key = ((self.current_key[0] - 1) % self._keyboard_size[1], self.current_key[1])
        self.display()
        return None
    
    def keyboard_right(self)->None:
        self.class_logger.info("move current key selection right",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_key = ((self.current_key[0] + 1) % self._keyboard_size[1], self.current_key[1])
        self.display()
        return None
    
    def keyboard_select(self)->None:
        self.class_logger.info("handle key selection callbacks",
                               extra={'className':f"{self.__class__.__name__}:"})
        key_val = self.keyboard_keys[self.case[self._case]][self.current_key[1]][self.current_key[0]]
        if len(key_val)<2:
            print(key_val)
        elif key_val == "MAJ":
            self._case = not self._case
        self.display()
        return None
    
    def navigate(self, direction:str)->None:
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        return None
    
    def _display_keys(self, draw:ImageDraw.ImageDraw, keys:list)->None:
        # Display special keys
        for k in self._key_spe.keys():
            icon = Image.open(self._key_spe[k]['path'][k==keys[self.current_key[1]][self.current_key[0]]])
            self.LCD.screen_img.paste(icon, self._key_spe[k]['pos'])
            
        # Display alphabetic keys
        if len(keys[self.current_key[1]][self.current_key[0]])<2:
            x = self.init_pos[0]+self.step[0]*(self.current_key[0]-0.5)
            y = self.init_pos[1]+self.step[1]*(self.current_key[1]-0.5)
            draw.rounded_rectangle((x-1, y-1, x+self.step[0]+1, y+self.step[1]+1),
                                   radius=5,
                                   fill=(0, 0, 0),
                                   outline=(255, 255, 255),
                                   width=2)
        option_font = self.FONTS["PixelOperator_M"]
        for i in range(self._keyboard_size[0]):
            for j in range(self._keyboard_size[1]):
                if len(keys[i][j])<2:
                    option_pos = (self.init_pos[0]+self.step[0]*j, self.init_pos[1]+self.step[1]*i)
                    draw.text(option_pos, keys[i][j], font=option_font, fill=(255, 255, 255), anchor='mm')
        return None
    
    def display(self)->None:
        self.class_logger.info("add infos to the display",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        draw = ImageDraw.Draw(self.LCD.screen_img)
        keys = self.keyboard_keys[self.case[self._case]]
        
        self._display_keys(draw, keys)
        return None


class Numpad(Parameter):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict)->None:
        self.class_logger.info("initialise Info specific options",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().__init__(config)
        self._config = config
        
        self.name = self._config['name']
        self.unit = self._config['unit']
        self.value = self._config['value']
        self.step = self._config['step']
        
        self._pose = self._config['position']
        
        # Set callbacks for navigation keys
        try:
            self.keys_callbacks = {
                **self.keys_callbacks,
                'parameter_up'   : self.parameter_increment,
                'parameter_down' : self.parameter_decrement,
                }
        except AttributeError:
            self.class_logger.warning("keys_callbacks doesn't existe",
                                      extra={'className':f"{self.__class__.__name__}:"})
            self.keys_callbacks = {
                'parameter_up'   : self.parameter_increment,
                'parameter_down' : self.parameter_decrement,
                }
        return None
    
    def parameter_increment(self)->None:
        self.class_logger.info("increase current parameter value",
                               extra={'className':f"{self.__class__.__name__}:"})
        parameter = self.parameter_options[self.current_parameter]
        value = parameter['value']
        step = parameter['step']
        parameter['value'] = max(0, value + step)
        self.display()
        return None
    
    def parameter_decrement(self)->None:
        self.class_logger.info("decrease current parameter value",
                               extra={'className':f"{self.__class__.__name__}:"})
        parameter = self.parameter_options[self.current_parameter]
        value = parameter['value']
        step = parameter['step']
        parameter['value'] = max(0, value - step)
        self.display()
        return None
    
    def navigate(self, direction:str)->None:
        self.class_logger.info("navigate in the parameters",
                               extra={'className':f"{self.__class__.__name__}:"})
        try:
            if self.keys[direction] not in ['', 'none']:
                self.action = self.keys_callbacks[self.keys[direction]]
        except KeyError as e:
            self.class_logger.error(f"KeyError: {e}")
        return None
    
    def display(self)->None:
        self.class_logger.info("add parameter elements to the display",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        draw = ImageDraw.Draw(self.LCD.screen_img)
        # Display parameter with values
        
        font = self.FONTS["PixelOperatorBold_M" if self.parameter_seleceted else "PixelOperator_M"]
        draw.text((self._pose['left'], self._pose['top']),
                  self.name,
                  font=font,
                  fill=(255, 255, 255),
                  anchor='lm')
        
        box_pose = (self._pose['right']+self._pose['pad'],
                    self._pose['top']-self._pose['pad'],
                    self._pose['right']+self._pose['pad']+self._pose['width'],
                    self._pose['top']+self._pose['pad']+self._pose['hight'])
        if self.parameter_seleceted:
            draw.rounded_rectangle(box_pose,
                                   radius=self._pose['radius'],
                                   fill=(64, 64, 64),
                                   outline=(255, 255, 255),
                                   width=2)
            # TODO: replace this text by a top-bottom chevron custom icon
            draw.text((self._pose['right']+2*self._pose['offset'], self._pose['top']),
                      "<>",
                      font=font,
                      fill=(255, 255, 255),
                      anchor='lm')
        else:
            draw.rounded_rectangle(box_pose,
                                   radius=self._pose['radius'],
                                   fill=(0, 0, 0),
                                   outline=(255, 255, 255),
                                   width=2)
        
        draw.text((box_pose[2]-self._pose['offset'], self._pose['top']),
                  str(self.value),
                  font=font,
                  fill=(255, 255, 255),
                  anchor='rm')
        return None


class Picture(Page):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict)->None:
        self.class_logger.info("initialise Picture specific options",
                               extra={'className':f"{self.__class__.__name__}:"})
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
            self.class_logger.warning("keys_callbacks doesn't existe",
                                      extra={'className':f"{self.__class__.__name__}:"})
            self.keys_callbacks = {}
        return None
    
    def _set_pose(self)->None:
        self.class_logger.info("compute image position in screen",
                               extra={'className':f"{self.__class__.__name__}:"})
        if 'position' in self.picture_options.keys():
            self.pose = self.picture_options['position']
        else:
            self.pose = (int((self.LCD.screen_img.width-self.picture.height)/2),
                         int((self.LCD.screen_img.height-self.picture.height)/2))
        return None
    
    def _generate_QRCode(self, text:str="")->None:
        self.class_logger.info("generate QRCode",
                               extra={'className':f"{self.__class__.__name__}:"})
        if len(text)>50:
            box_size = 4
        else:
            box_size = 5
        qr = qrcode.QRCode(box_size=box_size, border=2)
        qr.add_data(text)
        self.picture = qr.make_image()
        self._set_pose()
        return None
    
    def display(self)->None:
        self.class_logger.info("add picture to the display",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        
        self.LCD.screen_img.paste(self.picture, self.pose)
        return None


class Info(Page):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict)->None:
        self.class_logger.info("initialise Info specific options",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().__init__(config)
        self._config = config
        
        # Set callbacks for navigation keys
        try:
            self.keys_callbacks = {
                **self.keys_callbacks,
                }
        except AttributeError:
            self.class_logger.warning("keys_callbacks doesn't existe",
                                      extra={'className':f"{self.__class__.__name__}:"})
            self.keys_callbacks = {}
        return None
    
    def navigate(self, direction:str)->None:
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        return None
    
    def display(self)->None:
        self.class_logger.info("add infos to the display",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        return None



class ComingSoonPage(Page):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict, callbacks:dict, general_config:dict)->None:
        self.class_logger.info("initialise ComingSoonPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        # Associate general high level attribute to 'self'
        for key, value in general_config.items():
            setattr(self, key, value)
        
        super().__init__(config)
        self._config = config
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {**callbacks["keys_callbacks"]}
        
        # Set callbacks for navigation
        self.page_callbacks = {**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        return None
    
    def navigate(self, direction:str)->None:
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None
    
    def display(self)->None:
        self.class_logger.info("display ComingSoonPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        draw = ImageDraw.Draw(self.LCD.screen_img)
        
        icon = self.default_icon
        self.LCD.screen_img.paste(icon, (160-int(icon.width/2), 60))
        
        option_font = self.FONTS["PixelOperatorBold_M"]
        option_text = "Coming soon"
        option_pos = (160, 130)
        draw.text(option_pos, option_text, font=option_font, fill=(255, 255, 255), anchor='mm')
        
        self._draw_status_bar()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None


class MainMenuPage(Menu):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict, callbacks:dict, general_config:dict)->None:
        self.class_logger.info("initialise MainMenuPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        # Associate general high level attribute to 'self'
        for key, value in general_config.items():
            setattr(self, key, value)
        
        super().__init__(config)
        self._config = config
        
        self.menu_parameters = {
            "top_offset"  : 32,
            "step"        : 60,
            "text_middle" : 8,
            "text_left"   : 64,
            "bbox_middle" : 72,
            "bbox_height" : 60,
            "bbox_left"   : 0,
            "bbox_right"  : 300,
            "bbox_radius" : 12,
            "bbox_lw"     : 3,
            "icon"        : True,
            "icon_middle" : 12,
            "icon_left"   : 6,
            "font_size"   : "L",
            "max_line"    : 3,
            }
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {**self.keys_callbacks, **callbacks["keys_callbacks"]}
        
        # Set callbacks for navigation
        self.page_callbacks = {**self.page_callbacks, **callbacks["page_callbacks"]}
        
        self.action = lambda: None
        return None
    
    def display(self)->None:
        self.class_logger.info("display MainMenuPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        self._draw_status_bar()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def navigate(self, direction:str)->None:
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None


class ShutdownPage(Button):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict, callbacks:dict, general_config:dict)->None:
        self.class_logger.info("initialise ShutdownPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        # Associate general high level attribute to 'self'
        for key, value in general_config.items():
            setattr(self, key, value)
        
        super().__init__(config)
        self._config = config
        
        self.button_pose = {**self.button_pose,
            "pad_x"  : 15,
            "pad_y"  : 10,
            "radius" : 12
            }
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {**self.keys_callbacks, 'select': self.select, **callbacks["keys_callbacks"]}
        
        # Set callbacks for navigation
        self.page_callbacks = {**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        return None
    
    def select(self)->None:
        self.class_logger.info("handle shutdown button selection",
                               extra={'className':f"{self.__class__.__name__}:"})
        action = self.button_options[self.current_button]['action']
        
        if action in self.page_callbacks.keys():
            self.class_logger.debug(f"action '{action}'",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.page_callbacks[action](action)
        elif action in self.keys_callbacks.keys():
            self.class_logger.debug(f"action '{action}'",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.keys_callbacks[action]()
        else:
            self.class_logger.debug("no action to trigger",
                                    extra={'className':f"{self.__class__.__name__}:"})
        return None
    
    def navigate(self, direction:str)->None:
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None
    
    def display(self)->None:
        self.class_logger.info("display ShutdownPage",
                               extra={'className':f"{self.__class__.__name__}:"})
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


class SequenceParameterPage(Page):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict, callbacks:dict, general_config:dict)->None:
        self.class_logger.info("initialise SequenceParameterPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        # Associate general high level attribute to 'self'
        for key, value in general_config.items():
            setattr(self, key, value)
        
        super().__init__(config)
        self._config = config
        
        # self.parameters_pose = {
        #     "left"       : 12,
        #     "top"        : 52,
        #     "font_size"  : "M",
        #     "step"       : 32,
        #     "pad_x"      : 14,
        #     "pad_y"      : 14,
        #     "offset"     : 8,
        #     "radius"     : 12,
        #     "box_length" : 100,
        #     'right'  : max([
        #         ImageDraw.Draw(self.LCD.screen_img).textbbox((12, 0), param['name'],
        #                        font=self.FONTS["PixelOperatorBold_M"], anchor='lm')[2]
        #         for param in self.parameter_options]),
        #     }
        
        # Set callbacks for navigation keys
        try:
            self.keys_callbacks = {
                **self.keys_callbacks,
                'select' : {'button':self.launch_sequence},
                'back' : self.option_back,
                'up' : self.option_up,
                'down' : self.option_down,
                **callbacks["keys_callbacks"],
                }
        except AttributeError:
            self.class_logger.warning("keys_callbacks doesn't existe",
                                      extra={'className':f"{self.__class__.__name__}:"})
            self.keys_callbacks = {
                'select' : {'button':self.launch_sequence},
                'back' : self.option_back,
                'up' : self.option_up,
                'down' : self.option_down,
                **callbacks["keys_callbacks"],
                }
        
        # Set callbacks for navigation
        self.page_callbacks = {**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        
        self._input_type = {'number': Numpad, 'text': Keyboard}
        self.options = [self._input_type[parameter['type']](parameter) for parameter in self._config['parameters']]
        self.options = sorted(self.options, key=self._sorted_option)
        self.current_option = 0
        
        self.tmp_param_file = "../tmp/sequence_parameters.tmp"
        return None
    
    def _sorted_option(self, _in:dict)->int:
        return _in._pose
    
    def activate_options(self)->None:
        self.class_logger.info("activate usefull options",
                               extra={'className':f"{self.__class__.__name__}:"})
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
    
    def select(self)->None:
        self.class_logger.info("handle selection action",
                               extra={'className':f"{self.__class__.__name__}:"})
        action = self.button_options[self.current_button]['action']
        if action in self.page_callbacks.keys():
            self.class_logger.debug(f"action '{action}'",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.page_callbacks[action](action)
        elif action in self.keys_callbacks.keys():
            self.class_logger.debug(f"action '{action}'",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.keys_callbacks[action]()
        else:
            self.class_logger.debug("no action to trigger",
                                    extra={'className':f"{self.__class__.__name__}:"})
        return None
    
    def option_back(self)->None:
        option = self.options_list[self.current_option]
        if option == 'parameter' and self.parameter_seleceted:
            self.parameter_select()
        else:
            self.keys_callbacks['go_back']()
        return None
    
    def option_up(self)->None:
        self.class_logger.info("move current option up",
                               extra={'className':f"{self.__class__.__name__}:"})
        if not self.parameter_seleceted:
            self.current_option = (self.current_option-1)%len(self.options_list)
        self.action = self.options_callbacks[self.options_list[self.current_option]]['up']
        if type(self.action) == list:
            self.action = self.action[self.parameter_seleceted]
        self.activate_options()
        self.action()
        return None
    
    def option_down(self)->None:
        self.class_logger.info("move current option down",
                               extra={'className':f"{self.__class__.__name__}:"})
        if not self.parameter_seleceted:
            self.current_option = (self.current_option+1)%len(self.options_list)
        self.action = self.options_callbacks[self.options_list[self.current_option]]['down']
        if type(self.action) == list:
            self.action = self.action[self.parameter_seleceted]
        self.activate_options()
        self.action()
        return None
    
    def launch_sequence(self)->None:
        self.class_logger.info("write parameters for SequenceRunningPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        seq_param = {param['name'].lower():{'value':param['value'], 'unit':param['unit']} for param in self.parameter_options}
        seq_param['offset'] = {'value':300, 'unit':'ms'}  # TODO: Get this parameter from settings_config.json
        
        shots = seq_param['shots']['value']
        offset = seq_param['offset']['value'] * UNIT_CONVERTER[seq_param['offset']['unit']]
        exposure = seq_param['exposure']['value'] * UNIT_CONVERTER[seq_param['exposure']['unit']]
        interval = seq_param['interval']['value'] * UNIT_CONVERTER[seq_param['interval']['unit']]
        
        start_time = time.time()
        running_time = shots * (offset+exposure) + (shots-1) * interval
        end_time = start_time + running_time + 2*offset + 0.1
        time_param = {"start":start_time, "end":end_time}
        
        parameters = {"sequence_parameters":seq_param,
                      "sequence_time":time_param}
        os.makedirs(os.path.dirname(self.tmp_param_file), exist_ok=True)
        with open(self.tmp_param_file, 'w') as f:
            json.dump(parameters, f)
        
        action = "sequence_running_page"
        self.page_callbacks[action](action)
        return None
    
    def navigate(self, direction:str)->None:
        self.class_logger.info(f"navigate '{direction}' into sequence parameter page options",
                               extra={'className':f"{self.__class__.__name__}:"})
        try:
            if self.keys[direction] not in ['', 'none']:
                self.action = self.keys_callbacks[self.keys[direction]]
            if type(self.action) == dict:
                self.action = self.action[self.options_list[self.current_option]]
            self.class_logger.debug(f"execute '{self.action.__name__}'",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.action()
        except KeyError as e:
            self.class_logger.error(f"KeyError: {e}")
        return None
    
    def display(self)->None:
        self.class_logger.info("display SequenceParameterPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        self._draw_status_bar()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None


class SequenceRunningPage(Button):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict, callbacks:dict, general_config:dict)->None:
        self.class_logger.info("initialise SequenceRunningPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        # Associate general high level attribute to 'self'
        for key, value in general_config.items():
            setattr(self, key, value)
        
        super().__init__(config)
        self._config = config
        
        self.button_pose = {**self.button_pose,
            "pad_x"  : 10,
            "pad_y"  : 10,
            "radius" : 6
            }
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {
            **self.keys_callbacks,
            **callbacks["keys_callbacks"],
            }
        
        # Set callbacks for navigation
        self.page_callbacks = {**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        
        self.tmp_param_file = "../tmp/sequence_parameters.tmp"
        self.tmp_locker_file = "../tmp/tmp.lock"
        self.lock = filelock.FileLock(self.tmp_locker_file)
        return None
    
    def navigate(self, direction:str)->None:
        self.class_logger.info("navigate into sequence running page options",
                               extra={'className':f"{self.__class__.__name__}:"})
        try:
            if self.keys[direction] not in ['', 'none']:
                if type(self.keys_callbacks[self.keys[direction]]) is list:
                    self.action = self.keys_callbacks[self.keys[direction]][self.parameter_seleceted]
                else:
                    self.action = self.keys_callbacks[self.keys[direction]]
        except KeyError as e:
            self.class_logger.error(f"KeyError: {e}",
                                    extra={'className':f"{self.__class__.__name__}:"})
            return None
        if self.action.__name__ == "go_back":
            self.trigger_process.terminate()
            self.interrupt_event.set()
            self.trigger_process.join()
            self.display_thread.join()
            trigger._release_gpio()
            self.class_logger.warning("Interrupt sequence",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.action = self.keys_callbacks['go_back']
        self.action()
        return None
    
    def run_sequence(self)->None:
        self.class_logger.info("Launch sequence",
                               extra={'className':f"{self.__class__.__name__}:"})
        try:
            with open(self.tmp_param_file, 'r') as f:
                self.sequence_parameters = json.load(f)
        except FileNotFoundError as e:
            self.class_logger.warning(f"File not found: {e}",
                                      extra={'className':f"{self.__class__.__name__}:"})
            return None
        # self.LCD.set_bl_DutyCycle(7.5) # Save power consumption
        self._nb_shots = self.sequence_parameters['sequence_parameters']['shots']['value']
        self._exposure = self.sequence_parameters['sequence_parameters']['exposure']
        self._time_exp = self._exposure['value'] * UNIT_CONVERTER[self._exposure['unit']]
        self._end_time = self.sequence_parameters['sequence_time']['end']
        
        self.PROCESS_DICT = {'trigger':{'target':trigger.execute_sequence,
                                        'args':(self.sequence_parameters['sequence_parameters'],)},
                              'display':{'target':self.display_running,
                                        'args':()}
                              }
        self.interrupt_event = threading.Event()
        self.watcher_thread = threading.Thread(target=self.run_join)
        self.watcher_thread.start()
        return None
    
    def run_join(self)->None:
        self.trigger_process = multiprocessing.Process(target=trigger.execute_sequence,
                                                   args=(self.sequence_parameters['sequence_parameters'],))
        self.display_thread = threading.Thread(target=self.display_running)
        
        self.trigger_process.start()
        self.display_thread.start()
        
        self.trigger_process.join()
        self.display_thread.join()
        return None
    
    def display_running(self)->None:
        Ti = time.time()
        while self.trigger_process.is_alive() and not self.interrupt_event.is_set():
            if (time.time()-Ti) > min(self.UPDATE_TIMES["sequence_running"], self._time_exp/2):
                self.class_logger.info("display screen while running",
                                       extra={'className':f"{self.__class__.__name__}:"})
                try:
                    with self.lock:
                        with open("../tmp/running_parameters.tmp", 'r') as f:
                            running_track = json.load(f)
                except FileNotFoundError as e:
                    self.class_logger.warning(f"File not found: {e}",
                                              extra={'className':f"{self.__class__.__name__}:"})
                    return True
                
                super().display()
                self._running_screen(running_track['taken'])
                self._draw_status_bar()
                self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
                Ti = time.time()
            else:
                time.sleep(self.UPDATE_TIMES["thread_scan"])
        if not self.interrupt_event.is_set():
            self.class_logger.warning("end sequence",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.class_logger.warning(f"End time error (estimated-real): {self._end_time-time.time():.6f}s",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.action = self.keys_callbacks['go_back']
            self.action()
        return None
    
    def _running_screen(self, taken:int)->None:
        fill = (255,255,255)
        text_font = self.FONTS["PixelOperator_M"]
        number_font = self.FONTS["PixelOperatorBold_M"]
        draw = ImageDraw.Draw(self.LCD.screen_img)
        # Current shot traking
        draw.text((12, 50), "Shot:", fill=fill, font=text_font, anchor='lm', align='center')
        draw.text((110, 50), f"{taken+1}/{self._nb_shots}", fill=fill, font=number_font, anchor='lm', align='center')
        # Exposed time tracking
        time_exposed = trigger.time2str(seconds=taken*self._time_exp, fmt='(s)s')
        draw.text((12, 75), "Exposure:", fill=fill, font=text_font, anchor='lm', align='center')
        draw.text((110, 75), f"{time_exposed}", fill=fill, font=number_font, anchor='lm', align='center')
        # Time left tracking
        draw.text((12, 110), "Time left:", fill=fill, font=text_font, anchor='lm', align='center')
        time_left = trigger.time2str(seconds=max(0, self._end_time-time.time()), fmt='(*h)h (*m)min (s)s')
        draw.text((int(self.LCD.height/2), 140), f"{time_left}",
                  fill=(255,255,255), font=self.FONTS["PixelOperatorBold_L"], anchor='mm', align='center')
        return None
    
    def display(self)->None:
        self.class_logger.warning("display SequenceRunningPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        if os.path.isfile(self.tmp_param_file):
            self.run_sequence()
        else:
            self.class_logger.warning("no temporary exchange file found...",
                                      extra={'className':f"{self.__class__.__name__}:"})
            self.LCD._reset_frame()
            draw = ImageDraw.Draw(self.LCD.screen_img)
            icon = Image.open(f"{self.PATH_ASSETS}Icon_Empty.png").resize((130, 130), Image.Resampling.NEAREST)
            icon_pose = (int((self.LCD.size[1] - icon.size[0])/2),
                         int((self.LCD.size[0] - icon.size[0]+34)/2 ))
            self.LCD.screen_img.paste(icon, icon_pose)
            
            text_font = self.FONTS["PixelOperator_M"]
            text_pose = (8, 40)
            draw.text(text_pose, "Error 404:\n'../tmp/sequence_parameters.tmp'\nfile  not found !",
                      fill=(255,255,255), font=text_font, align='center')
        
            self._draw_status_bar()
            self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None


class WifiPage(Picture):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict, callbacks:dict, general_config:dict)->None:
        self.class_logger.info("initialise WifiPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        # Associate general high level attribute to 'self'
        for key, value in general_config.items():
            setattr(self, key, value)
        
        super().__init__(config)
        self._config = config
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {**self.keys_callbacks, **callbacks["keys_callbacks"]}
        
        # Set callbacks for navigation
        self.page_callbacks = {**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        return None
    
    def get_wifi_QRCode(self)->None:
        self.class_logger.info("generate wifi connection QRCode",
                               extra={'className':f"{self.__class__.__name__}:"})
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
    
    def navigate(self, direction:str)->None:
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None
    
    def display(self)->None:
        self.class_logger.info("display WifiPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.get_wifi_QRCode()
        super().display()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None


class SmartphonePage(Picture):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict, callbacks:dict, general_config:dict)->None:
        self.class_logger.info("initialise SmartphonePage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        # Associate general high level attribute to 'self'
        for key, value in general_config.items():
            setattr(self, key, value)
        
        super().__init__(config)
        self._config = config
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {**self.keys_callbacks, **callbacks["keys_callbacks"]}
        
        # Set callbacks for navigation
        self.page_callbacks = {**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        return None
    
    def get_website_QRCode(self)->None:
        self.class_logger.info("generate website connection QRCode",
                               extra={'className':f"{self.__class__.__name__}:"})
        if os.path.exists(self.PATH_WEBSITE['path']):
            file_values = subprocess.check_output(f"sudo cat {self.PATH_WEBSITE['path']}", shell=True).decode('utf-8')
            id_paragraphe = file_values.find('#static IP')
            paragraphe = file_values[id_paragraphe:]
            WEBSITE_CONFIG = {'ip'   : paragraphe[paragraphe.find('=')+1:paragraphe.find('=')+11],
                              'port' : self.PATH_WEBSITE['port']}
        else:
            WEBSITE_CONFIG = {'ip'   :'255.255.255.255',
                                   'port' :'65535',
                                   }
        
        self._generate_QRCode(f"HTTP:{WEBSITE_CONFIG['ip']}:{WEBSITE_CONFIG['port']}")
        return None
    
    def navigate(self, direction:str)->None:
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None
    
    def display(self)->None:
        self.class_logger.info("display SmartphonePage",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.get_website_QRCode()
        super().display()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None


# TODO: Make a setting to switch RPi between access point to wifi mode
# TODO: Make a setting to enable user to connect a spacific website to add wifi
#       router ssid and passphrase for internet access on wifi mode
# TODO: Make a setting to check updates, only on wifi mode
class SettingPage(Menu):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict, callbacks:dict, general_config:dict)->None:
        self.class_logger.info("initialise MainMenuPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        # Associate general high level attribute to 'self'
        for key, value in general_config.items():
            setattr(self, key, value)
        
        super().__init__(config)
        self._config = config
        
        self.menu_parameters = {
            "top_offset"  : 32,
            "step"        : 32,
            "text_left"   : 16,
            "text_middle" : 4,
            "bbox_left"   : 6,
            "bbox_middle" : 38,
            "bbox_height" : 35,
            "bbox_right"  : 300,
            "bbox_radius" : 8,
            "bbox_lw"     : 2,
            "icon"        : False,
            "font_size"   : "M",
            "max_line"    : -1,
            }
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {**self.keys_callbacks, **callbacks["keys_callbacks"]}
        
        # Set callbacks for navigation
        self.page_callbacks = {**self.page_callbacks, **callbacks["page_callbacks"]}
        
        self.action = lambda: None
        return None
    
    def display(self)->None:
        self.class_logger.info("display MainMenuPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        self._draw_status_bar()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def navigate(self, direction:str)->None:
        self.class_logger.info("Navigate into SettingPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.class_logger.info(f"Execute: '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.action()
        return None


class BatteryPage(Info):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict, callbacks:dict, general_config:dict)->None:
        self.class_logger.info("initialise BatteryPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        # Associate general high level attribute to 'self'
        for key, value in general_config.items():
            setattr(self, key, value)
        
        super().__init__(config)
        self._config = config
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {**self.keys_callbacks, **callbacks["keys_callbacks"]}
        
        # Set callbacks for navigation
        self.page_callbacks = {**self.page_callbacks, **callbacks["page_callbacks"]}
        
        self.action = lambda: None
        
        self.MAX17043_is_active = True
        try:
            self.fuel_gauge = max17043(busnum=1, address=0x36)
            self.fuel_gauge.getVCell()
        except OSError as e:
            self.class_logger.error(f"OSError: {e}, I2C device MAX17043 (addr {hex(self.fuel_gauge._address)}) not responding",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.MAX17043_is_active = False
        self.INA2___is_active = True
        try:
            self.powermeter = INA2__(busnum=1, address=0x42, max_expected_amps=2.7, shunt_ohms=30e-3)
            self.powermeter.configure()
        except BaseException as e:
            self.class_logger.error(f"Error: {e}, I2C device INA219 (addr {hex(self.powermeter._address)}) not responding",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.INA2___is_active = False
        return None
    
    def update_infos(self)->None:
        self.class_logger.info("Update battery and power infos",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        # TODO: Split line for static and moving part to add dynamic coloration
        #       to values: blue, green, orange, red
        # TODO: Replace value by '--' or 'xx' when a module is not connected and
        #       display an error message inline in red
        super().display()
        draw = ImageDraw.Draw(self.LCD.screen_img)
        
        if not (self.MAX17043_is_active or self.INA2___is_active):
            self.LCD.screen_img.paste(self.default_icon, (160-int(self.default_icon.width/2), 45))
            
            option_font = self.FONTS["PixelOperator_M"]
            option_text = "I2C communication error\n"
            option_text += f"with MAX17043 (addr {hex(self.fuel_gauge._address)})"
            option_text += f"and with INA219 (addr {hex(self.powermeter._address)})"
            option_pos = (16, 100)
            draw.text(option_pos, option_text, font=option_font, fill=(255, 0, 0))
            self._draw_status_bar()
            self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
            self.interrupt_event.set()
        
        Ti = time.time()
        while not self.interrupt_event.is_set():
            if (time.time()-Ti) > self.UPDATE_TIMES['battery_infos']:
                super().display()
                draw = ImageDraw.Draw(self.LCD.screen_img)
                
                option_text = ""
                if self.MAX17043_is_active:
                    option_text += f"Cell voltage: {self.fuel_gauge.getVCell():.2f} V\n"
                    option_text += f"State of charge: {self.fuel_gauge.getSoc():.1f} %\n"
                else:
                    option_text += "Cell voltage: -- V\n"
                    option_text += "State of charge: -- %\n"
                if self.INA2___is_active:
                    option_text += f"RPi current: {self.powermeter.current():.1f} mA\n"
                    option_text += f"RPi power: {self.powermeter.power():.1f} mW\n"
                else:
                    option_text += "RPi current: -- mA\n"
                    option_text += "RPi power: -- mW\n"
        
                option_font = self.FONTS["PixelOperator_M"]
                option_pos = (16, 50)
                draw.text(option_pos, option_text, font=option_font, fill=(255, 255, 255))
                
                self._draw_status_bar()
                self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
                Ti = time.time()
            time.sleep(self.UPDATE_TIMES['thread_scan'])
        return None
    
    def navigate(self, direction:str)->None:
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        if (self.action.__name__ == "go_back") and not self.interrupt_event.is_set():
            self.interrupt_event.set()
            self.update_thread.join()
        self.action()
        return None
    
    def display(self)->None:
        self.class_logger.info("display BatteryPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.interrupt_event = threading.Event()
        self.update_thread = threading.Thread(target=self.update_infos)
        self.update_thread.start()
        return None


class WifiPasswordPage(Parameter):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, config:dict, callbacks:dict, general_config:dict)->None:
        self.class_logger.info("initialise MainMenuPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        # Associate general high level attribute to 'self'
        for key, value in general_config.items():
            setattr(self, key, value)
        
        super().__init__(config)
        self._config = config
        
        # self.parameters_pose = {
        #     "left"       : 12,
        #     "top"        : 52,
        #     "font_size"  : "M",
        #     "step"       : 32,
        #     "pad_x"      : 14,
        #     "pad_y"      : 14,
        #     "offset"     : 8,
        #     "radius"     : 12,
        #     "box_length" : 100,
        #     'right'  : max([
        #         ImageDraw.Draw(self.LCD.screen_img).textbbox((12, 0), param['name'],
        #                        font=self.FONTS["PixelOperatorBold_M"], anchor='lm')[2]
        #         for param in self.parameter_options]),
        #     }
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {#**self.keys_callbacks,
                               # "up":self.keyboard_up,
                               # "down":self.keyboard_down,
                               # "right":self.keyboard_right,
                               # "left":self.keyboard_left,
                               # "select":self.keyboard_select,
                                **callbacks["keys_callbacks"]}
        
        # Set callbacks for navigation
        self.page_callbacks = {**self.page_callbacks,**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        return None
    
    def display(self)->None:
        self.class_logger.info("display MainMenuPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        self._draw_status_bar()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def navigate(self, direction:str)->None:
        self.class_logger.info("Navigate into SettingPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.class_logger.info(f"Execute: '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.action()
        return None


class PageManager:
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, UI_config_path:str, general_config:dict)->None:
        self.class_logger.info("initialise PageManager",
                               extra={'className':f"{self.__class__.__name__}:"})
        self._general_config = general_config
        self.QUIT = False
        
        with open(UI_config_path, 'r') as f:
            self.pages_structure = json.load(f)
        
        self.pages = {}
        self.current_page = None
        self.page_stack = []
        
        # Set class correspondance dict
        self.class_dict = {
            "ComingSoonPage"        : ComingSoonPage,
            "MainMenuPage"          : MainMenuPage,
            "ShutdownPage"          : ShutdownPage,
            "SequenceParameterPage" : SequenceParameterPage,
            "SequenceRunningPage"   : SequenceRunningPage,
            "SettingPage"           : SettingPage,
            "WifiPage"              : WifiPage,
            "SmartphonePage"        : SmartphonePage,
            "BatteryPage"           : BatteryPage,
            "WifiPasswordPage"      : WifiPasswordPage,
            }
        
        # Define interface level keys callback function
        self.keys_callbacks = {
            "go_back"  : self.go_back,
            "shutdown" : self.shutdown,
            }
        # Define interface level page callback function
        self.page_callbacks = {key:self.show_page for key in self.pages_structure.keys()}
        
        self.callbacks = {
            "keys_callbacks" : self.keys_callbacks,
            "page_callbacks" : self.page_callbacks,
            }
        
        self.stop_event = threading.Event()
        self.battery_SoC_thread = SoCMonitor(self.stop_event, self._general_config)
        self.battery_SoC_thread.start()
        
        self.load_pages()
        return None
    
    def load_pages(self)->None:
        self.class_logger.info("generate pages based on config file",
                               extra={'className':f"{self.__class__.__name__}:"})
        for page_key, page_data in self.pages_structure.items():
            self.pages[page_key] = self.class_dict[page_data["class"]](page_data, self.callbacks, self._general_config)
        return None
    
    def show_page(self, page_key:str=None)->None:
        self.class_logger.info(f"keep track of page history, showing page {page_key}",
                               extra={'className':f"{self.__class__.__name__}:"})
        if self.current_page:
            self.page_stack.append(self.current_page)
        
        self.current_page = self.pages[page_key]
        self.current_page.display()
        return None
    
    def go_back(self)->None:
        self.class_logger.info("move to previous history page",
                               extra={'className':f"{self.__class__.__name__}:"})
        if self.page_stack:
            self.current_page = self.page_stack.pop()
            self.current_page.display()
        return None
    
    def shutdown(self)->None:
        self.class_logger.info("shutdown PageManager",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.stop_event.set()
        if self.battery_SoC_thread.is_alive():
            self.battery_SoC_thread.join()
        self.QUIT = True
        return None


class SoCMonitor(threading.Thread):
    class_logger = logging.getLogger('classLogger')
    
    def __init__(self, event:threading.Event, general_config:dict)->None:
        self.class_logger.debug("initialise battery monitoring thread",
                               extra={'className':f"{self.__class__.__name__}:"})
        super(SoCMonitor, self).__init__()
        self._stop_event = event
        
        # Associate general high level attribute to 'self'
        for key, value in general_config.items():
            setattr(self, key, value)
        return None
    
    def run(self)->None:
        self.class_logger.info("Start thread wor",
                               extra={'className':f"{self.__class__.__name__}:"})
        global BATTERY_SOC
        global BATTERY_VOLTAGE
        fuel_gauge = max17043(busnum=1, address=0x36)
        Ti = time.time()-self.UPDATE_TIMES["battery_SoC"]
        try:
            while not self._stop_event.is_set():
                if (time.time()-Ti) > self.UPDATE_TIMES["battery_SoC"]:
                    BATTERY_SOC = fuel_gauge.getSoc()
                    BATTERY_VOLTAGE = fuel_gauge.getVCell()
                    self.class_logger.info(f"Battery SoC: {BATTERY_SOC:.2f}%; Battery voltage: {BATTERY_VOLTAGE:.3f} V",
                                           extra={'className':f"{self.__class__.__name__}:"})
                    Ti = time.time()
                else:
                    pass
                time.sleep(self.UPDATE_TIMES["thread_scan"])
        except OSError as e:
            self.class_logger.error(f"OSError: {e}, I2C device (addr {hex(fuel_gauge._address)}) not responding",
                                    extra={'className':f"{self.__class__.__name__}:"})
        fuel_gauge.deinit()
        return None