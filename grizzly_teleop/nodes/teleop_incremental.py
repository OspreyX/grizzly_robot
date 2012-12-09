#!/usr/bin/python

""" If we're using the usual Logitech gamepad, suggest using "X" mode
via the switch on the front. That will map the buttons to "Green=GO, 
Red=E-Stop.

This is a modified version of teleop which allows a change into 
"incremental mode" where steering and throttle inputs are incremental 
changes. Not sure if an enable button needs to be held here
or if e-stop is enough"""

import roslib; roslib.load_manifest('grizzly_teleop')
import rospy

from sensor_msgs.msg import Joy
from geometry_msgs.msg import Twist
from std_msgs.msg import Bool
from math import copysign

class IncrementalTeleop:
    
    def __init__(self):
        rospy.init_node('grizzly_incr_teleop')

        # Button assignments
        self.turn_scale = rospy.get_param('~turn_scale')
        self.drive_scale = rospy.get_param('~drive_scale')
        self.deadman_button = rospy.get_param('~deadman_button', 0)
        self.estop_button = rospy.get_param('~estop_button', 1)
        # TODO: Confirm button assignments
        self.mode_button = rospy.get_param('~mode_button', 2)
        self.zero_button = rospy.get_param('~zero_button', 3)
     
        self.incr_mode = False # If true, we're in incremental mode
        self.incr_debounce = False # For debouncing button press

        self.cmd = None
        self.cmd_inc = None
        cmd_pub = rospy.Publisher('cmd_vel', Twist)
        self.estop = False
        cmd_estop = rospy.Publisher('/mcu/estop', Bool)

        rospy.Subscriber("joy", Joy, self.callback)
        rate = rospy.Rate(rospy.get_param('~hz', 20))
        period = rospy.get_param('~hz',20)
        
        while not rospy.is_shutdown():
            rate.sleep()
            if self.incr_mode:
                # Increment command
                self.cmd.linear.x += self.cmd_inc.linear.x / period 
                self.cmd.angular.z += self.cmd_inc.angular.z / period 
                # Saturate to range
                self.cmd.linear.x = self.saturate(self.cmd.linear.x,self.drive_scale) 
                self.cmd.angular.z = self.saturate(self.cmd.angular.z,self.turn_scale) 
            """ This won't exist if we set it to None in the callback
            Otherwise, self.cmd is either modified by the above code (in
            incremental mode) or directly by the callback (in absolute mode) 
            """
            if self.cmd:
                cmd_pub.publish(self.cmd)
            """ As long as we're active, give it e-stop data
            A manual reset is required once an e-stop is asserted
            anyway, and having to reset everytime we let go of the
            joystick isn't the point """
            cmd_estop.publish(self.estop)

    def saturate(self,inp,rng):
        """ Keeps inp within a range defined by [-rng,rng] """
        return copysign(min(abs(inp),rng),inp)

    def callback(self, data):
        """ Receive joystick data, formulate Twist message. """
        cmd = Twist()
        cmd.linear.x = data.axes[1] * self.drive_scale
        cmd.angular.z = data.axes[0] * self.turn_scale

        # We are not debouncing, change mode
        if data.buttons[self.mode_button] == 1 and not self.incr_debounce:
            self.incr_mode = not self.incr_mode            
            rospy.loginfo("Incremental mode: %s",self.incr_mode)
            self.incr_debounce = True
            # If we are now in incremental mode, zero output command
            if self.incr_mode:
                self.cmd = Twist()
        # Finish debounce
        if data.buttons[self.mode_button] == 0:
            self.incr_debounce = False

        # Use the mode, Luke
        if self.incr_mode:
            if data.buttons[self.deadman_button] == 1:
                self.cmd_inc = cmd
            else:
                # TODO: Do we want to use the deadman button?
                # If so, swap below commenting
                self.cmd_inc = cmd
                #self.cmd_inc = None
                #self.cmd = None
        else:
            if data.buttons[self.deadman_button] == 1:
                self.cmd = cmd
            else:
                self.cmd = None

        # Zero output velocity, if required
        # Only supported in incremental mode
        if self.incr_mode and data.buttons[self.zero_button] == 1:
            self.cmd = Twist()
            self.cmd_inc = Twist()

        if data.buttons[self.estop_button] == 1:
            self.estop = True
        else:
            self.estop = False

if __name__ == "__main__": 
    IncrementalTeleop() 
