#!/usr/bin/env python2

import rospy, os, subprocess
from nav_msgs.msg import Odometry, Path
from geometry_msgs.msg import PoseStamped
from geometry_msgs.msg import Twist, Point, Quaternion
from tf.transformations import euler_from_quaternion,quaternion_from_euler
from numpy import sqrt, pi, square
from math import atan2
from nav_msgs.srv import GetPlan
from rbe3002_lab3.srv import frontierList, frontierListResponse, frontierListRequest



class Lab4:

    def __init__(self):
        """
        Class constructor
        """
        self.px = 0     #X location of the robot
        self.py = 0     #Y location of the robot
        self.pth = 0    #Orientation (yaw) of the robot
        self.omega = 0  #Angular Velocity of the robot

        #Initialize node, name it 'lab4'
        rospy.init_node('lab4',anonymous= True) 

        ### Tell ROS that this node publishes Twist messages on the '/cmd_vel' topic
        self.pub_move = rospy.Publisher('/cmd_vel', Twist, queue_size=10)
        
        ### Tell ROS that this node subscribes to Odometry messages on the '/odom' topic, when a message is received, call self.update_odom
        rospy.Subscriber('/odom', Odometry, self.update_odometry)

        self.startPose = PoseStamped()
        self.startPose.pose.position = Point(self.px, self.py, 0)
        self.quatStart = quaternion_from_euler(0,0,self.pth)
        self.startPose.pose.orientation = Quaternion(self.quatStart[0], self.quatStart[1], self.quatStart[2], self.quatStart[3])

        #self.pathSub = rospy.Subscriber()
        ### Tell ROS that this node subscribes to Path messages on the '/path_planner/path' topic, and when a message is received, call self.execute_path
        #rospy.Subscriber('/path_planner/path', Path, self.executePath)

        ### Tell ROS that this node subscribes to PoseStamped messages on the '/move_base_simple/goal' topic, and when a message is received, call self.go_to
        #rospy.Subscriber('/path_planner/path', Path, self.executePath)

        subMove = rospy.Subscriber('/move_base_simple/goal',PoseStamped,self.executePath)

        rospy.sleep(.25) #Pause to let roscore recognize everything


    
    def executePath(self, msg):
        """
        Takes in a Path message as the goal
        records start location and requests plan from path planner
        obtains plan and executes all posedStamped waypoints
        """
        TOL = 0.1

        rospy.wait_for_service('plan_path')

        #Robot's Current Position
        PSstart = PoseStamped()
        PSstart.pose.position = Point(self.px,self.py,0)
        quat = quaternion_from_euler(0,0,self.pth)
        PSstart.pose.orientation = Quaternion(quat[0],quat[1],quat[2],quat[3])

        #Request path Planniung Service 
        req = GetPlan()
        path_planner = rospy.ServiceProxy('/plan_path',GetPlan)
        resp = path_planner(PSstart,msg,TOL)

        #self.pathPublisher.publish(resp.plan)
        
        #Extract Waypoints - start position??
        #resp.plan.poses.pop(0)

        for everyWaypoint in resp.plan.poses:
            #print(everyWaypoint)
            self.go_to(everyWaypoint)

        #Go Back to the starting position
	'''
        currPose = PoseStamped()
        currPose.pose.position = Point(self.px, self.py,0)
        quat = quaternion_from_euler(0,0,self.pth)
        currPose.pose.orientation = Quaternion(quat[0],quat[1],quat[2],quat[3])
	
        pathHome = rospy.ServiceProxy('/plan_path', GetPlan)
        trip = pathHome(currPose, PSstart, TOL)
	'''
	resp.plan.poses.reverse()
        for each in resp.plan.poses:
            self.go_to(each)
        
        rospy.loginfo('All Done!')


    def send_speed(self, linear_speed, angular_speed):
        """
        Sends the speeds to the motors.
        :param linear_speed  [float] [m/s]   The forward linear speed.
        :param angular_speed [float] [rad/s] The angular speed for rotating around the body center.
        """
        ### Make a new Twist message
        msg_cmd_vel = Twist()
        #Linear
        msg_cmd_vel.linear.x = linear_speed
        msg_cmd_vel.linear.y = 0.0
        msg_cmd_vel.linear.z = 0.0
        #Angular v        
        msg_cmd_vel.angular.x = 0.0
        msg_cmd_vel.angular.y = 0.0
        msg_cmd_vel.angular.z = angular_speed

        ### Publish the message
        self.pub_move.publish(msg_cmd_vel)

    
        
    def drive(self, distance, linear_speed):
        """
        Drives the robot in a straight line.
        This Function uses smooth drive in a linear fashion
        :param distance     [float] [m]   The distance to cover.
        :param linear_speed [float] [m/s] The forward linear speed.
        """
        #Save the initial x,y pose and orientation
        initX = self.px
        initY  = self.py
        initYaw = 0
        THRESH = .07    #Tolerance for distance measurement [m]
        
        #Yaw Closed Loop Controller Vals
        kpOmega = .4
        kiOmega = 0.0006
        kdOmega = 0.001
        omegaInt = 0
      
        kpDist = 0
        errorInt = 0    #Initialize the integral error
        start = True    #Flag for the robot motion
        end = False     #flag for the robot motion
        prevError = 0

        #print('SPEEDING UP')
        for x in range(1000):
            omegaError = 0 - self.omega
            omegaInt = omegaInt + omegaError
            omegaDir = omegaError - prevError
            self.send_speed(linear_speed*(float(x)/1000),kpOmega*omegaError + kiOmega*omegaInt + kdOmega*omegaDir)
            prevError = omegaError
            start = False
            run = True
        
        
        while(self.calc_distance(initX, self.px, initY, self.py) < distance - THRESH):
            print('Running at speed')
            omegaError = 0 - self.omega
            omegaInt = omegaInt + omegaError
            omegaDir = omegaError - prevError        #Integral of error used for ki term
            self.send_speed(linear_speed,kpOmega*omegaError + kiOmega*omegaInt + kdOmega*omegaDir)
        
        #Since the robot is within the tolerance, brake
        #print('BRAKING')
        for u in range(1000):
            self.send_speed(linear_speed*(float(1000-u)/1000),0)
        
        #print('Move Completed!')
        self.send_speed(0,0)

    def calc_distance(self,xInit, xFinal, yInit, yFinal):
        """
        Calculates the distance between 2 points on a 2D plane
        :param xInit    The starting x position [m]
        :param xFinal   The current / goal x position [m]
        :param yInit    The starting y position [m]
        :param yFinal   The current / goal y position [m]
        """
        xDiff = xFinal - xInit      #Find out horizontal distance from goal to robot
        yDiff = yFinal - yInit      #Find out vertical distance from goal to robot
        dist = sqrt(square(xDiff) + square(yDiff))      #Calculate hypotnuse of the created triangle
        return dist
        

    def rotate(self, angle, aspeed):
        """
        Rotates the robot around the body center by the given angle.
        :param angle         [float] [rad]   The distance to cover.
        :param angular_speed [float] [rad/s] The angular speed.
        """
        try:
            #angle = self.pth + angle    #Rotate x degrees relative to the current pos
            initPth = self.pth          #Store the current position
            THRESH = .1                #Threshold for angle difference [rad]
            
            #Adjust the angle to determine which side of the x axis it lies on
            if angle > pi:             
                angle = angvle - 2*pi    #if 180-360, set angle to a negative angle
            elif angle < -pi:
                angle = angle + 2*pi    #if -180--360, set angle to positive angle

            #Rotate while the error is less than an error
            while(abs(angle - self.pth) >= THRESH):
                #print(abs(angle - self.pth))
                error = angle - self.pth
                self.send_speed(0,self.turnDirection(angle, self.pth)*aspeed)
            
            #print('Done rotating')      #Print to confirm completion

            self.send_speed(0,0)        #Stop the robot motion
        except Exception as e:
            print('Failed on rotate')
            print(e)

    def turnDirection(self, goal, start):
        #remember, positive = CCW, neg = CW
        deltaAng = goal - start
        ROT = 1
        #print('robot currently at ' + str((180/pi) * start+90))
        #print('robot needs to go to ' + str((180/pi) * goal+90))
        if deltaAng <= 0:
            if abs(deltaAng) >= pi:
                #print('Turning CCW')
                return ROT
            else: 
                #print('Turning CW')
                return -1*ROT

        elif deltaAng > 0:
            if abs(deltaAng) > pi:
                #print('Turning CW')
                return -1*ROT
            else:
                #print('Turning CCW')
                return ROT
        
        

    def go_to(self, msg):
        """
        Calls rotate(), drive(), and rotate() to attain a given pose.
        This method is a callback bound to a Subscriber.
        :param msg [PoseStamped] The target pose.
        """
        try:
            ROT = .8    #Set in turnDirection Function
            #SPEED = .15
            SPEED = .22
            goal = msg.pose
            
            #1 Calculate Angle between current pose and goal (rotate)
            xDiff = goal.position.x - self.px   #Error in the x direction
            yDiff = goal.position.y - self.py   #Error in the y direction
            angToGoal = atan2(yDiff,xDiff)      #Calculate the angle based on the error
            self.rotate(angToGoal, ROT)
            rospy.sleep(.25)
            #2 Calculate Distance between current pose and goal (drive)
            distToGoal = self.calc_distance(self.px, goal.position.x, self.py, goal.position.y)
            rospy.loginfo("Driving " + str(distToGoal) + ' To get to the next goal')
            self.drive(distToGoal, SPEED)
            rospy.loginfo("Im at my goal!")
            rospy.sleep(.25)
            #3 Once at goal, rotate to desired orientation (rotate)
            quat_orig  = goal.orientation                            
            quat_list = [quat_orig.x, quat_orig.y, quat_orig.z, quat_orig.w]
            (roll, pitch, yaw) = euler_from_quaternion(quat_list)
            #Figure out which way to turn

            self.rotate(angToGoal, ROT)
            rospy.sleep(.25)

        except Exception as e:
            print('Failed on go_to()')
            print(e)
        


    def update_odometry(self, msg):
        """
        Updates the current pose of the robot.
        This method is a callback bound to a Subscriber.
        :param msg [Odometry] The current odometry information.
        """
        #Set the x and y positions of the robot
        self.omega = msg.twist.twist.angular.z
        self.px  = msg.pose.pose.position.x
        self.py  = msg.pose.pose.position.y
        #Set the robots orientation as a quaternion and create a list with the variables
        quat_orig  = msg.pose.pose.orientation                              
        quat_list = [quat_orig.x, quat_orig.y, quat_orig.z, quat_orig.w]  
        #Convert quaternion to rpy variables  
        (roll, pitch, yaw)= euler_from_quaternion(quat_list)
        #Set the robots yaw orientation
        self.pth = yaw
        

    def arc_to(self, position):
        """
        Drives to a given position in an arc.
        :param msg [PoseStamped] The target pose.
        """

        """
        IDEA FOR FUTURE USE: Set the ICC to the center of the distance to the desired point
        offset the ICC by a specified about to the left or right of the center of the ICC
        """
        ### EXTRA CREDIT
        # TODO
        pass # delete this when you implement your code

    def run(self):
        #print('Running')
        rospy.spin()

if __name__ == '__main__':
    Lab4().run()
