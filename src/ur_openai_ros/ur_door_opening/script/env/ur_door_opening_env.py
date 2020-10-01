#!/usr/bin/env python
'''
    By Akira Ebisui <shrimp.prawn.lobster713@gmail.com>
'''
# Python
import copy
import numpy as np
import math
import sys
import time
from matplotlib import pyplot as plt

# ROS 
import rospy
import tf
from tf.transformations import euler_from_quaternion, quaternion_from_euler

from joint_publisher import JointPub
from joint_traj_publisher import JointTrajPub

# Gazebo
from gazebo_msgs.srv import SetModelState, SetModelStateRequest, GetModelState
from gazebo_msgs.srv import GetWorldProperties
from gazebo_msgs.msg import LinkStates 

# For reset GAZEBO simultor
#from gazebo_connection import GazeboConnection
#from controllers_connection import ControllersConnection

# ROS msg
from geometry_msgs.msg import Pose, Point, Quaternion, Vector3, WrenchStamped
from sensor_msgs.msg import JointState, Imu
from std_msgs.msg import String
from std_srvs.srv import SetBool, SetBoolResponse, SetBoolRequest
from std_srvs.srv import Empty
from tactilesensors4.msg import StaticData, Dynamic

# Gym
import gym
from gym import utils, spaces
from gym.utils import seeding
from gym.envs.registration import register

# For inherit RobotGazeboEnv
from env import robot_gazebo_env_goal

# UR5 Utils
from env.ur_setups import setups
from env import ur_utils

from robotiq_interface_for_door import RobotiqInterface

rospy.loginfo("register...")
#register the training environment in the gym as an available one
reg = gym.envs.register(
    id='URSimDoorOpening-v0',
    entry_point='env.ur_door_opening_env:URSimDoorOpening', # Its directory associated with importing in other sources like from 'ur_reaching.env.ur_sim_env import *' 
    #timestep_limit=100000,
    )

class URSimDoorOpening(robot_gazebo_env_goal.RobotGazeboEnv):
    def __init__(self):
        rospy.logdebug("Starting URSimDoorOpening Class object...")

        # Subscribe joint state and target pose
        rospy.Subscriber("/wrench", WrenchStamped, self.wrench_stamped_callback)
        rospy.Subscriber("/joint_states", JointState, self.joints_state_callback)
        rospy.Subscriber("/TactileSensor4/StaticData", StaticData, self.tactile_static_callback)
        rospy.Subscriber("/TactileSensor4/Dynamic", Dynamic, self.tactile_dynamic_callback)
        rospy.Subscriber("/imu/data", Imu, self.rt_imu_callback)
        rospy.Subscriber("/imu/data_3dmg", Imu, self.microstrain_imu_callback)

        # Gets training parameters from param server
        self.desired_pose = Pose()
        self.running_step = rospy.get_param("/running_step")
        self.max_height = rospy.get_param("/max_height")
        self.min_height = rospy.get_param("/min_height")
        self.observations = rospy.get_param("/observations")
        
        # Joint limitation
        shp_max = rospy.get_param("/joint_limits_array/shp_max")
        shp_min = rospy.get_param("/joint_limits_array/shp_min")
        shl_max = rospy.get_param("/joint_limits_array/shl_max")
        shl_min = rospy.get_param("/joint_limits_array/shl_min")
        elb_max = rospy.get_param("/joint_limits_array/elb_max")
        elb_min = rospy.get_param("/joint_limits_array/elb_min")
        wr1_max = rospy.get_param("/joint_limits_array/wr1_max")
        wr1_min = rospy.get_param("/joint_limits_array/wr1_min")
        wr2_max = rospy.get_param("/joint_limits_array/wr2_max")
        wr2_min = rospy.get_param("/joint_limits_array/wr2_min")
        wr3_max = rospy.get_param("/joint_limits_array/wr3_max")
        wr3_min = rospy.get_param("/joint_limits_array/wr3_min")
        self.joint_limits = {"shp_max": shp_max,
                             "shp_min": shp_min,
                             "shl_max": shl_max,
                             "shl_min": shl_min,
                             "elb_max": elb_max,
                             "elb_min": elb_min,
                             "wr1_max": wr1_max,
                             "wr1_min": wr1_min,
                             "wr2_max": wr2_max,
                             "wr2_min": wr2_min,
                             "wr3_max": wr3_max,
                             "wr3_min": wr3_min
                             }

        # cartesian_limits
        self.x_max = rospy.get_param("/cartesian_limits/x_max")
        self.x_min = rospy.get_param("/cartesian_limits/x_min")
        self.y_max = rospy.get_param("/cartesian_limits/y_max")
        self.y_min = rospy.get_param("/cartesian_limits/y_min")
        self.z_max = rospy.get_param("/cartesian_limits/z_max")
        self.z_min = rospy.get_param("/cartesian_limits/z_min")

#        shp_init_value0 = rospy.get_param("/init_joint_pose0/shp")
#        shl_init_value0 = rospy.get_param("/init_joint_pose0/shl")
#        elb_init_value0 = rospy.get_param("/init_joint_pose0/elb")
#        wr1_init_value0 = rospy.get_param("/init_joint_pose0/wr1")
#        wr2_init_value0 = rospy.get_param("/init_joint_pose0/wr2")
#        wr3_init_value0 = rospy.get_param("/init_joint_pose0/wr3")
#        self.init_joint_pose0 = [shp_init_value0, shl_init_value0, elb_init_value0, wr1_init_value0, wr2_init_value0, wr3_init_value0]

        shp_init_value1 = rospy.get_param("/init_joint_pose1/shp")
        shl_init_value1 = rospy.get_param("/init_joint_pose1/shl")
        elb_init_value1 = rospy.get_param("/init_joint_pose1/elb")
        wr1_init_value1 = rospy.get_param("/init_joint_pose1/wr1")
        wr2_init_value1 = rospy.get_param("/init_joint_pose1/wr2")
        wr3_init_value1 = rospy.get_param("/init_joint_pose1/wr3")
        self.init_joint_pose1 = [shp_init_value1, shl_init_value1, elb_init_value1, wr1_init_value1, wr2_init_value1, wr3_init_value1]
        init_pos1 = self.init_joints_pose(self.init_joint_pose1)
        self.arr_init_pos1 = np.array(init_pos1, dtype='float32')

        shp_init_value2 = rospy.get_param("/init_joint_pose2/shp")
        shl_init_value2 = rospy.get_param("/init_joint_pose2/shl")
        elb_init_value2 = rospy.get_param("/init_joint_pose2/elb")
        wr1_init_value2 = rospy.get_param("/init_joint_pose2/wr1")
        wr2_init_value2 = rospy.get_param("/init_joint_pose2/wr2")
        wr3_init_value2 = rospy.get_param("/init_joint_pose2/wr3")
        self.init_joint_pose2 = [shp_init_value2, shl_init_value2, elb_init_value2, wr1_init_value2, wr2_init_value2, wr3_init_value2]
        init_pos2 = self.init_joints_pose(self.init_joint_pose2)
        self.arr_init_pos2 = np.array(init_pos2, dtype='float32')

        shp_far_pose = rospy.get_param("/far_pose/shp")
        shl_far_pose = rospy.get_param("/far_pose/shl")
        elb_far_pose = rospy.get_param("/far_pose/elb")
        wr1_far_pose = rospy.get_param("/far_pose/wr1")
        wr2_far_pose = rospy.get_param("/far_pose/wr2")
        wr3_far_pose = rospy.get_param("/far_pose/wr3")
        self.far_pose = [shp_far_pose, shl_far_pose, elb_far_pose, wr1_far_pose, wr2_far_pose, wr3_far_pose]
        far_pose = self.init_joints_pose(self.far_pose)
        self.arr_far_pose = np.array(far_pose, dtype='float32')

        shp_before_close_pose = rospy.get_param("/before_close_pose/shp")
        shl_before_close_pose = rospy.get_param("/before_close_pose/shl")
        elb_before_close_pose = rospy.get_param("/before_close_pose/elb")
        wr1_before_close_pose = rospy.get_param("/before_close_pose/wr1")
        wr2_before_close_pose = rospy.get_param("/before_close_pose/wr2")
        wr3_before_close_pose = rospy.get_param("/before_close_pose/wr3")
        self.before_close_pose = [shp_before_close_pose, shl_before_close_pose, elb_before_close_pose, wr1_before_close_pose, wr2_before_close_pose, wr3_before_close_pose]
        before_close_pose = self.init_joints_pose(self.before_close_pose)
        self.arr_before_close_pose = np.array(before_close_pose, dtype='float32')

        shp_close_door_pose = rospy.get_param("/close_door_pose/shp")
        shl_close_door_pose = rospy.get_param("/close_door_pose/shl")
        elb_close_door_pose = rospy.get_param("/close_door_pose/elb")
        wr1_close_door_pose = rospy.get_param("/close_door_pose/wr1")
        wr2_close_door_pose = rospy.get_param("/close_door_pose/wr2")
        wr3_close_door_pose = rospy.get_param("/close_door_pose/wr3")
        self.close_door_pose = [shp_close_door_pose, shl_close_door_pose, elb_close_door_pose, wr1_close_door_pose, wr2_close_door_pose, wr3_close_door_pose]
        close_door_pose = self.init_joints_pose(self.close_door_pose)
        self.arr_close_door_pose = np.array(close_door_pose, dtype='float32')

        # Fill in the Done Episode Criteria list
        self.episode_done_criteria = rospy.get_param("/episode_done_criteria")
        
        # Controller type for ros_control
        self._ctrl_type =  rospy.get_param("/control_type")
        self.pre_ctrl_type =  self._ctrl_type

	# Get the force and troque limit
        self.force_limit = rospy.get_param("/force_limit")
        self.torque_limit = rospy.get_param("/torque_limit")

        # We init the observations
        self.quat = Quaternion()
        self.door_rpy = Vector3()
        self.door_rotation = Vector3()
        self.door_rpy_ini = Vector3()
        self.knob_rpy = []
        self.knob_rotation = []
        self.knob_rpy_ini = []
        self.link_state = LinkStates()
        self.wrench_stamped = WrenchStamped()
        self.joints_state = JointState()
        self.tactile_static = StaticData()
        self.tactile_dynamic = Dynamic()
        self.rt_imu = Imu()
        self.microstrain_imu = Imu()
        self.end_effector = Point() 
        self.previous_action =[1.521, -1.346, 2.307, 2.180, -1.521, 1.566]

        # Arm/Control parameters
        self._ik_params = setups['UR5_6dof']['ik_params']
        
        # ROS msg type
        self._joint_pubisher = JointPub()
        self._joint_traj_pubisher = JointTrajPub()

        # Gym interface and action
        self.action_space = spaces.Discrete(6)
        self.observation_space = 77 #np.arange(self.get_observations().shape[0])
        self.reward_range = (-np.inf, np.inf)
        self._seed()

        # Gripper interface
        self.gripper = RobotiqInterface()

        # Joint trajectory publisher
        self.jointpub = JointTrajPub()

    def check_stop_flg(self):
        if self.stop_flag is False:
            return False
        else:
            return True

    def _start_trainnig(self, req):
        rospy.logdebug("_start_trainnig!!!!")
        self.stop_flag = False
        return SetBoolResponse(True, "_start_trainnig")

    def _stop_trainnig(self, req):
        rospy.logdebug("_stop_trainnig!!!!")
        self.stop_flag = True
        return SetBoolResponse(True, "_stop_trainnig")

    # A function to initialize the random generator
    def _seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]
        
    def check_all_systems_ready(self):
        """
        We check that all systems are ready
        :return:
        """
        joint_states_msg = None
        while joint_states_msg is None and not rospy.is_shutdown():
            try:
                joint_states_msg = rospy.wait_for_message("/joint_states", JointState, timeout=0.1)
                self.joints_state = joint_states_msg
                rospy.logdebug("Current joint_states READY")
            except Exception as e:
                self._ctrl_conn.start_controllers(controllers_on="joint_state_controller")                
                rospy.logdebug("Current joint_states not ready yet, retrying==>"+str(e))

        rospy.logdebug("ALL SYSTEMS READY")

    def check_cartesian_limits(self, action):
        ee_xyz = Point()
        ee_xyz = self.get_xyz(action)
#        print("action.z", ee_xyz[2])
        if self.x_min < ee_xyz[0] and ee_xyz[0] < self.x_max and self.y_min < ee_xyz[1] and ee_xyz[1] < self.y_max and self.z_min < ee_xyz[2] and ee_xyz[2] < self.z_max:
            return True
        else:
            return False

    def get_xyz(self, q):
        """Get x,y,z coordinates 
        Args:
            q: a numpy array of joints angle positions.
        Returns:
            xyz are the x,y,z coordinates of an end-effector in a Cartesian space.
        """
        mat = ur_utils.forward(q, self._ik_params)
        xyz = mat[:3, 3]
        return xyz

    def get_current_xyz(self):
        """Get x,y,z coordinates according to currrent joint angles
        Returns:
        xyz are the x,y,z coordinates of an end-effector in a Cartesian space.
        """
        joint_states = self.joints_state
        shp_joint_ang = joint_states.position[0]
        shl_joint_ang = joint_states.position[1]
        elb_joint_ang = joint_states.position[2]
        wr1_joint_ang = joint_states.position[3]
        wr2_joint_ang = joint_states.position[4]
        wr3_joint_ang = joint_states.position[5]
        
        q = [shp_joint_ang, shl_joint_ang, elb_joint_ang, wr1_joint_ang, wr2_joint_ang, wr3_joint_ang]
        mat = ur_utils.forward(q, self._ik_params)
        xyz = mat[:3, 3]
        return xyz
            
    def get_orientation(self, q):
        """Get Euler angles 
        Args:
            q: a numpy array of joints angle positions.
        Returns:
            xyz are the x,y,z coordinates of an end-effector in a Cartesian space.
        """
        mat = ur_utils.forward(q, self._ik_params)
        orientation = mat[0:3, 0:3]
        roll = -orientation[1, 2]
        pitch = orientation[0, 2]
        yaw = -orientation[0, 1]
        
        return Vector3(roll, pitch, yaw)


    def cvt_quat_to_euler(self, quat):
        euler_rpy = Vector3()
        euler = euler_from_quaternion([self.quat.x, self.quat.y, self.quat.z, self.quat.w])
        euler_rpy.x = euler[0]
        euler_rpy.y = euler[1]
        euler_rpy.z = euler[2]
        return euler_rpy

    def init_joints_pose(self, init_pos):
        """
        We initialise the Position variable that saves the desired position where we want our
        joints to be
        :param init_pos:
        :return:
        """
        self.current_joint_pose =[]
        self.current_joint_pose = copy.deepcopy(init_pos)
#	print("[current_joint_pose]:", self.current_joint_pose, type(self.current_joint_pose))
        return self.current_joint_pose

    def get_euclidean_dist(self, p_in, p_pout):
        """
        Given a Vector3 Object, get distance from current position
        :param p_end:
        :return:
        """
        a = numpy.array((p_in.x, p_in.y, p_in.z))
        b = numpy.array((p_pout.x, p_pout.y, p_pout.z))

        distance = numpy.linalg.norm(a - b)

        return distance

    def joints_state_callback(self,msg):
        self.joints_state = msg

    def wrench_stamped_callback(self,msg):
        self.wrench_stamped = msg

    def tactile_static_callback(self,msg):
        self.tactile_static = msg

    def tactile_dynamic_callback(self,msg):
        self.tactile_dynamic = msg

    def rt_imu_callback(self,msg):
        self.rt_imu = msg

    def microstrain_imu_callback(self,msg):
        self.microstrain_imu = msg

    def joint_trajectory(self,msg):
        self.jointtrajectory = msg

    def get_observations(self):
        """
        Returns the state of the robot needed for OpenAI QLearn Algorithm
        The state will be defined by an array
        :return: observation
        """
        joint_states = self.joints_state
        self.force = self.wrench_stamped.wrench.force
        self.torque = self.wrench_stamped.wrench.torque
        static_taxel = self.tactile_static.taxels
#        dynamic_taxel= tactile_dynamic

#        print("[force]", self.force.x, self.force.y, self.force.z)
#        print("[torque]", self.torque.x, self.torque.y, self.torque.z)
        shp_joint_ang = joint_states.position[0]
        shl_joint_ang = joint_states.position[1]
        elb_joint_ang = joint_states.position[2]
        wr1_joint_ang = joint_states.position[3]
        wr2_joint_ang = joint_states.position[4]
        wr3_joint_ang = joint_states.position[5]

        shp_joint_vel = joint_states.velocity[0]
        shl_joint_vel = joint_states.velocity[1]
        elb_joint_vel = joint_states.velocity[2]
        wr1_joint_vel = joint_states.velocity[3]
        wr2_joint_vel = joint_states.velocity[4]
        wr3_joint_vel = joint_states.velocity[5]

        q = [shp_joint_ang, shl_joint_ang, elb_joint_ang, wr1_joint_ang, wr2_joint_ang, wr3_joint_ang]
#        print("q(observation):", q)
        eef_x, eef_y, eef_z = self.get_xyz(q)
        self.end_effector = self.get_xyz(q)

        observation = []
#        rospy.logdebug("List of Observations==>"+str(self.observations))
        for obs_name in self.observations:
            if obs_name == "shp_joint_ang":
                observation.append(shp_joint_ang)
            elif obs_name == "shl_joint_ang":
                observation.append(shl_joint_ang)
            elif obs_name == "elb_joint_ang":
                observation.append(elb_joint_ang)
            elif obs_name == "wr1_joint_ang":
                observation.append(wr1_joint_ang)
            elif obs_name == "wr2_joint_ang":
                observation.append(wr2_joint_ang)
            elif obs_name == "wr3_joint_ang":
                observation.append(wr3_joint_ang)
            elif obs_name == "shp_joint_vel":
                observation.append(shp_joint_vel)
            elif obs_name == "shl_joint_vel":
                observation.append(shl_joint_vel)
            elif obs_name == "elb_joint_vel":
                observation.append(elb_joint_vel)
            elif obs_name == "wr1_joint_vel":
                observation.append(wr1_joint_vel)
            elif obs_name == "wr2_joint_vel":
                observation.append(wr2_joint_vel)
            elif obs_name == "wr3_joint_vel":
                observation.append(wr3_joint_vel)
            elif obs_name == "eef_x":
                observation.append(eef_x)
            elif obs_name == "eef_y":
                observation.append(eef_y)
            elif obs_name == "eef_z":
                observation.append(eef_z)
            elif obs_name == "force_x":
                observation.append(self.force.x)
            elif obs_name == "force_y":
                observation.append(self.force.y)
            elif obs_name == "force_z":
                observation.append(self.force.z)
            elif obs_name == "torque_x":
                observation.append(self.torque.x)
            elif obs_name == "torque_y":
                observation.append(self.torque.y)
            elif obs_name == "torque_z":
                observation.append(self.torque.z)
            elif obs_name == "static_taxel":
                for x in range(0, 28):
                    observation.append(static_taxel[0].values[x])
                for x in range(0, 28):
                    observation.append(static_taxel[1].values[x])
#            elif obs_name == "dynamic_taxel":
#                observation.append(dynamic_taxel[0].values[x])
#                for x in range(0, 1):
#                    observation.append(dynamic_taxel[0].values[x])
#                for x in range(0, 1):
#                    observation.append(dynamic_taxel[1].values[x])
            else:
                raise NameError('Observation Asked does not exist=='+str(obs_name))

        return observation

    def clamp_to_joint_limits(self):
        """
        clamps self.current_joint_pose based on the joint limits
        self._joint_limits
        {
         "shp_max": shp_max,
         "shp_min": shp_min,
         ...
         }
        :return:
        """

        rospy.logdebug("Clamping current_joint_pose>>>" + str(self.current_joint_pose))
        shp_joint_value = self.current_joint_pose[0]
        shl_joint_value = self.current_joint_pose[1]
        elb_joint_value = self.current_joint_pose[2]
        wr1_joint_value = self.current_joint_pose[3]
        wr2_joint_value = self.current_joint_pose[4]
        wr3_joint_value = self.current_joint_pose[5]

        self.current_joint_pose[0] = max(min(shp_joint_value, self._joint_limits["shp_max"]), self._joint_limits["shp_min"])
        self.current_joint_pose[1] = max(min(shl_joint_value, self._joint_limits["shl_max"]), self._joint_limits["shl_min"])
        self.current_joint_pose[2] = max(min(elb_joint_value, self._joint_limits["elb_max"]), self._joint_limits["elb_min"])
        self.current_joint_pose[3] = max(min(wr1_joint_value, self._joint_limits["wr1_max"]), self._joint_limits["wr1_min"])
        self.current_joint_pose[4] = max(min(wr2_joint_value, self._joint_limits["wr2_max"]), self._joint_limits["wr2_min"])
        self.current_joint_pose[5] = max(min(wr3_joint_value, self._joint_limits["wr3_max"]), self._joint_limits["wr3_min"])

        rospy.logdebug("DONE Clamping current_joint_pose>>>" + str(self.current_joint_pose))

    # Resets the state of the environment and returns an initial observation.
    def reset(self):
	# 1st: Go to initial position
        rospy.logdebug("set_init_pose init variable...>>>" + str(self.init_joint_pose1))

        self.gripper.goto_gripper_pos(0, False)
        time.sleep(1)
        self.jointpub.FollowJointTrajectoryCommand(self.arr_far_pose)
#        time.sleep(0.3)
        self.jointpub.FollowJointTrajectoryCommand(self.arr_before_close_pose)
#        time.sleep(0.3)
        self.jointpub.FollowJointTrajectoryCommand(self.arr_close_door_pose)
#        time.sleep(0.3)
        self.jointpub.FollowJointTrajectoryCommand(self.arr_init_pos1)
#        time.sleep(0.3)

        # 2nd: Check all subscribers work.
        rospy.logdebug("check_all_systems_ready...")
        self.check_all_systems_ready()

        # 3rd: Get the initial state.
        self.knob_rpy_ini = copy.deepcopy(self.microstrain_imu.linear_acceleration.y / 9.8 * 1.57)
        self.quat = self.rt_imu.orientation
        self.door_rpy_ini = copy.deepcopy(self.cvt_quat_to_euler(self.quat))
#        print("knob_ini", self.knob_rpy_ini)
#        print("door_ini", self.door_rpy_ini)

        # 4th: Go to start position.
        self.jointpub.FollowJointTrajectoryCommand(self.arr_init_pos2)
        time.sleep(0.3)
        self.gripper.goto_gripper_pos(120, False)

        # 5th: Get the State Discrete Stringuified version of the observations
        rospy.logdebug("get_observations...")
       	observation = self.get_observations()
        return observation

    def _act(self, action):
        if self._ctrl_type == 'traj_pos':
            self.pre_ctrl_type = 'traj_pos'
            self._joint_traj_pubisher.FollowJointTrajectoryCommand(action)
        elif self._ctrl_type == 'pos':
            self.pre_ctrl_type = 'pos'
            self._joint_pubisher.move_joints(action)
        elif self._ctrl_type == 'traj_vel':
            self.pre_ctrl_type = 'traj_vel'
            self._joint_traj_pubisher.FollowJointTrajectoryCommand(action)
        elif self._ctrl_type == 'vel':
            self.pre_ctrl_type = 'vel'
            self._joint_pubisher.move_joints(action)
        else:
            self._joint_pubisher.move_joints(action)
        
    def training_ok(self):
        rate = rospy.Rate(1)
        while self.check_stop_flg() is True:                  
            rospy.logdebug("stop_flag is ON!!!!")
            self._gz_conn.unpauseSim()

            if self.check_stop_flg() is False:
                break 
            rate.sleep()
                
    def step(self, action):
        '''
        ('action: ', array([ 0.,  0. , -0., -0., -0. , 0. ], dtype=float32))        
        '''
        rospy.logdebug("UR step func")	# define the logger

        # Given the action selected by the learning algorithm,
        # we perform the corresponding movement of the robot
        # Act

        action = action + self.arr_init_pos2

        if self.check_cartesian_limits(action) is True:
            self._act(action)
            self.wrench_stamped
            self.force = self.wrench_stamped.wrench.force
            self.torque = self.wrench_stamped.wrench.torque
            if self.force_limit < self.force.x or self.force.x < -self.force_limit:
                self._act(self.previous_action)
                print("force.x over the limit")
            elif self.force_limit < self.force.y or self.force.y < -self.force_limit:
                self._act(self.previous_action)
                print("force.y over the limit")
            elif self.force_limit < self.force.z or self.force.z < -self.force_limit:
                self._act(self.previous_action)
                print("force.z over the limit")
            elif self.torque_limit < self.torque.x or self.torque.x < -self.torque_limit:
                self._act(self.previous_action)
                print("torque.x over the limit")
            elif self.torque_limit < self.torque.y or self.torque.y < -self.torque_limit:
                self._act(self.previous_action)
                print("torque.y over the limit")
            elif self.torque_limit < self.torque.z or self.torque.z < -self.torque_limit:
                self._act(self.previous_action)
                print("torque.z over the limit")
            else:
                self.previous_action = copy.deepcopy(action)
                print("True")
        else:
            print("False")

        # We now process the latest data saved in the class state to calculate
        # the state and the rewards. This way we guarantee that they work
        # with the same exact data.
        # Generate State based on observations
        observation = self.get_observations()

        # finally we get an evaluation based on what happened in the sim
        reward = self.compute_dist_rewards()
        done = self.check_done()

        return observation, reward, done, {}

    def compute_dist_rewards(self):
        compute_rewards = 0
        self.quat = self.rt_imu.orientation
        self.door_rpy = self.cvt_quat_to_euler(self.quat)
        self.door_rotation.x = self.door_rpy.x - self.door_rpy_ini.x
        self.door_rotation.y = self.door_rpy.y - self.door_rpy_ini.y
        self.door_rotation.z = self.door_rpy.z - self.door_rpy_ini.z
        
        self.knob_rpy = self.microstrain_imu.linear_acceleration.y / 9.8 * 1.57
        self.knob_rotation = self.knob_rpy_ini - self.knob_rpy

        print("knob_rotation", self.knob_rotation)
#        print("door_rotation.x", self.door_rotation.x)
#        print("door_rotation.y", self.door_rotation.y)
        print("door_rotation.z", self.door_rotation.z)

        if self.knob_rotation < 0.9:
            compute_rewards = self.knob_rotation
        else:
            compute_rewards = 0.9 + self.door_rotation.z * 10

	return compute_rewards

    def check_done(self):
        if self.knob_rotation > 0.9 and self.door_rotation.z > 0.2:
            print("done")
            return True
        else :
        	return False
