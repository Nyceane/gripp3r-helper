#!/usr/bin/env python3
# Copyright 2019 Amazon.com, Inc. or its affiliates.  All Rights Reserved.
# 
# You may not use this file except in compliance with the terms and conditions 
# set forth in the accompanying LICENSE.TXT file.
#
# THESE MATERIALS ARE PROVIDED ON AN "AS IS" BASIS. AMAZON SPECIFICALLY DISCLAIMS, WITH 
# RESPECT TO THESE MATERIALS, ALL WARRANTIES, EXPRESS, IMPLIED, OR STATUTORY, INCLUDING 
# THE IMPLIED WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.

import os
import sys
import time
import logging
import json
import math
import random
import threading
from enum import Enum

from agt import AlexaGadget

from ev3dev2.led import Leds
from ev3dev2.sound import Sound
from ev3dev2.motor import OUTPUT_A, OUTPUT_B, OUTPUT_C, MoveTank, SpeedPercent, MediumMotor
from ev3dev2.sensor.lego import InfraredSensor
from ev3dev2.sensor.lego import UltrasonicSensor
from ev3dev2.sensor.lego import TouchSensor
from ev3dev2.sensor.lego import GyroSensor
# Set the logging level to INFO to see messages from AlexaGadget
logging.basicConfig(level=logging.INFO, stream=sys.stdout, format='%(message)s')
logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))
logger = logging.getLogger(__name__)


class Direction(Enum):
    """
    The list of directional commands and their variations.
    These variations correspond to the skill slot values.
    """
    FORWARD = ['forward', 'forwards', 'go forward']
    BACKWARD = ['back', 'backward', 'backwards', 'go backward']
    LEFT = ['left', 'go left']
    RIGHT = ['right', 'go right']
    STOP = ['stop', 'brake', 'halt']


class Command(Enum):
    """
    The list of preset commands and their invocation variation.
    These variations correspond to the skill slot values.
    """
    MOVE_CIRCLE = ['circle', 'move around']
    MOVE_SQUARE = ['square']
    SENTRY = ['guard', 'guard mode', 'sentry', 'sentry mode']
    PATROL = ['patrol', 'patrol mode']
    FIRE_ONE = ['cannon', '1 shot', 'one shot']
    FIRE_ALL = ['all shots', 'all shot']


class EventName(Enum):
    """
    The list of custom event name sent from this gadget
    """
    SENTRY = "Sentry"
    PROXIMITY = "Proximity"
    SPEECH = "Speech"


class MindstormsGadget(AlexaGadget):
    """
    A Mindstorms gadget that can perform bi-directional interaction with an Alexa skill.
    """

    def __init__(self):
        """
        Performs Alexa Gadget initialization routines and ev3dev resource allocation.
        """
        super().__init__()

        # Connect two large motors on output ports B and C
        self.drive = MoveTank(OUTPUT_B, OUTPUT_C)
        self.grip = MediumMotor(OUTPUT_A)
        self.sound = Sound()
        self.leds = Leds()
        self.ir = InfraredSensor()
        self.touch = TouchSensor()
        self.gyro = GyroSensor()
        self.isComing = False
        self.isTaking = False
        self.isBringing = False
        self.isTurning = False
        # Start threads
        threading.Thread(target=self._proximity_thread, daemon=True).start()

    def on_connected(self, device_addr):
        """
        Gadget connected to the paired Echo device.
        :param device_addr: the address of the device we connected to
        """
        self.leds.set_color("LEFT", "GREEN")
        self.leds.set_color("RIGHT", "GREEN")
        logger.info("{} connected to Echo device".format(self.friendly_name))

    def on_disconnected(self, device_addr):
        """
        Gadget disconnected from the paired Echo device.
        :param device_addr: the address of the device we disconnected from
        """
        self.leds.set_color("LEFT", "BLACK")
        self.leds.set_color("RIGHT", "BLACK")
        logger.info("{} disconnected from Echo device".format(self.friendly_name))

    def on_custom_mindstorms_gadget_control(self, directive):
        """
        Handles the Custom.Mindstorms.Gadget control directive.
        :param directive: the custom directive with the matching namespace and name
        """
        try:
            payload = json.loads(directive.payload.decode("utf-8"))
            print("Control payload: {}".format(payload), file=sys.stderr)
            control_type = payload["type"]
            if control_type == "move":

                # Expected params: [direction, duration, speed]
                self._move(payload["direction"], int(payload["duration"]), int(payload["speed"]))

            elif control_type == "come":
                self._come()

            elif control_type == "take":
                self._take()

            elif control_type == "bring":
                self._bring()

        except KeyError:
            print("Missing expected parameters: {}".format(directive), file=sys.stderr)

    def _come(self, duration=10, speed=50):
        self.leds.set_color("LEFT", "GREEN", 1)
        self.leds.set_color("RIGHT", "GREEN", 1)
        self.isComing = True
        self._move(Direction.FORWARD.value[0], duration, speed)

    def _take(self, duration=20, speed=50):
        self.grip.on_for_rotations(SpeedPercent(100), 1)
        self.leds.set_color("LEFT", "GREEN", 1)
        self.leds.set_color("RIGHT", "GREEN", 1)
        self.gyro.reset()
        self.gyro.mode = 'GYRO-RATE'
        self.gyro.mode = 'GYRO-ANG'
        self.isTurning = True
        self.drive.on_for_seconds(SpeedPercent(100), SpeedPercent(-100), 1.3)
        self.drive.on_for_seconds(SpeedPercent(4), SpeedPercent(-4), 40)
        self.isTaking = True
        self.drive.on_for_seconds(SpeedPercent(50), SpeedPercent(50), duration)

    def _bring(self, duration=20):
        self.isTurning = True
        self.gyro.mode = 'GYRO-RATE'
        self.gyro.mode = 'GYRO-ANG'
        self.drive.on_for_seconds(SpeedPercent(100), SpeedPercent(-100), 1.3)
        self.drive.on_for_seconds(SpeedPercent(4), SpeedPercent(-4), 40)
        self.drive.on_for_seconds(SpeedPercent(50), SpeedPercent(50), 1.5)
        self.grip.on_for_rotations(SpeedPercent(100), 1)
        self.isTurning = True
        self.gyro.mode = 'GYRO-RATE'
        self.gyro.mode = 'GYRO-ANG'
        self.drive.on_for_seconds(SpeedPercent(100), SpeedPercent(-100), 1.3)
        self.drive.on_for_seconds(SpeedPercent(4), SpeedPercent(-4), 40)
        self.isBringing = True
        self.now = time.time()
        self.drive.on_for_seconds(SpeedPercent(50), SpeedPercent(50), duration)
        self.leds.set_color("LEFT", "GREEN", 1)
        self.leds.set_color("RIGHT", "GREEN", 1)


    def _move(self, direction, duration: int, speed: int, is_blocking=False):
        """
        Handles move commands from the directive.
        Right and left movement can under or over turn depending on the surface type.
        :param direction: the move direction
        :param duration: the duration in seconds
        :param speed: the speed percentage as an integer
        :param is_blocking: if set, motor run until duration expired before accepting another command
        """
        print("Move command: ({}, {}, {}, {})".format(direction, speed, duration, is_blocking), file=sys.stderr)
        if direction in Direction.FORWARD.value:
            self.drive.on_for_seconds(SpeedPercent(speed), SpeedPercent(speed), duration, block=is_blocking)

        if direction in Direction.BACKWARD.value:
            self.drive.on_for_seconds(SpeedPercent(-speed), SpeedPercent(-speed), duration, block=is_blocking)

        if direction in (Direction.RIGHT.value + Direction.LEFT.value):
            self._turn(direction, speed)
            self.drive.on_for_seconds(SpeedPercent(speed), SpeedPercent(speed), duration, block=is_blocking)

        if direction in Direction.STOP.value:
            self.drive.off()
            self.patrol_mode = False

    def _turn(self, direction, speed):
        """
        Turns based on the specified direction and speed.
        Calibrated for hard smooth surface.
        :param direction: the turn direction
        :param speed: the turn speed
        """
        if direction in Direction.LEFT.value:
            self.drive.on_for_seconds(SpeedPercent(0), SpeedPercent(speed), 2)

        if direction in Direction.RIGHT.value:
            self.drive.on_for_seconds(SpeedPercent(speed), SpeedPercent(0), 2)

    def _send_event(self, name: EventName, payload):
        """
        Sends a custom event to trigger a sentry action.
        :param name: the name of the custom event
        :param payload: the sentry JSON payload
        """
        self.send_custom_event('Custom.Mindstorms.Gadget', name.value, payload)

    def _proximity_thread(self):
        """ 
        Monitors the distance between the robot and an obstacle when sentry mode is activated.
        If the minimum distance is breached, send a custom event to trigger action on
        the Alexa skill.
        """
        while True:
            distance = self.ir.proximity
            angle = self.gyro.angle
            #print("Proximity: {}".format(distance), file=sys.stderr)
            if self.isTurning == True:
                print("angle: {}".format(angle), file=sys.stderr)
                self.leds.set_color("LEFT", "YELLOW", 1)
                self.leds.set_color("RIGHT", "YELLOW", 1)
                if abs(angle) >= 179 or abs(angle) <= -181:
                    self.isTurning = False
                    self._move(Direction.STOP.value[0], 0, 0,)
                    self.gyro.reset()
                    self.gyro.mode = 'GYRO-RATE'
                    self.gyro.mode = 'GYRO-ANG'
                    self.leds.set_color("LEFT", "GREEN", 1)
                    self.leds.set_color("RIGHT", "GREEN", 1)

            if distance <= 55:
                """
                When the bot is coming, it will stop and open up it's arm
                """

                if self.isComing == True:
                    self.isComing = False
                    print("Proximity breached, stopping")
                    self._move(Direction.STOP.value[0], 0, 0,)
                    self.leds.set_color("LEFT", "RED", 1)
                    self.leds.set_color("RIGHT", "RED", 1)
                    while not self.touch.is_pressed:
                        self.grip.on_for_degrees(SpeedPercent(10), -90)                        
                    print("Lowered the grip")
                elif self.isTaking ==True:
                    self.isTaking = False
                    print("Proximity breached, stopping")
                    self._move(Direction.STOP.value[0], 0, 0,)
                    self.leds.set_color("LEFT", "RED", 1)
                    self.leds.set_color("RIGHT", "RED", 1)
                    while not self.touch.is_pressed:
                        self.grip.on_for_degrees(SpeedPercent(10), -90)                        
                    print("Dropping Item")
                    self.drive.on_for_seconds(SpeedPercent(-50), SpeedPercent(-50), 1)
                    self.gyro.reset()
                    self.isTurning = True
                    self.gyro.mode = 'GYRO-RATE'
                    self.gyro.mode = 'GYRO-ANG'
                    self.drive.on_for_seconds(SpeedPercent(100), SpeedPercent(-100), 1.3)
                    self.drive.on_for_seconds(SpeedPercent(4), SpeedPercent(-4), 40, block=False)
                    self.leds.set_color("LEFT", "GREEN", 1)
                    self.leds.set_color("RIGHT", "GREEN", 1)
                elif self.isBringing ==True:
                    self.isBringing = False
                    print("Proximity breached, stopping")
                    self._move(Direction.STOP.value[0], 0, 0)
                    self.later = time.time()
                    self.leds.set_color("LEFT", "RED", 1)
                    self.leds.set_color("RIGHT", "RED", 1)
                    while not self.touch.is_pressed:
                        self.grip.on_for_degrees(SpeedPercent(10), -90)             
                    print("Dropping Item")
                    difference = int(self.later - self.now)
                    self.drive.on_for_seconds(SpeedPercent(-50), SpeedPercent(-50), difference - 0.5)
            time.sleep(0.2)


if __name__ == '__main__':

    gadget = MindstormsGadget()

    # Set LCD font and turn off blinking LEDs
    os.system('setfont Lat7-Terminus12x6')
    gadget.leds.set_color("LEFT", "BLACK")
    gadget.leds.set_color("RIGHT", "BLACK")

    # Startup sequence
    gadget.sound.play_song((('C4', 'e'), ('D4', 'e'), ('E5', 'q')))
    gadget.leds.set_color("LEFT", "GREEN")
    gadget.leds.set_color("RIGHT", "GREEN")

    # Gadget main entry point
    gadget.main()

    # Shutdown sequence
    gadget.sound.play_song((('E5', 'e'), ('C4', 'e')))
    gadget.leds.set_color("LEFT", "BLACK")
    gadget.leds.set_color("RIGHT", "BLACK")
