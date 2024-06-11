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
import logging.config
import subprocess
import numpy as np
from PIL import Image, ImageDraw

import lib.Trigger as trigger

OPERATING_SYSTEM = os.uname()
RUN_ON_RPi = (OPERATING_SYSTEM.sysname == 'Linux') and (OPERATING_SYSTEM.machine in ['aarch64', 'armv6l'])

if RUN_ON_RPi:
    BYPASS_BUILTIN_SCREEN = False
else:
    BYPASS_BUILTIN_SCREEN = True


SCRIPT_NAME = __file__.split('/')[-1]

logging.config.fileConfig('logging.conf')
lib_logger = logging.getLogger('libLogger')
lib_logger.debug("Imported file")


class Page:
    class_logger = logging.getLogger('classLogger')
    def __init__(self, page_config:dict):
        self.class_logger.info("initialise utils attributes for the page",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        self.title = page_config["title"]
        
        self.keys = page_config["keys"]
        
        # Set callbacks for navigation
        self.page_callbacks = {}
        
        self.BATTERY_LEVEL = 47
        self.STATUS_TXT    = "Ready to GO !"
        return None
    
    def _get_battery_icon(self):
        self.class_logger.debug("get the appropriate battery icon",
                                extra={'className':f"{self.__class__.__name__}:"})
        auth_level = np.array(list(self.BATTERY_DICT.keys()))
        auth_level[::-1].sort()
        
        if self.BATTERY_LEVEL>auth_level[-1]:
            arg = np.argmax(auth_level<self.BATTERY_LEVEL)
        else:
            arg = -1
        return self.BATTERY_DICT[auth_level[arg]]
    
    def _draw_status_bar(self):
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
    
    def display(self):
        self.class_logger.info("initialise new LCD image",
                               extra={'className':f"{self.__class__.__name__}:"})
        # Generate an image representing the page
        self.LCD.screen_img = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0, 0, 0, 255))
        return None
    
    def navigate(self, direction):
        self.class_logger.info("navigate in the page",
                                extra={'className':f"{self.__class__.__name__}:"})
        if direction in self.keys.keys():
            if self.keys[direction] not in ['', 'none']:
                self.class_logger.debug("callback function '{self.keys[direction]}'",
                                        extra={'className':f"{self.__class__.__name__}:"})
                self.action = self.keys_callbacks[self.keys[direction]]
        return None


class Menu(Page):
    class_logger = logging.getLogger('classLogger')
    def __init__(self, config):
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
    
    def menu_up(self):
        self.class_logger.info("move menu up",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_menu = (self.current_menu - 1) % len(self.menu_options)
        self.display()
        return None
    
    def menu_down(self):
        self.class_logger.info("move menu down",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_menu = (self.current_menu + 1) % len(self.menu_options)
        self.display()
        return None
    
    def menu_select(self):
        self.class_logger.info("handle menu selection callbacks",
                               extra={'className':f"{self.__class__.__name__}:"})
        action = self.menu_options[self.current_menu]["action"]
        if action not in ['', 'none']:
            self.class_logger.debug("action '{action}'",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.page_callbacks[action](action)
        else:
            self.class_logger.debug("no action to trigger",
                                    extra={'className':f"{self.__class__.__name__}:"})
        return None
    
    def display(self):
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
    def __init__(self, config):
        self.class_logger.info("initialise menu specific options",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().__init__(config)
        self._config = config
        
        self.button_config = self._config["buttons"]
        self.button_options = self.button_config["options"]
        
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
    
    def button_up(self):
        self.class_logger.info("move to the next button",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_button = (self.current_button - 1) % len(self.button_options)
        self.display()
        return None
    
    def button_down(self):
        self.class_logger.info("move to the previous button",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_button = (self.current_button + 1) % len(self.button_options)
        self.display()
        return None
    
    def button_select(self):
        self.class_logger.info("handle menu selection callbacks",
                               extra={'className':f"{self.__class__.__name__}:"})
        action = self.menu_options[self.current_button]["action"]
        if action not in ['', 'none']:
            self.class_logger.debug("action '{action}'",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.page_callbacks[action](action)
        else:
            self.class_logger.debug("No action yet !",
                                    extra={'className':f"{self.__class__.__name__}:"})
        return None
    
    def display(self):
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


class Parameter(Page):
    class_logger = logging.getLogger('classLogger')
    def __init__(self, config):
        self.class_logger.info("initialise parameter specific options",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().__init__(config)
        self._config = config
        
        self.parameter_config = self._config["parameters"]
        self.parameter_options = self.parameter_config["options"]
        
        self.current_parameter = 0
        self.parameter_seleceted = 0
        self.parameter_active = True
        
        self.parameters_pose = {}
        
        # Set callbacks for navigation keys
        try:
            self.keys_callbacks = {
                **self.keys_callbacks,
                'parameter_up'   : [self.parameter_up, self.parameter_increment],
                'parameter_down' : [self.parameter_down, self.parameter_decrement],
                }
        except AttributeError:
            self.class_logger.warning("keys_callbacks doesn't existe",
                                      extra={'className':f"{self.__class__.__name__}:"})
            self.keys_callbacks = {
                'parameter_up'   : [self.parameter_up, self.parameter_increment],
                'parameter_down' : [self.parameter_down, self.parameter_decrement],
                }
        return None
    
    def parameter_up(self):
        self.class_logger.info("move current parameter up",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_parameter = (self.current_parameter - 1) % len(self.parameter_options)
        self.display()
        return None
    
    def parameter_down(self):
        self.class_logger.info("move current parameter down",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.current_parameter = (self.current_parameter + 1) % len(self.parameter_options)
        self.display()
        return None
    
    def parameter_select(self):
        self.class_logger.info("handle parameter selection callbacks",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.parameter_seleceted = (self.parameter_seleceted+1)%2
        self.class_logger.debug("Selected {bool(self.parameter_seleceted)}",
                                extra={'className':f"{self.__class__.__name__}:"})
        self.display()
        return None
    
    def parameter_increment(self):
        self.class_logger.info("increase current parameter value",
                               extra={'className':f"{self.__class__.__name__}:"})
        parameter = self.parameter_options[self.current_parameter]
        value = parameter['value']
        step = parameter['step']
        parameter['value'] = max(0, value + step)
        self.display()
        return None
    
    def parameter_decrement(self):
        self.class_logger.info("decrease current parameter value",
                               extra={'className':f"{self.__class__.__name__}:"})
        parameter = self.parameter_options[self.current_parameter]
        value = parameter['value']
        step = parameter['step']
        parameter['value'] = max(0, value - step)
        self.display()
        return None
    
    def navigate(self, direction):
        self.class_logger.info("navigate in the parameters",
                               extra={'className':f"{self.__class__.__name__}:"})
        try:
            if self.keys[direction] not in ['', 'none']:
                if type(self.keys_callbacks[self.keys[direction]]) is list:
                    self.action = self.keys_callbacks[self.keys[direction]][self.parameter_seleceted]
                else:
                    self.action = self.keys_callbacks[self.keys[direction]]
        except KeyError as e:
            self.class_logger.error(f"KeyError: {e}")
        return None
    
    def display(self):
        self.class_logger.info("add parameter elements to the display",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        draw = ImageDraw.Draw(self.LCD.screen_img)
        # Add parameters with values
        for i in range(len(self.parameter_options)):
            parameter = self.parameter_options[i]
            
            if i == self.current_parameter:
                font = self.FONTS["PixelOperatorBold_M"]
            else:
                font = self.FONTS["PixelOperator_M"]
            
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
                              font=self.FONTS["PixelOperatorBold_M"],
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
    class_logger = logging.getLogger('classLogger')
    def __init__(self, config):
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
    
    def _set_pose(self):
        self.class_logger.info("compute image position in screen",
                               extra={'className':f"{self.__class__.__name__}:"})
        if 'position' in self.picture_options.keys():
            self.pose = self.picture_options['position']
        else:
            self.pose = (int((self.LCD.screen_img.width-self.picture.height)/2),
                         int((self.LCD.screen_img.height-self.picture.height)/2))
        return None
    
    def _generate_QRCode(self, text=""):
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
    
    def display(self):
        self.class_logger.info("add picture to the display",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        
        self.LCD.screen_img.paste(self.picture, self.pose)
        return None

# TODO: Create a class Info() to handle general information display
class Info(Page):
    class_logger = logging.getLogger('classLogger')
    def __init__(self, config):
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
    
    def navigate(self, direction):
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None
    
    def display(self):
        self.class_logger.info("add infos to the display",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        return None



class ComingSoonPage(Page):
    class_logger = logging.getLogger('classLogger')
    def __init__(self, config, callbacks, general_config):
        self.class_logger.info("initialise ComingSoonPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        # Associate general high level attribute to 'self'
        for key, value in general_config.items():
            setattr(self, key, value)
        
        super().__init__(config)
        self._config = config
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {**callbacks["keys_callbacks"]}
        return None
    
    def navigate(self, direction):
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None
    
    def display(self):
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
    def __init__(self, config, callbacks, general_config):
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
    
    def display(self):
        self.class_logger.info("display MainMenuPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        self._draw_status_bar()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def navigate(self, direction):
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None


class ShutdownPage(Button):
    class_logger = logging.getLogger('classLogger')
    def __init__(self, config, callbacks, general_config):
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
    
    def select(self):
        self.class_logger.info("handle shutdown button selection",
                               extra={'className':f"{self.__class__.__name__}:"})
        action = self.button_options[self.current_button]['action']
        
        if action in self.page_callbacks.keys():
            self.class_logger.debug("action '{action}'",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.page_callbacks[action](action)
        elif action in self.keys_callbacks.keys():
            self.class_logger.debug("action '{action}'",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.keys_callbacks[action]()
        else:
            self.class_logger.debug("no action to trigger",
                                    extra={'className':f"{self.__class__.__name__}:"})
        return None
    
    def navigate(self, direction):
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None
    
    def display(self):
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


# TODO: When sequence is paused by sequenceRunningPage, the class need to check
#       the sequence_finish boolean to let 'continue' button appear or not
class SequenceParameterPage(Parameter, Button):
    class_logger = logging.getLogger('classLogger')
    def __init__(self, config, callbacks, general_config):
        self.class_logger.info("initialise SequenceParameterPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        # Associate general high level attribute to 'self'
        for key, value in general_config.items():
            setattr(self, key, value)
        
        super().__init__(config)
        self._config = config
        
        self.parameters_pose = {
            "left"       : 12,
            "top"        : 52,
            "font_size"  : "M",
            "step"       : 32,
            "pad_x"      : 14,
            "pad_y"      : 14,
            "offset"     : 8,
            "radius"     : 12,
            "box_length" : 100,
            'right'  : max([
                ImageDraw.Draw(self.LCD.screen_img).textbbox((12, 0), param['name'],
                               font=self.FONTS["PixelOperatorBold_M"], anchor='lm')[2]
                for param in self.parameter_options]),
            }
            
        self.button_pose = {**self.button_pose,
            "pad_x"  : 10,
            "pad_y"  : 10,
            "radius" : 6
            }
        
        # Set callbacks for navigation keys
        self.keys_callbacks = {
            **self.keys_callbacks,
            'select' : {'button':self.run_sequence, 'parameter':self.parameter_select},
            'back' : {'button':callbacks["keys_callbacks"]['go_back'], 'parameter':self.parameter_select},
            'up' : self.option_up,
            'down' : self.option_down,
            **callbacks["keys_callbacks"],
            }
        
        # Set callbacks for navigation
        self.page_callbacks = {**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        
        self.options_list = [
            *['parameter']*len(self.parameter_options),
            *['button']*len(self.button_options)
            ]
        self.options_callbacks = {
            'parameter' : {'up': self.keys_callbacks['parameter_up'],
                           'down': self.keys_callbacks['parameter_down']},
            'button' : {'up': self.keys_callbacks['button_up'],
                        'down': self.keys_callbacks['button_down']}
            }
        self.current_option = 0
        self.activate_options()
        
        self.tmp_param_file = "../tmp/sequence_parameters.tmp"
        return None
    
    def activate_options(self):
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
    
    def select(self):
        self.class_logger.info("handle selection action",
                               extra={'className':f"{self.__class__.__name__}:"})
        action = self.button_options[self.current_button]['action']
        if action in self.page_callbacks.keys():
            self.class_logger.debug("action '{action}'",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.page_callbacks[action](action)
        elif action in self.keys_callbacks.keys():
            self.class_logger.debug("action '{action}'",
                                    extra={'className':f"{self.__class__.__name__}:"})
            self.keys_callbacks[action]()
        else:
            self.class_logger.debug("no action to trigger",
                                    extra={'className':f"{self.__class__.__name__}:"})
        return None
    
    def option_up(self):
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
    
    def option_down(self):
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
    
    def run_sequence(self):
        self.class_logger.info("write parameters for SequenceRunningPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        
        parameters = {"sequence_parameters":{param['name'].lower():{'value':param['value'], 'unit':param['unit']}
                                             for param in self.parameter_options},
                      "start_time":time.time()}
        # TODO: Get this parameter from settings_config.json
        parameters['sequence_parameters']['offset'] = {'value':300, 'unit':'ms'}
        
        with open(self.tmp_param_file, 'w') as f:
            json.dump(parameters, f)
        
        action = "sequence_running_page"
        self.page_callbacks[action](action)
        return None
    
    def navigate(self, direction):
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
    
    def display(self):
        self.class_logger.info("display SequenceParameterPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        self._draw_status_bar()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None


# TODO: Make a loop for sequence update, with periode based on running sequence parameters
# TODO: Add action to the 'pause' button to kill running sequence process and go back to parameters
class SequenceRunningPage(Button):
    class_logger = logging.getLogger('classLogger')
    def __init__(self, config, callbacks, general_config):
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
            'select' : self.button_select,
            'back' : callbacks["keys_callbacks"]['go_back'],
            'run' : lambda:print("Run function not implemented yet!"),
            'up' : self.button_up,
            'down' : self.button_down,
            **callbacks["keys_callbacks"],
            }
        
        # Set callbacks for navigation
        self.page_callbacks = {**callbacks["page_callbacks"]}
        
        self.action = lambda: None
        
        self.tmp_param_file = "../tmp/sequence_parameters.tmp"
            
        return None
    
    def launch_sequence(self):
        with open(self.tmp_param_file, 'r') as f:
            self.sequence_parameters = json.load(f)
        # TODO: Run the function in a fork, for non-blocking execution
        trigger.run_sequence(**self.sequence_parameters['sequence_parameters'])
        return None
    
    def navigate(self, direction):
        self.class_logger.info("navigate into sequence running page options",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None
    
    def display(self):
        self.class_logger.info("display SequenceRunningPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        if os.path.isfile(self.tmp_param_file):
            self.launch_sequence()
            super().display()
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
    def __init__(self, config, callbacks, general_config):
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
    
    def get_wifi_QRCode(self):
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
    
    def display(self):
        self.class_logger.info("display WifiPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.get_wifi_QRCode()
        super().display()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def navigate(self, direction):
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None


class SmartphonePage(Picture):
    class_logger = logging.getLogger('classLogger')
    def __init__(self, config, callbacks, general_config):
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
    
    def get_website_QRCode(self):
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
    
    def display(self):
        self.class_logger.info("display SmartphonePage",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.get_website_QRCode()
        super().display()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def navigate(self, direction):
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None


# TODO: Make a setting to switch RPi between access point to wifi mode
# TODO: Make a setting to enable user to connect a spacific website to add wifi
#       router ssid and passphrase for internet access on wifi mode
# TODO: Make a setting to check updates, only on wifi mode
class SettingPage(Menu):
    class_logger = logging.getLogger('classLogger')
    def __init__(self, config, callbacks, general_config):
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
    
    def display(self):
        self.class_logger.info("display MainMenuPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        self._draw_status_bar()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def navigate(self, direction):
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None


# TODO: Create class BatteryPage() to handle battery information display
class BatteryPage(Info):
    class_logger = logging.getLogger('classLogger')
    def __init__(self, config, callbacks, general_config):
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
        return None
    
    def display(self):
        self.class_logger.info("display BatteryPage",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().display()
        draw = ImageDraw.Draw(self.LCD.screen_img)
        
        icon = self.default_icon
        self.LCD.screen_img.paste(icon, (160-int(icon.width/2), 50))
        
        option_font = self.FONTS["PixelOperatorBold_M"]
        option_text = "BatteryPage()\ncoming soon"
        option_pos = (160, 130)
        draw.text(option_pos, option_text, font=option_font, fill=(255, 255, 255), anchor='mm')
        
        self._draw_status_bar()
        self.LCD.ShowImage(show=BYPASS_BUILTIN_SCREEN)
        return None
    
    def navigate(self, direction):
        self.class_logger.info(f"execute '{self.action.__name__}'",
                               extra={'className':f"{self.__class__.__name__}:"})
        super().navigate(direction)
        self.action()
        return None


class PageManager:
    class_logger = logging.getLogger('classLogger')
    def __init__(self, UI_config_path, general_config):
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
            "MainMenuPage"          : MainMenuPage,
            "ComingSoonPage"        : ComingSoonPage,
            "ShutdownPage"          : ShutdownPage,
            "SequenceParameterPage" : SequenceParameterPage,
            "SequenceRunningPage"   : SequenceRunningPage,
            "SettingPage"           : SettingPage,
            "WifiPage"              : WifiPage,
            "SmartphonePage"        : SmartphonePage,
            "BatteryPage"           : BatteryPage,
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
        
        self.load_pages()
        return None
    
    def load_pages(self):
        self.class_logger.info("generate pages based on config file",
                               extra={'className':f"{self.__class__.__name__}:"})
        for page_key, page_data in self.pages_structure.items():
            self.pages[page_key] = self.class_dict[page_data["class"]](page_data, self.callbacks, self._general_config)
        return None
    
    def show_page(self, page_key=None):
        self.class_logger.info(f"keep track of page history, showing page {page_key}",
                               extra={'className':f"{self.__class__.__name__}:"})
        if self.current_page:
            self.page_stack.append(self.current_page)
        
        self.current_page = self.pages[page_key]
        self.current_page.display()
        return None
    
    def go_back(self):
        self.class_logger.info("move to previous history page",
                               extra={'className':f"{self.__class__.__name__}:"})
        if self.page_stack:
            self.current_page = self.page_stack.pop()
            self.current_page.display()
        return None
    
    def shutdown(self):
        self.class_logger.info("shutdown PageManager",
                               extra={'className':f"{self.__class__.__name__}:"})
        self.QUIT = True
        return None