# !/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import xml.dom.minidom
import numpy as np
import pyproj
import sys


class Config:

    def __init__(self, ws_dirs):
        self.ws_dirs = ws_dirs
        self.dir_in = self.ws_dirs[1]
        self.dir_out = self.ws_dirs[2]
        self.file_points = os.path.join(self.ws_dirs[0], 'points.txt')
        self.file_junctions = os.path.join(self.ws_dirs[0], 'junctions.txt')

        self.dis_delta = 8.1  # self.radius = 14m


def getDocPaths(dir_name):
    # txt file

    filepathList = []

    for maindir, subdir, fileListStr in os.walk(dir_name):
        fileList = []
        for each in fileListStr:
            try:
                file_number = int(each[:-4])
                fileList.append(file_number)
            except:
                print('Ignore <%s>' % each)

        for each in sorted(fileList):
            filename = str(each) + '.txt'
            filepath = os.path.join(maindir, filename)
            filepathList.append(filepath)

    print("Dir <%s> has %d files." % (maindir, len(filepathList)))

    return filepathList


def get_temp_seg(path_list):
    # 读取暂存路段中的点并进行坐标转换，转换到投影坐标系中
    p1 = pyproj.Proj(init="epsg:4326")
    p2 = pyproj.Proj(init="epsg:3857")
    way_id = 10000
    points_all_segs = []
    for each_path in path_list:
        points = np.loadtxt(each_path, skiprows=(1), dtype={'names': ('num', 'lon', 'lat', 'alt', 'item'),
                                                            'formats': (int, float, float, float, int)})
        i = 1
        points_seg = []
        for point in points:
            x, y = pyproj.transform(p1, p2, point[1], point[2])
            point_id = way_id + i
            point_PCS = [x, y, point_id]
            points_seg.append(point_PCS)
            i = i + 1

        points_all_segs.append(points_seg)
        way_id = way_id + 10000

    return points_all_segs


def setIntersection(points, points_stack, way_id, dis_delta):

    print('******Setting junction point. Way id: %d******' % way_id)

    shape = points_stack.shape

    if not shape[0]:
        points_stack = np.vstack([points[0], points[-1]])
        print('First way, set two junction points')
    else:
        points_stack, point = stackPoint(
            points[0], points_stack, dis_delta, index_str='First point')
        points[0] = point
        points_stack, point = stackPoint(
            points[-1], points_stack, dis_delta, index_str='Last point')
        points[-1] = point

    # print(points_stack.shape)
    return points, points_stack


def calcDis(point, points_stack):

    lon_delta = np.subtract(point[0], points_stack[:, 0])
    lat_delta = np.subtract(point[1], points_stack[:, 1])
    dis = np.sqrt(np.multiply(lon_delta, lon_delta) + np.multiply(lat_delta, lat_delta))
    dis = dis[:, np.newaxis]

    return np.hstack([points_stack, dis])


def stackPoint(point, points_stack, dis_delta, index_str=''):

    points_stack_dis = calcDis(point, points_stack)
    # print(points_stack_dis)
    point_stack_dis_min = points_stack_dis.min(axis=0)
    # print(point_stack_dis_min.shape)
    index = np.argwhere(points_stack_dis == point_stack_dis_min[-1])
    row = index[0][0]
    col = index[0][1]
    # print(row, col)

    if abs(point_stack_dis_min[-1]) < dis_delta:
        point_lon = points_stack_dis[row, 0]
        point_lat = points_stack_dis[row, 1]
        point_id = points_stack_dis[row, col - 1]
        print('%s already exits in junction points, point id: %d.' % (index_str, point_id))
        point = [point_lon, point_lat, point_id]

    else:
        points_stack = np.vstack([points_stack, point])
        print('%s stacked.' % index_str)

    return points_stack, point


def writeXML(points, way_id, config):

    print('Writing XML')
    p1 = pyproj.Proj(init="epsg:4326")
    p2 = pyproj.Proj(init="epsg:3857")

    doc = xml.dom.minidom.Document()
    doc.appendChild(doc.createComment("Generated by python, Author: Mengze."))
    osmNode = doc.createElement("osm")
    doc.appendChild(osmNode)

    addNode(doc, osmNode, points, p1, p2)
    addWay(doc, osmNode, points, way_id, p1, p2)

    file_name = '%s/%d.xml' % (config.dir_out, way_id)
    print(file_name)

    with open(file_name, 'w') as f:
        doc.writexml(f, addindent="    ", newl="\n", encoding="UTF-8")

    print('Done!')


def addNode(doc, osmNode, points, p1, p2):

    count = 0
    for point in points:
        point[0], point[1] = pyproj.transform(p2, p1, point[0], point[1])
        count += 1
        lon = '%.8f' % point[0]
        lat = '%.8f' % point[1]
        point_id = '%d' % point[2]
        pointNode = doc.createElement("node")
        pointNode.setAttribute('id', point_id)
        pointNode.setAttribute('lat', lat)
        pointNode.setAttribute('lon', lon)

        if (count == 1) | (count == len(points)):

            point_tagNode = doc.createElement("tag")
            point_tagNode.setAttribute('k', "highway")
            point_tagNode.setAttribute('v', "traffic_signals")
            pointNode.appendChild(point_tagNode)

        osmNode.appendChild(pointNode)


def addWay(doc, osmNode, points, way_id, p1, p2):

    way_id_str = '%d' % way_id
    wayNode = doc.createElement("way")
    wayNode.setAttribute('id', way_id_str)
    osmNode.appendChild(wayNode)

    for point in points:
        point[0], point[1] = pyproj.transform(p2, p1, point[0], point[1])
        point_id = '%d' % point[2]
        ndtNode = doc.createElement("nd")
        ndtNode.setAttribute('ref', point_id)
        wayNode.appendChild(ndtNode)

    way_tagNode = doc.createElement("tag")
    way_tagNode.setAttribute('k', "name:en")
    way_tagNode.setAttribute('v', "double way")

    wayNode.appendChild(way_tagNode)


def saveData(points_all, points_stack, dir_points, dir_junctions):
    p1 = pyproj.Proj(init="epsg:4326")
    p2 = pyproj.Proj(init="epsg:3857")

    points_all[:, 0], points_all[:, 1] = pyproj.transform(
        p2, p1, points_all[:, 0], points_all[:, 1])
    points_stack[:, 0], points_stack[:, 1] = pyproj.transform(
        p2, p1, points_stack[:, 0], points_stack[:, 1])
    np.savetxt(dir_points, points_all, fmt='%.8f %.8f %d')
    np.savetxt(dir_junctions, points_stack, fmt='%.8f %.8f %d')


def genRoad(ws_dirs):
    print(ws_dirs)
    config = Config(ws_dirs)
    filepath_in = getDocPaths(config.dir_in)

    points_stack = np.empty(shape=[0, 3])
    points_all = np.empty(shape=[0, 3])

    points_all_segs = get_temp_seg(filepath_in)

    way_id = 10000
    for each_seg in points_all_segs:
        print('Wait for writing XML ...')
        each_seg, points_stack = setIntersection(each_seg, points_stack, way_id, config.dis_delta)
        points_all = np.vstack((points_all, each_seg))
        writeXML(each_seg, way_id, config)

        way_id = way_id + 10000

    print('Done! Set %d junction points.' % points_stack.shape[0])

    saveData(points_all, points_stack, config.file_points, config.file_junctions)
    print('Data <%s> and <%s> have saved.' % (config.file_points, config.file_junctions))


if __name__ == '__main__':

    print(sys.version)
    home = os.path.expanduser('~')
    dir_path = os.path.join(home, 'Desktop', 'Example')

    ws_dir = dir_path
    ws_dir_temp_seg = os.path.join(ws_dir, 'temp_seg')
    ws_dir_seg = os.path.join(ws_dir, 'seg')
    file_config = os.path.join(ws_dir, 'config.txt')

    ws_dirs = [ws_dir, ws_dir_temp_seg, ws_dir_seg]
    genRoad(ws_dirs)
