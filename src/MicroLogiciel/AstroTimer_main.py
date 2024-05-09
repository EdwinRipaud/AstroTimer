#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Mon Apr 29 10:38:16 2024

@author: edwinripaud
"""

import os
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
    from pynput.keyboard import Key, Listener
    USE_SCREEN = True

class Intervalometre():
    """
    Class Intervallometers
    Set hgih level function to control the intervalometer parameters,
    hardware definition and software commandes.
    """
    # Log vrebose level
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
    
    # Set directory
    PATH_FONTS  = "fonts/"
    PATH_ASSETS = "assets/"
    
    
    def __init__(self, id_name:str=None, display_dict:dict=None, sw5_dict:dict=None):
        
        if id_name:
            self.id_name = id_name
        else:
            self.id_name = __file__.split('/')[-1]
        
        logging.info(f"{self.id_name}:Intervalometre(class):__init__(): Initialisation of variables")
        	
        logging.debug(f"{self.id_name}:Intervalometre(class):__init__(): initialise fonts")
        # Set fonts
        self.Font_PixelOperator_small           = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperator.ttf", 24)
        self.Font_PixelOperatorBold_small       = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperator-Bold.ttf", 24)
        self.Font_PixelOperatorMono_small       = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperatorMono.ttf", 24)
        self.Font_PixelOperatorMonoBold_small   = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperatorMono-Bold.ttf", 24)
        	
        self.Font_PixelOperator             = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperator.ttf", 32)
        self.Font_PixelOperatorBold         = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperator-Bold.ttf", 32)
        self.Font_PixelOperatorMono         = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperatorMono.ttf", 32)
        self.Font_PixelOperatorMonoBold     = ImageFont.truetype(self.PATH_FONTS + "pixel_operator/PixelOperatorMono-Bold.ttf", 32)
        	
        logging.debug(f"{self.id_name}:Intervalometre(class):__init__(): initialise static assets")
        # Set assets
        self.Img_SplashScreen = Image.open(self.PATH_ASSETS + "SplashScreen.png")
        
        # Battery level variable
        self.BATTERY_DICT = {90.:f"{self.PATH_ASSETS}Icon_battery_90.png",
                             75.:f"{self.PATH_ASSETS}Icon_battery_75.png",
                             55.:f"{self.PATH_ASSETS}Icon_battery_55.png",
                             35.:f"{self.PATH_ASSETS}Icon_battery_35.png",
                             25.:f"{self.PATH_ASSETS}Icon_battery_25.png",
                             15.:f"{self.PATH_ASSETS}Icon_battery_15.png",
                             7.5:f"{self.PATH_ASSETS}Icon_battery_7.5.png",
                             }
        
        # Raspberry Pi pin configuration:
        logging.debug(f"{self.id_name}:Intervalometre(class):__init__(): initialise LCD display")
        # Display config
        if not display_dict:
            self.DISPLAY_DICT   = {'spi_bus'    : 0,
                                   'spi_device' : 0,
                                   'spi_freq'   : 40000000,
                                   'rst'        : 27,
                                   'dc'         : 25,
                                   'bl'         : 18,
                                   'bl_freq'    : 90,
                                   }
        else:
            self.DISPLAY_DICT = display_dict
        # Initialize LCD object form LCD_1inch47 library
        self.LCD = LCD_1inch47.LCD_1inch47(**self.DISPLAY_DICT)
        
        logging.debug(f"{self.id_name}:Intervalometre(class):__init__(): initialise 5-way switch")
        	# 5-way switch PIN
        if not sw5_dict:
            if RUN_ON_RPi:
                self.SW5_DICT   = {6    : "Click",
                                   19   : "Right",
                                   5    : "Left",
                                   26   : "Up",
                                   13   : "Down",
                                   }
            else:
                self.SW5_DICT   = {Key.enter : "Click",
                                   Key.right : "Right",
                                   Key.left  : "Left",
                                   Key.up    : "Up",
                                   Key.down  : "Down",
                                   }
        else:
            self.SW5_DICT = sw5_dict
        self.SW5_PIN = None
        if RUN_ON_RPi:
            for pin in list(self.SW5_DICT.keys()):
                GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
                GPIO.add_event_detect(pin, GPIO.FALLING, callback=self.callback_SW5)
        else:
            self.listener = Listener(on_press=self.callback_SW5)
            self.listener.start()
            
            
        logging.debug(f"{self.id_name}:Intervalometre(class):__init__(): initialise wifi parameters")
        # Wifi parameters configuration
        file_path = "/etc/hostapd/hostapd.conf"
        if os.path.exists(file_path):
            file_values = subprocess.check_output(f"sudo cat {file_path}", shell=True).decode('utf-8')
            self.WIFI_CONFIG = {line.split('=')[0]:line.split('=')[1] for line in file_values.split('\n')[:-1]}
            
            if 'ignore_broadcast_ssid' not in self.WIFI_CONFIG.keys():
                self.WIFI_CONFIG['ignore_broadcast_ssid'] = 'false'
            else:
                if self.WIFI_CONFIG['ignore_broadcast_ssid']:
                    self.WIFI_CONFIG['ignore_broadcast_ssid'] = 'true'
                else:
                    self.WIFI_CONFIG['ignore_broadcast_ssid'] = 'false'
        else:
            self.WIFI_CONFIG   = {'ssid'                      :'WifiHelloWorld',
                                  'wpa_passphrase'            :'HelloWorld!',
                                  'ignore_broadcast_ssid'     :'true',
                                  'wpa'                       :'WPA2',
                                  }
            
        logging.debug(f"{self.id_name}:Intervalometre(class):__init__(): initialise website parameters")
        # Website parameters configuration
        file_path = "/etc/dhcpcd-static.conf"
        if os.path.exists(file_path):
            file_values = subprocess.check_output(f"sudo cat {file_path}", shell=True).decode('utf-8')
            id_paragraphe = file_values.find('#static IP')
            paragraphe = file_values[id_paragraphe:]
            self.WEBSITE_CONFIG = {'ip'     :paragraphe[paragraphe.find('=')+1:paragraphe.find('=')+11],
                                   'port'   :'55000'}
        else:
            self.WEBSITE_CONFIG = {'ip'     :'255.255.255.255',
                                   'port'   :'65535',
                                   }
        
        
        logging.debug(f"{self.id_name}:Intervalometre(class):__init__(): initialise interface level and handlers functions")
        # Full interface definition
        # Iterface depth level switcher
        self.INTERFACE_DEPTH_DICT = {-1: self._handler_shutdown,
                                      0: self._handler_main_menu,
                                      1: self._handle_interface_level_1,
                                      2: self._handle_interface_level_2,
                                      }
        self.MAX_INTERFACE_DEPTH = max(self.INTERFACE_DEPTH_DICT.keys())
        self.MIN_INTERFACE_DEPTH = min(self.INTERFACE_DEPTH_DICT.keys())
        
        
        logging.debug(f"{self.id_name}:Intervalometre(class):__init__(): initialise level 0 variables and handler function")
        # Main menu variable
        self.MAIN_MENU_LIST = [{'name':"Sequence",
                                'func':self._handle_menu_sequence,
                                'icon':f"{self.PATH_ASSETS}Icon_Sequence.png",
                                },
                               {'name':"Battery",
                                'func':self._handle_menu_battery,
                                'icon':f"{self.PATH_ASSETS}Icon_Battery.png",
                                },
                               {'name':"Parameters",
                                'func':self._handle_menu_parameters,
                                'icon':f"{self.PATH_ASSETS}Icon_Parameters.png",
                                },
                               {'name':"Shutdown",
                                'func':self._handle_menu_shutdown,
                                'icon':f"{self.PATH_ASSETS}Icon_Shutdown.png",
                                },
                               {'name':"Wifi config",
                                'func':self._handle_menu_wifi_config,
                                'icon':f"{self.PATH_ASSETS}Icon_Wifi_config.png",
                                },
                               {'name':"Smartphone",
                                'func':self._handle_menu_smartphone,
                                'icon':f"{self.PATH_ASSETS}Icon_Smartphone.png",
                                },
                               ]
        self.NB_MAIN_MENU = len(self.MAIN_MENU_LIST)
        self.SCROLLBAR_STEP_MAIN_MENU = int(138/self.NB_MAIN_MENU)
        
        logging.debug(f"{self.id_name}:Intervalometre(class):__init__(): initialise level 1 variables and handler function")
        # Interface level 1 variable
        self.LEVEL_1_DICT = {"Sequence"     : {'func':lambda:print("No callback function yet"),},
                             "Parameters"   : {'func':lambda:print("No callback function yet"),},
                             }
        
        # Sequence parameters variable
        self.SEQUENCE_PARAMETERS_LIST = [{'name':"exposure",
                                          'text':"Exposure",
                                          'value':1,
                                          'step_func':self._sequence_parameters_step,
                                          'step_param':{'min_step':1, 'max_step':5, 'threshold':10},
                                          'position':(8, 45),
                                          },
                                         {'name':"shots",
                                          'text':"Shots",
                                          'value':3,
                                          'step_func':self._sequence_parameters_step,
                                          'step_param':{'min_step':1, 'max_step':5, 'threshold':10},
                                          'position':(8, 70),
                                          },
                                         {'name':"delay", 
                                          'text':"Delay",
                                          'value':0.5,
                                          'step_func':self._sequence_parameters_step,
                                          'step_param':{'min_step':0.25, 'max_step':0.5, 'threshold':4},
                                          'position':(8, 95),
                                          },
                                         {'name':"run",
                                          'text':"Run ->",
                                          'value':'',
                                          'step':None,
                                          'position':(215, 135),
                                          },
                                         ]
        # Parameters base parameters variable
        self.PARAMETER_PARAMETERS_DICT = {'offset_time': 300,
                                          }
        
        logging.debug(f"{self.id_name}:Intervalometre(class):__init__(): initialise global variables")
        # Global variables
        
        self.INTERFACE_DEPTH_LEVEL  = 0                 # [int] Depth position in the interface (-1 --> shutdown confirmation page)
        self.SELECTED_MAIN_MENU     = 0                 # [int] Selected menu position in `MAIN_MENU_LIST`
        self.SELECTED_SEQ_PARAM     = 0                 # [int] Selected parameter in `SEQUENCE_PARAMETERS_LIST`
        self.MODIFY_PARAM           = False             # [bool] True when parameter modification is active
        self.QUIT                   = 0                 # [bool] True to quite the loop
        
        self.SEQUENCE_RUNNING       = False             # [bool] Is a sequence running ?
        
        self.BATTERY_LEVEL          = 31                # [float] Battery percentage value
        
        self.STATUS_TXT             = "Ready to GO !"   # [str] Message on the status info bar
        
        return None
    
    
    def _sequence_parameters_step(self, val, min_step=1, max_step=5, threshold=10):
        if val >= threshold:
            return max_step
        else:
            return min_step
    
    def _increment_interface(self):
        self.INTERFACE_DEPTH_LEVEL = (self.INTERFACE_DEPTH_LEVEL+1)
        if self.INTERFACE_DEPTH_LEVEL > self.MAX_INTERFACE_DEPTH:
            self.INTERFACE_DEPTH_LEVEL = self.MAX_INTERFACE_DEPTH
        return None
    
    def _decrement_interface(self):
        self.INTERFACE_DEPTH_LEVEL = (self.INTERFACE_DEPTH_LEVEL-1)
        if self.INTERFACE_DEPTH_LEVEL < self.MIN_INTERFACE_DEPTH:
            self.INTERFACE_DEPTH_LEVEL = self.MIN_INTERFACE_DEPTH
        return None
    
    def _get_battery_icon(self):
        auth_level = np.array(list(self.BATTERY_DICT.keys()))
        auth_level[::-1].sort()
        
        if self.BATTERY_LEVEL>auth_level[-1]:
            arg = np.argmax(auth_level<self.BATTERY_LEVEL)
        else:
            arg = -1
        return self.BATTERY_DICT[auth_level[arg]]
    
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
    
    def _draw_menu(self, img_in=None):
        if not img_in:
            logging.debug(f"{self.id_name}:Intervalometre(class):_draw_menu(): Create new black background image")
            img_out = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0, 0, 0, 255))
        else:
            img_out = img_in
        draw = ImageDraw.Draw(img_out)
        
        px_icon_left = 4
        px_icon_top  = 20
        px_text_left = px_icon_left+60
        px_text_top  = px_icon_top+7
        px_step = 60
        
        logging.debug(f"{self.id_name}:Intervalometre(class):_draw_menu(): Add menu icon")
        for k in range(3):
            sel = (self.SELECTED_MAIN_MENU + k-1) % self.NB_MAIN_MENU
            asset_menu = Image.open(self.MAIN_MENU_LIST[sel]['icon'])
            img_out.paste(asset_menu, (px_icon_left, px_icon_top+k*px_step))
            draw.text((px_text_left, px_text_top+k*px_step), f"{self.MAIN_MENU_LIST[sel]['name']}", fill=(255,255,255), font=self.Font_PixelOperator)
        
        logging.debug(f"{self.id_name}:Intervalometre(class):_draw_menu(): Add menu selection")
        asset_selection = Image.open(f"{self.PATH_ASSETS}Selection.png")
        img_out.paste(asset_selection, (1, px_icon_top+px_step-4), asset_selection.convert("RGBA"))
        
        logging.debug(f"{self.id_name}:Intervalometre(class):_draw_menu(): Add scrollbar")
        asset_scrollbar_background = Image.open(f"{self.PATH_ASSETS}Scrollbar_background.png")
        img_out.paste(asset_scrollbar_background, (311, 33))
        asset_scrollbar = Image.open(f"{self.PATH_ASSETS}Scrollbar.png")
        img_out.paste(asset_scrollbar, (309, 34+self.SCROLLBAR_STEP_MAIN_MENU*self.SELECTED_MAIN_MENU))
        
        img_out = self.__draw_status_bar(img_out)
        return img_out
    
    def _draw_QRCode(self, txt, img_in=None, pos='center'):
        if not img_in:
            logging.debug(f"{self.id_name}:Intervalometre(class):_draw_QRCode(): Create new black background image")
            img_out = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0, 0, 0, 255))
        else:
            img_out = img_in
        logging.debug(f"{self.id_name}:Intervalometre(class):_draw_QRCode(): Generate QR code")
        if len(txt)>50:
            box_size = 4
        else:
            box_size = 5
        qr = qrcode.QRCode(box_size=box_size, border=2)
        qr.add_data(txt)
        img_qr = qr.make_image()
        if pos == 'center':
            pos = (int((img_out.width-img_qr.height)/2), int((img_out.height-img_qr.height)/2))
        else:
            pos = pos
        img_out.paste(img_qr, pos)
        return img_out
    
    def _draw_quit(self):
        logging.info(f"{self.id_name}:Intervalometre(class):_draw_quit(): Draw `QUIT` paged")
        img_out = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0, 0, 0, 255))
        draw = ImageDraw.Draw(img_out)
        asset = Image.open(f"{self.PATH_ASSETS}Icon_Shutdown.png")
        img_out.paste(asset, (136, 2))
        draw.text((160, 75), "Shutdown now ?", fill=(255,255,255), font=self.Font_PixelOperatorBold, anchor='mm')
        draw.text((64, 125), "Yes", fill=(255,255,255), font=self.Font_PixelOperatorBold, anchor='mm')
        draw.text((256, 125), "No", fill=(255,255,255), font=self.Font_PixelOperatorBold, anchor='mm')
        return img_out
    
    def _draw_sequence_base(self):
        self.STATUS_TXT = "Sequence param."
        
        logging.info(f"{self.id_name}:Intervalometre(class):_draw_sequence_base(): Draw sequence base")
        img_out = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0, 0, 0, 255))
        draw = ImageDraw.Draw(img_out)
        
        for i in range(len(self.SEQUENCE_PARAMETERS_LIST)):
            seq_param = self.SEQUENCE_PARAMETERS_LIST[i]
            text = f"{seq_param['text']: <9}:" if i < len(self.SEQUENCE_PARAMETERS_LIST)-1 else f"{seq_param['text']}"
            value = f"{seq_param['value']}"
            x0, y0 = seq_param['position']
            bbox_text = draw.textbbox((x0, y0), text, font=self.Font_PixelOperatorMonoBold_small)
            if i == self.SELECTED_SEQ_PARAM:
                # draw.rounded_rectangle(bbox_text, radius=3, fill=(100, 100, 100))
                draw.text((x0, y0), text, fill=(255,255,255), font=self.Font_PixelOperatorMonoBold_small)
                draw.text((bbox_text[2]+35, y0), value, fill=(255,255,255), font=self.Font_PixelOperatorMonoBold_small, anchor='ma')
                
                if self.MODIFY_PARAM and i < len(self.SEQUENCE_PARAMETERS_LIST)-1:
                    draw.rounded_rectangle([bbox_text[2]+5, bbox_text[1]-5, bbox_text[2]+65, bbox_text[3]+5], radius=5)
                else:
                    draw.line([bbox_text[0], bbox_text[3], bbox_text[2], bbox_text[3]], width=1)
            else:
                draw.text((x0, y0), text, fill=(255,255,255), font=self.Font_PixelOperatorMono_small)
                draw.text((bbox_text[2]+35, y0), value, fill=(255,255,255), font=self.Font_PixelOperatorMonoBold_small, anchor='ma')
        
        img_out = self.__draw_status_bar(img_out)
        return img_out
    
    def _draw_parameters_base(self):
        logging.info(f"{self.id_name}:Intervalometre(class):_draw_parameters_base(): Draw parameters base")
        self.comming_soon()
        return self.LCD.screen_img
    
    def _handler_shutdown(self):
        if self.SW5_DICT[self.SW5_PIN] == "Click":
            logging.debug(f"{self.id_name}:Intervalometre(class):_handler_shutdown(): QUIT")
            self.QUIT = 1
        
        self.LCD.screen_img = self._draw_quit()
        self.LCD.ShowImage(show=USE_SCREEN)
        return None
    
    def _handler_main_menu(self):
        if self.SW5_DICT[self.SW5_PIN] == "Click":
            if self.MAIN_MENU_LIST[self.SELECTED_MAIN_MENU]['name'] in self.LEVEL_1_DICT.keys():
                logging.info(f"{self.id_name}:Intervalometre(class):_handler_main_menu(): {self.SW5_DICT[self.SW5_PIN]} to enter selected menu")
                func = self.MAIN_MENU_LIST[self.SELECTED_MAIN_MENU]['func']
                func()
                return None
            else:
                logging.info(f"{self.id_name}:Intervalometre(class):_handler_main_menu(): No sub-menu for {self.MAIN_MENU_LIST[self.SELECTED_MAIN_MENU]['name']}")
        
        elif self.SW5_DICT[self.SW5_PIN] == "Up":
            logging.debug(f"{self.id_name}:Intervalometre(class):_handler_main_menu(): Move menue {self.SW5_DICT[self.SW5_PIN]}")
            self.SELECTED_MAIN_MENU  = (self.SELECTED_MAIN_MENU - 1) % self.NB_MAIN_MENU
        elif self.SW5_DICT[self.SW5_PIN] == "Down":
            logging.debug(f"{self.id_name}:Intervalometre(class):_handler_main_menu(): Move menue {self.SW5_DICT[self.SW5_PIN]}")
            self.SELECTED_MAIN_MENU  = (self.SELECTED_MAIN_MENU + 1) % self.NB_MAIN_MENU
        
        self.LCD.screen_img = self._draw_menu()
        self.LCD.ShowImage(show=USE_SCREEN)
        return None
    
    def _handle_interface_level_1(self):
        if self.SW5_DICT[self.SW5_PIN] == "Left":
            logging.info(f"{self.id_name}:Intervalometre(class):_handle_interface_level_1(): Back to main menu")
            func = self.MAIN_MENU_LIST[self.SELECTED_MAIN_MENU]['func']
            func()
            return None
        
        elif self.SW5_DICT[self.SW5_PIN] == "Up":
            if self.MODIFY_PARAM:
                func = self.SEQUENCE_PARAMETERS_LIST[self.SELECTED_SEQ_PARAM]['step_func']
                param = self.SEQUENCE_PARAMETERS_LIST[self.SELECTED_SEQ_PARAM]['step_param']
                val = self.SEQUENCE_PARAMETERS_LIST[self.SELECTED_SEQ_PARAM]['value']
                self.SEQUENCE_PARAMETERS_LIST[self.SELECTED_SEQ_PARAM]['value'] += func(val, **param)
            else:
                self.SELECTED_SEQ_PARAM = (self.SELECTED_SEQ_PARAM - 1)%len(self.SEQUENCE_PARAMETERS_LIST)
        
        elif self.SW5_DICT[self.SW5_PIN] == "Down":
            if self.MODIFY_PARAM:
                func = self.SEQUENCE_PARAMETERS_LIST[self.SELECTED_SEQ_PARAM]['step_func']
                param = self.SEQUENCE_PARAMETERS_LIST[self.SELECTED_SEQ_PARAM]['step_param']
                val = self.SEQUENCE_PARAMETERS_LIST[self.SELECTED_SEQ_PARAM]['value']
                val_new = val - func(val, **param)
                self.SEQUENCE_PARAMETERS_LIST[self.SELECTED_SEQ_PARAM]['value'] = max(0, val_new)
            else:
                self.SELECTED_SEQ_PARAM = (self.SELECTED_SEQ_PARAM + 1)%len(self.SEQUENCE_PARAMETERS_LIST)
        
        if self.INTERFACE_DEPTH_LEVEL == 1:
            logging.info(f"{self.id_name}:Intervalometre(class):_handle_interface_level_1()")
            func = self.MAIN_MENU_LIST[self.SELECTED_MAIN_MENU]['func']
            func()
        else:
            logging.info(f"{self.id_name}:Intervalometre(class):_handle_interface_level_1(): This messgae shouldn't appear ...")
            return None
    
    def _handle_interface_level_2(self):
        logging.info(f"{self.id_name}:Intervalometre(class):_handle_interface_level_2(): Comming soon ;)")
        self.comming_soon(disp=True)
        return None
    
    def _handle_menu_sequence(self):
        logging.info(f"{self.id_name}:Intervalometre(class):_handle_menu_sequence()")
        self.LCD.screen_img = self._draw_sequence_base()
        self.LCD.ShowImage(show=USE_SCREEN)
        return None
    
    def _handle_menu_battery(self):
        logging.info(f"{self.id_name}:Intervalometre(class):_handle_menu_battery()")
        self.comming_soon(disp=True)
        return None
    
    def _handle_menu_parameters(self):
        logging.info(f"{self.id_name}:Intervalometre(class):_handle_menu_parameters()")
        self.LCD.screen_img = self._draw_parameters_base()
        self.LCD.ShowImage(show=USE_SCREEN)
        return None
    
    def _handle_menu_shutdown(self):
        logging.info(f"{self.id_name}:Intervalometre(class):_handle_menu_shutdown()")
        self.INTERFACE_DEPTH_LEVEL = -1
        self.LCD.screen_img = self._draw_quit()
        self.LCD.ShowImage(show=USE_SCREEN)
        return None
    
    def _handle_menu_wifi_config(self):
        logging.info(f"{self.id_name}:Intervalometre(class):_handle_menu_wifi_config()")
        autent = self.WIFI_CONFIG['wpa']
        ssid = self.WIFI_CONFIG['ssid']
        password = self.WIFI_CONFIG['wpa_passphrase']
        hide = self.WIFI_CONFIG['ignore_broadcast_ssid']
        self.LCD.screen_img = self._draw_QRCode(f"WIFI:T:{autent};S:{ssid};P:{password};H:{hide};;")
        self.LCD.ShowImage(show=USE_SCREEN)
        return None
    
    def _handle_menu_smartphone(self):
        logging.info(f"{self.id_name}:Intervalometre(class):_handle_menu_smartphone()")
        self.LCD.screen_img = self._draw_QRCode(f"HTTP:{self.WEBSITE_CONFIG['ip']}:{self.WEBSITE_CONFIG['port']}")
        self.LCD.ShowImage(show=USE_SCREEN)
        return None
    
    def callback_SW5(self, pin):
        self.SW5_PIN = pin
        menu = self.MAIN_MENU_LIST[self.SELECTED_MAIN_MENU]
        
        if self.SW5_PIN not in list(self.SW5_DICT.keys()):
            logging.warning(f"{self.id_name}:Intervalometre(class):callback_SW5(): Unknown pin {self.SW5_PIN} fro 5-way switch")
            return None
        
        if self.SW5_DICT[self.SW5_PIN] == "Click":
            if self.INTERFACE_DEPTH_LEVEL < 0:
                logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): QUIT")
                self.QUIT = 1
                return None
            elif self.INTERFACE_DEPTH_LEVEL == 0:
                self._increment_interface()
                logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): Enter menu {menu['name']}")
            elif self.INTERFACE_DEPTH_LEVEL == 1:
                self._increment_interface()
                if menu['name'] in self.LEVEL_1_DICT.keys():
                    if self.SELECTED_SEQ_PARAM == len(self.SEQUENCE_PARAMETERS_LIST)-1:
                        logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): Enter sub-menu of {menu['name']}")
                    elif not self.MODIFY_PARAM:
                        logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): Modification of {menu['name']} parameters")
                        self.MODIFY_PARAM = True
                        self._decrement_interface()
                    elif self.MODIFY_PARAM:
                        logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): Stop modification of {menu['name']} parameters")
                        self.MODIFY_PARAM = False
                        self._decrement_interface()
                    else:
                        logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): This message shoudln't appear...")
                else:
                    logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): No sub-menu for {menu['name']}")
                    self._decrement_interface()
                    self._decrement_interface()
            else:
                return None
        
        elif self.SW5_DICT[self.SW5_PIN] == "Right":
            if self.INTERFACE_DEPTH_LEVEL < 0:
                self._increment_interface()
                logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): Moving back to main menu")
            elif self.INTERFACE_DEPTH_LEVEL == 0:
                self._increment_interface()
                logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): Enter menu {menu['name']}")
            elif self.INTERFACE_DEPTH_LEVEL == 1:
                self._increment_interface()
                if menu['name'] in self.LEVEL_1_DICT.keys():
                    if self.SELECTED_SEQ_PARAM == len(self.SEQUENCE_PARAMETERS_LIST)-1:
                        logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): Enter sub-menu of {menu['name']}")
                    elif not self.MODIFY_PARAM:
                        logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): Modification of {menu['name']} parameters")
                        self.MODIFY_PARAM = True
                        self._decrement_interface()
                    else:
                        logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): Enter sub-menu of {menu['name']}")
                else:
                    logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): No sub-menu for {menu['name']}")
                    self._decrement_interface()
                    return None
            else:
                return None
        
        elif self.SW5_DICT[self.SW5_PIN] == "Left":
            if self.INTERFACE_DEPTH_LEVEL == 1:
                self._decrement_interface()
                if menu['name'] in self.LEVEL_1_DICT.keys() and self.MODIFY_PARAM:
                    logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): Stop modification of {menu['name']} parameters")
                    self._increment_interface()
                    self.MODIFY_PARAM = False
                else:
                    logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): Moving back to main menu")
            elif self.INTERFACE_DEPTH_LEVEL > 1:
                self._decrement_interface()
                logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): Comme back to menu {menu['name']}")
            elif self.INTERFACE_DEPTH_LEVEL == 0:
                self._decrement_interface()
                logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): Enter Shutdown menu")
            else:
                return None
        
        elif self.SW5_DICT[self.SW5_PIN] == "Up":
            if self.INTERFACE_DEPTH_LEVEL == 0:
                pass
            elif self.INTERFACE_DEPTH_LEVEL == 1:
                pass
            else:
                return None
        
        elif self.SW5_DICT[self.SW5_PIN] == "Down":
            if self.INTERFACE_DEPTH_LEVEL == 0:
                pass
            elif self.INTERFACE_DEPTH_LEVEL == 1:
                if menu['name'] in self.LEVEL_1_DICT.keys():
                    print("Yess modification parameters")
                else:
                    pass
            else:
                return None
        
        else:
            logging.info(f"{self.id_name}:Intervalometre(class):callback_SW5(): This message shouldn't appear...")
        
        
        func = self.INTERFACE_DEPTH_DICT[self.INTERFACE_DEPTH_LEVEL]
        func()
        return None
    
    def comming_soon(self, disp=False):
        logging.info(f"{self.id_name}:Intervalometre(class):comming_soon(): {self.MAIN_MENU_LIST[self.SELECTED_MAIN_MENU]['name']}")
        img_out = Image.new(mode="RGBA", size=self.LCD.size[::-1], color=(0, 0, 0, 255))
        draw = ImageDraw.Draw(img_out)
        if self.INTERFACE_DEPTH_LEVEL <= 1:
            draw.text((160, 50), f"{self.MAIN_MENU_LIST[self.SELECTED_MAIN_MENU]['name']}", fill=(255,255,255), font=self.Font_PixelOperatorBold, anchor='mm')
            draw.text((160, 110), "Cooming soon ;)", fill=(255,255,255), font=self.Font_PixelOperator, anchor='mm')
        elif self.INTERFACE_DEPTH_LEVEL == 2:
            draw.text((160, 50), "No level 2 yet", fill=(255,255,255), font=self.Font_PixelOperatorBold, anchor='mm')
            draw.text((160, 110), "Cooming soon ;)", fill=(255,255,255), font=self.Font_PixelOperator, anchor='mm')
        else:
            logging.info(f"{self.id_name}:Intervalometre(class):comming_soon(): This message shouldn't appear...")
        
        self.LCD.screen_img = img_out
        if disp :
            self.LCD.ShowImage(show=USE_SCREEN)
            return None
        else:
            return img_out
    
    def Run(self):
        logging.info(f"{self.id_name}:Intervalometre(class):run(): Running the Intervalometer(class)")
        
        self.LCD.screen_img = self._draw_menu()
        self.LCD.ShowImage(show=USE_SCREEN)
        
        while not self.QUIT:
            continue
        
        return None
    
    def Clean_stop(self):
        logging.info(f"{self.id_name}:Intervalometre(class):Clean_stop(): Cleanning Intervalometre(class)")
        if RUN_ON_RPi:
            for pin in list(self.SW5_DICT.keys()):
                GPIO.remove_event_detect(pin)
            
            self.LCD.set_bl_DutyCycle(0)
            self.LCD.ClearScreen()
            
            GPIO.cleanup()
        
        else:
            self.LCD.ClearScreen()
            
            self.listener.stop()
        return None


if __name__ == '__main__':
    SCRIPT_NAME = __file__.split('/')[-1]
    print(__file__)
    try:
        
        Intervallometer_V5 = Intervalometre()
        
        Intervallometer_V5.Run()
        
        logging.info(f"{SCRIPT_NAME}: Add shutdown script call")
        Intervallometer_V5.Clean_stop()
    
    except IOError as e:
        logging.info(f"{SCRIPT_NAME}: IOError - {e}")
        Intervallometer_V5.Clean_stop()
    except KeyboardInterrupt:
        logging.info(f"{SCRIPT_NAME}: KeyboardInterrupt")
        Intervallometer_V5.Clean_stop()

