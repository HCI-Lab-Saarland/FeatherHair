#!/usr/bin/env python
# coding: utf-8

import time
import serial
from tkinter import *
from tkinter.ttk import *
import pickle
import pywt
from statistics import mean 
import numpy as np
import pandas as pd
import threading
import os
import sys

import time
import Adafruit_GPIO.SPI as SPI
import Adafruit_SSD1306
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
import subprocess

# I2C PiOLED config taken from 
# https://www.distrelec.de/Web/Downloads/_t/ds/Adafruit_Pioled-128x32_eng_tds.pdf

# Raspberry Pi pin configuration:
RST = None
# Note the following are only used with SPI:
DC = 23
SPI_PORT = 0
SPI_DEVICE = 0
# 128x32 display with hardware I2C:
disp = Adafruit_SSD1306.SSD1306_128_32(rst=RST)


#Initialize library.
disp.begin()
# Clear display.
disp.clear()
disp.display()
# Create blank image for drawing.
# Make sure to create image with mode '1' for 1-bit color.
width = disp.width
height = disp.height
image = Image.new('1', (width, height))
# Get drawing object to draw on image.
draw = ImageDraw.Draw(image)
# Draw a black filled box to clear the image.
draw.rectangle((0,0,width,height), outline=0, fill=0)

# Load default font.
#font = ImageFont.load_default()
font = ImageFont.truetype("/home/pi/Ubuntu-M.ttf", 20) 
connected = False
while not connected:
    try:
        ser =serial.Serial('/dev/ttyACM0', 115200)
        connected = True
    except:
        connected = False
        time.sleep(2)

# Feature Extraction
# Returns the column with values normalized to [0,1]
def normalize(column):
    return (column - np.min(column)) / (np.max(column) - np.min(column))

# Inspired by 
# https://github.com/taspinar/siml/blob/master/notebooks/WV4%20-%20Classification%20of%20ECG%20signals%20using%20the%20Discrete%20Wavelet%20Transform.ipynb
# Computing statistics for the coefficients of the DW-transformed data
# Returns the resulting list of features [Mean, MAD, Std, #zero_crossings, #mean_crossings]
def zero_crossings(coefficients):
    # Number of mean crossings          
    zero_crossing_indices_cap = np.nonzero(np.diff(np.array(coefficients) > 0))[0]
    return len(zero_crossing_indices_cap)   

# Returns the list of gestures given a dataframe
 
def data_to_features(window):
    features_list = []
    
    # Split data into resistance and capacitance
    resistances = []
    capacitances = []
    for sample in window:
        resistances.append(sample[0])
        capacitances.append(sample[1])
    resistance = normalize(resistances)
    capacitance = normalize(capacitances)
    
    # Create slightly smoothed resistance as feathers tend to be noisy
    resistance_rolling = (pd.Series(resistance).rolling(window=5)).mean()
    resistance_filtered = [resistance[pos] for pos in range(5)] + [resistance_rolling[pos + 5] for pos in range(len(resistance) - 5)]
    
    # Compute statistics in original domain, consider central half of data as it is most discriminating
    quarter = round(len(resistance) * 0.25)
    threequarter = round(len(resistance) * 0.75)
    centerhalf_cap = (pd.Series(capacitance[quarter:threequarter]))
    centerhalf_res = (pd.Series(resistance_filtered[quarter:threequarter]))
    
    ## Correlation between capacitive and resistive measurements
    features_list.append(pd.Series(resistance_filtered).corr(pd.Series(capacitance), method='pearson'))
    
    ## Additive mean and std of central half of data
    features_list.append(centerhalf_cap.mean() + centerhalf_res.mean())
    features_list.append(centerhalf_cap.std() +  centerhalf_res.std())
    
    ## Additive number of mean crossings of capacitive and filtered resistive data
    mean_crossing_indices_cap = np.nonzero(np.diff(np.array(capacitance) > np.nanmean(capacitance)))[0]
    mean_crossing_indices_res = np.nonzero(np.diff(np.array(resistance_filtered) > np.nanmean(resistance_filtered)))[0]
    features_list.append(len(mean_crossing_indices_cap) + len(mean_crossing_indices_res))
    
    # Compute statistics in DWT domain
    ## Pad all samples to length of 100 => each sample is recorded for max 10 seconds
    ## otherwise pad left and right end with boundary values
    cap_padded = pywt.pad(capacitance, 100, mode='constant')
    res_padded = pywt.pad(resistance_filtered, 100, mode='constant')
    
    ## Coefficients of capacitive and resistive signals
    ## Produces each 1 approximation coefficients array and 2 details coefficients arrays
    list_coeff = pywt.wavedec(cap_padded, 'db5', mode='constant', level = 2)
    list_coeff = pywt.wavedec(res_padded, 'db5', mode='constant', level = 2)
    
    ### Get statistics for DWT of capacitive data and resistive DWT data for all 3 coefficients arrays
    ### [Mean, MAD, Std, zero_cross, mean_cross]
    level1_stat_cap = zero_crossings(list_coeff[1])
    level2_stat_cap = zero_crossings(list_coeff[2])
    
    level1_stat_res = zero_crossings(list_coeff[1])
    level2_stat_res = zero_crossings(list_coeff[2])

    ### Additive number of mean crossings for detail coefficients arrays
    features_list.append(level1_stat_cap + level1_stat_res)
    features_list.append(level2_stat_cap + level2_stat_res)
  
    # 6 features in total
    return features_list

def get_data():
    reply = b''
    data = str(ser.readline())
    sample1=((((data.replace("(","")).replace(')',"")).replace("\\n","")).replace("b'","")).replace("'","")
    sample=((sample1.replace("\\r",""))).split(",")
    return [float(sample[0]),float(sample[1])]


def gesture_recognition():
    gestures = {0:'Doubletap', 1:'Hold', 2:'Noise', 3:'Slide', 4: 'Tap'}
    # Stop after 10 seconds
    max_window_size = 100
    # 1 second frame
    framing = 5
    # Initial current window is empty
    curr_window = []

    # Current average baseline for capacitive and resistive sensing
    old_baseline_cap = 0
    old_baseline_res = 0
    # Current average baseline for capacitive and resistive sensing
    curr_baseline_cap = 0
    curr_baseline_res = 0
    baseline_list_cap = []
    baseline_list_res = []

    # Current ratio of baseline/ratio for capacitive sensing
    curr_sample_baseline_ratio_cap = 0
    threshold_cap = 1.03
    # Current ratio of baseline/ratio for resistive sensing
    curr_sample_baseline_ratio_res = 0
    threshold_res = 1.2

    # Flag for gesture detection
    gestureStart = False
    gestureEnd = True

    counter = 0

    frame_res = []
    frame_cap = []
    iterations = 0
    ser.flushInput()
    ser.flush()
    ser.flushOutput()
    stopFeatherHair = False
        
    while not stopFeatherHair:
        iterations = iterations + 1
        global predicted
        data = str(ser.readline())
        line = get_data()
    
        capacitance = line[0]
        resistance = line[1]

        # Store 1 second of temporal framing
        frame_res.append(resistance)
        frame_cap.append(capacitance)
        if len(frame_res) > framing:
            del frame_res[0]
            del frame_cap[0]
    
        # Update baseline computation in case of no detected gesture. Computed across 1 seconds
        if not gestureStart:
            baseline_list_res.append(resistance)
            baseline_list_cap.append(capacitance)
            if len(baseline_list_cap) > 5:
                del baseline_list_cap[0]
                del baseline_list_res[0]
            old_baseline_cap = mean(baseline_list_cap)
            old_baseline_res = mean(baseline_list_res)
    
        if gestureStart:
            curr_window.append([resistance,capacitance])
        
        # Compute samplig rate as soon as we can refer to 2 seconds of data
        if len(baseline_list_cap) == 5:
            curr_sample_baseline_ratio_cap = capacitance / old_baseline_cap
            curr_sample_baseline_ratio_res = resistance / old_baseline_res
        
        if not gestureStart and ((curr_sample_baseline_ratio_cap >= threshold_cap) and (curr_sample_baseline_ratio_res >= 0.87*threshold_res)):
            gestureStart = True
            gestureEnd = False
            # add initial framing
            for i in range(framing):
                curr_window.append([frame_res[i],frame_cap[i]])
                counter  = 0
        elif gestureStart and (len(curr_window) > max_window_size or ((capacitance / old_baseline_cap < threshold_cap) and resistance / old_baseline_res < threshold_res)):
            counter = counter + 1
        if counter >= 10
            #if nothing happened for 1 second and
            gestureStart = False
            gestureEnd = True
            stopFeatherHair = True
            counter = 0
            # Transform features in curr_window
            features = data_to_features(curr_window) 
            #when the calculation is done, the result is stored in a global variable
            predicted = rf_trained.predict([features])[0]
            curr_window = []
        
    result_available.set()
    return


# Load model
rf_trained = pickle.load(open('rf_trained_pi.sav','rb'))

# Variables for threading
predicted = None
result_available = threading.Event()


while True:
# Draw a black filled box to clear the image.
    draw.rectangle((0,0,width,height), outline=0, fill=0)
    draw.text((width/6, height/4), "Detecting...", font=font, fill=255)
    # Display image.
    disp.image(image)
    disp.display()
    time.sleep(1)
    thread = threading.Thread(target=gesture_recognition)
    thread.start()
    result_available.wait()
    result_available.clear()
    draw.rectangle((0,0,width,height), outline=0, fill=0) 
    if predicted == "Hold":
   	 draw.text((width/3, height/4), str("Hold"), font=font, fill=255)
    
    if predicted == "Tap":
         draw.text((width/3, height/4), str("Tap"), font=font, fill=255)

    if predicted == "Doubletap":
         draw.text((width/5, height/4), str("Doubletap"), font=font, fill=255)

    if predicted == "Slide":
         draw.text((width/4, height/4), str("Slide"), font=font, fill=255)

    if predicted == "Noise":
         draw.text((width/4, height/4), str("Noise"), font=font, fill=255)

    # Display image.
    disp.image(image)
    disp.display()
    time.sleep(10)
