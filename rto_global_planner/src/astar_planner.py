#!/usr/bin/env python

import rospy
import numpy as np
import tf

from std_msgs.msg import String
from geometry_msgs.msg import Twist, Point, Quaternion, Pose, PoseStamped, PoseWithCovarianceStamped
from sensor_msgs.msg import LaserScan
from nav_msgs.msg import OccupancyGrid, MapMetaData, Path
from visualization_msgs.msg import Marker

# from rto_map_server.srv import GetMap

#TODO:fix bugs in the algorithm
#TODO:fit it to different maps
#TODO:make it can publish command to cmd_vel
#TODO:fit to different resolutions
#TODO:speed up second search

class Node():
    """
    A node class for A* Pathfinding
    """

    def __init__(self, parent=None, position=None):
        self.parent = parent
        self.position = position

        self.g = 0
        self.h = 0
        self.f = 0

    def __eq__(self, other):
        return self.position == other.position

class Astar_Planner():
    """
    Independent Astar_Planner function class
    """

    def getMinNode(self):
        """
        try to find the node with minimal f in openlist
        """
        currentNode = self.open_list[0]
        for node in self.open_list:
            if node.g + node.h < currentNode.g + currentNode.h:
                currentNode = node
        return currentNode

    def pointInCloseList(self, position):
        """
        determine if a node is in closedlist
        """
        for node in self.closed_list:
            if node.position == position:
                return True
        return False

    def pointInOpenList(self, position):
        """
        determine if a node is in openlist
        """
        for node in self.open_list:
            if node.position == position:
                return node
        return None

    def endPointInCloseList(self):
        """
        determine if a node is endnode
        """
        for node in self.closed_list:
            if node.position == self.endnode.position:
                return node
        return None

    def search(self, minF, offsetX, offsetY):
        """
        search action with minimal f for next step
        """

        node_pos = (minF.position[0] + offsetX, minF.position[1] + offsetY)

        #TODO:update out of boundary rule
        # if the offset is out of boundary
        if node_pos[0] > self.map_width - 1 or node_pos[1] > self.map_height - 1:
            return

        # if the offset is valid
        elif self.map[int(node_pos[0])][int(node_pos[1])] != 0:
            return

        # if the node is in closed set, then pass
        elif self.pointInCloseList(node_pos):
            return

        else:
            # if it is not in openlist, add it to openlist
            currentNode = self.pointInOpenList(node_pos)
            if not currentNode:
                currentNode = Node(minF, node_pos)
                currentNode.g = minF.g + 1
                currentNode.h = abs(node_pos[0] - self.endnode.position[0]) + abs(node_pos[1] - self.endnode.position[1])
                currentNode.f = currentNode.g + currentNode.h
                self.open_list.append(currentNode)
                return
            else:
                # if it is in openlist, determine if g of currentnode is smaller
                if minF.g + 1 < currentNode.g:
                    currentNode.g = minF.g + 1
                    currentNode.parent = minF
                    return

    def astar(self, gridmap, map_width, map_height, start, end):
        """
        main function of astar search
        """

        # Initialize end node and start node
        self.startnode = Node(None, start)
        self.startnode.g = self.startnode.h = self.startnode.f = 0
        self.endnode = Node(None, end)
        self.endnode.g = self.endnode.h = self.endnode.f = 0
        self.map = gridmap
        self.map_width = map_width
        self.map_height = map_height

        # Initialize open and closed list
        self.open_list = [self.startnode] # store f of next possible step
        self.closed_list = [] # store f of minimal path

        # try to find the path with minimal cost
        while True:

            # find the node with minimal f in openlist
            minF = self.getMinNode()

            # add this node to closed_list and delete this node from open_list
            self.closed_list.append(minF)
            self.open_list.remove(minF)

            # apply search to add node for next step in 8 directions
            self.search(minF, 0, 1)
            self.search(minF, 1, 0)
            self.search(minF, 0, -1)
            self.search(minF, -1, 0)

            # determine if it the endpoint
            endnode = self.endPointInCloseList()
            if endnode:
                path = []
                current = endnode
                while current is not None:
                    path.append(current.position)
                    current = current.parent
                return path[::-1]

class main():
    """
    implement of global planner, neccessary subscribers and publishers
    """

    def __init__(self):

        # Initialize Subscribers
        self.sub_pos = rospy.Subscriber('/amcl_pose', PoseWithCovarianceStamped, self.callback_pos)
        # self.sub_map = rospy.Subscriber('/move_base/global_costmap/costmap', OccupancyGrid, self.callback_costmap)
        self.sub_map = rospy.Subscriber('/map', OccupancyGrid, self.callback_map)
        self.sub_goal = rospy.Subscriber('/move_base_simple/goal', PoseStamped, self.callback_goal)

        # Initialize Publisher
        self.pub_path = rospy.Publisher('/global_path', Path, queue_size=10)
        self.pub_plan = rospy.Publisher('/visualization/plan', Marker, queue_size=10)
        # self.pub_cmd = rospy.Publisher('/cmd_vel',Twist, queue_size=10)

        # Initialize messages
        self.msg_path = Path()
        self.msg_path.header.stamp = rospy.Time.now()
        self.msg_path.header.frame_id = "path"

        self.msg_path_marker = Marker()
        self.msg_path_marker.header.frame_id = "map"
        self.msg_path_marker.ns = "navigation"
        self.msg_path_marker.id = 0
        self.msg_path_marker.type = Marker.LINE_STRIP
        self.msg_path_marker.action = Marker.ADD
        self.msg_path_marker.scale.x = 0.1
        self.msg_path_marker.color.a = 0.5
        self.msg_path_marker.color.r = 0.0
        self.msg_path_marker.color.g = 0.0
        self.msg_path_marker.color.b = 1.0
        self.msg_path_marker.pose.orientation = Quaternion(0, 0, 0, 1)

    def callback_pos(self, PoseWithCovarianceStamped):
        """
        callback of position
        """
        self.pos_x = int((PoseWithCovarianceStamped.pose.pose.position.x + 3.246519) / 0.05)
        self.pos_y = int((PoseWithCovarianceStamped.pose.pose.position.y + 3.028618) / 0.05)

    def callback_map(self, OccupancyGrid):
        """
        callback of map
        """
        self.map_input = np.array(OccupancyGrid.data)
        self.map_width = OccupancyGrid.info.width
        self.map_height = OccupancyGrid.info.height
        self.map = self.map_input.reshape(self.map_height, self.map_width) # shape of 169(width)*116(height)
        self.map = np.transpose(self.map)

    def callback_goal(self, PoseStamped):
        """
        callback of goal
        """
        # shift position to position in map
        self.goal_x = int((PoseStamped.pose.position.x + 3.246519) / 0.05)
        self.goal_y = int((PoseStamped.pose.position.y + 3.028618) / 0.05)

    def check_valid(self, goalx, goaly):
        """
        check the validility of goal
        """
        if self.map[int(goalx)][int(goaly)] == 0:
            return True
        else:
            return None

    # run astar node
    def run(self, rate: float = 1):

        while not rospy.is_shutdown():

            # wait for goal input to start global planner
            rospy.wait_for_message('/move_base_simple/goal', PoseStamped)
            global_planner = Astar_Planner()

            # initialize start node
            start = (self.pos_x, self.pos_y)

            if self.check_valid(self.goal_x, self.goal_y):

                end = (int(self.goal_x), int(self.goal_y))
                path = global_planner.astar(self.map, self.map_width, self.map_height, start, end)

                # publish path
                for pa in path:
                    pose = PoseStamped()
                    pose.pose.position.x = pa[0]
                    pose.pose.position.y = pa[1]
                    self.msg_path.poses.append(pose)
                self.pub_path.publish(self.msg_path)
                self.msg_path.poses.clear()
                rospy.loginfo('Path is published')

                # publish plan
                for p in path:
                    self.msg_path_marker.points.append(Point(p[0]*0.05 - 3.246519, p[1]*0.05 - 3.028618, 0))
                self.pub_plan.publish(self.msg_path_marker)
                self.msg_path_marker.points.clear()

            else:
                rospy.loginfo('Goal is not valid')



if __name__ == "__main__":
   rospy.init_node('rto_global_planner')

   main = main()
   main.run(rate=1)