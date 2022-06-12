# Measuring Resistance and Capacitance of FeatherHair
# -----------------------------------------
# This demo uses a Metro M0 Express to read in values from 2 pieces
# of polymerized feather hair extensions and 1 piece of feathers able
# of capacitive sensing.
# Author: Marie Muehlhaus


import time
import board
from analogio import AnalogIn, AnalogOut
import touchio
import random

# ###########################################################
# ----------------------------------------------------------#
# -------------------FUNCTION DECLARATIONS------------------#
# ----------------------------------------------------------#
# ###########################################################

# Convert value to voltage [0, 3.3]
def get_voltage(value):
    # Divide by 3.3 (ItsyBitsy-specific)
    return (value * 3.3) / 65536

# Measures resistance across two pins in one way (A1 > A0)
# ItsyBitsy M0 Express has only A0 as AnalogOut
def analogread(samples):
    resistanceIn = 0
    resistance = 0
    analog_in = AnalogIn(board.A1)
    analog_out = AnalogOut(board.A0)
    analog_out.value = 65535
    for i in range(0, samples, 1):
        resistanceIn = analog_in.value
        resistance = resistance + resistanceIn
    analog_in.deinit()
    analog_out.deinit()
    return resistance / samples

# Measures capacitance on one pin.
# Makes use of touchio / on-board capacitive
def capacitiveread(samples):
    capacitanceIn = 0
    capacitance = 0
    touch = touchio.TouchIn(board.A2)  # Not a touch pin on Trinket M0!
    for i in range(0, samples, 1):
        capacitanceIn = touch.raw_value
        capacitance = capacitance + capacitanceIn
    touch.deinit()
    return capacitance / samples

# ###########################################################
# ----------------------------------------------------------#
# -----------------------START OF STUDY---------------------#
# ----------------------------------------------------------#
# ###########################################################

# Amount of samples that will be used to compute the average of the raw measurement
samples = 5

# --------------Meaure capacitance and resistance once every 0.1 sec--------------
while True:
    print("({},{})".format(capacitiveread(samples), analogread(samples)),end='\r')
    time.sleep(0.1)
