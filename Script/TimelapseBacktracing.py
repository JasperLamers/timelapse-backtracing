#######################################################################################
# Author: Jasper Lamers
# Affiliation: Plant Physiology, Wageningen University
# Version 3 (Feb 2020)
#######################################################################################

global directory
directory = ""

from scipy import ndimage
import numpy as np
import cv2
import os
from bs4 import BeautifulSoup
import re
from xml.etree.ElementTree import Element, SubElement
from xml.etree import ElementTree
from xml.dom import minidom
import shutil

#ARBITRARY THRESHOLD OF 99% TO REMOVE NOISE
def main():
    #SET ALL DIRECTORIES AND MAKE OUTPUT FOLDER
    #READ RSML
    all_files = [(path, name) for path, subdirs, files in os.walk(directory) for name in files]
    unique_folders = sorted(list(set([item[0] for item in all_files if "Orginal_RSML" not in item[0] and "Result_images" not in item[0]])))
    for folder in unique_folders:
        folder_files = [item for item in all_files if item[0] == folder]
        image_files = sorted([item for item in folder_files if item[1].endswith(".tiff")])
        rsml_files = sorted([item for item in folder_files if item[1].endswith(".rsml")])

        #CREATE BACKUP OF ORIGINAL RSMLS
        if not os.path.exists(os.path.join(folder, "Result_images")):
            os.makedirs(os.path.join(folder, "Result_images"))

        if not os.path.exists(os.path.join(folder, "Orginal_RSML")):
            os.makedirs(os.path.join(folder, "Orginal_RSML"))
            for item in rsml_files:
                shutil.copy2(os.path.join(*item), os.path.join(item[0], "Orginal_RSML", item[1]))

        parts = transfer_splitter(image_files, rsml_files)
        for rsml_index, images_indeces in enumerate(parts):
            files = [os.path.join(*item) for item in image_files[images_indeces[0]:1+images_indeces[1]]]
            RootData = RSML_reader(os.path.splitext(os.path.join(*image_files[images_indeces[1]]))[0] + ".rsml")
            RootData = sorted(RootData, key=lambda item: item[0][0][0])

            #LOOP OVER FILES
            for file in files:
                print(file)

                #open image and copy to write final output (as control)
                image_read = cv2.imread(os.path.join(file))
                # from PIL import Image, ImageDraw
                # im = Image.fromarray(np.copy(image_read))
                # draw = ImageDraw.Draw(im)

                #Crop roots with diameter (d), perform edgde detection (sobel)
                #and place crop back in (empty) in segmentation_image

                segmentation_image = np.zeros_like(image_read)
                d = 80
                for root in RootData:
                    x = [item[0][0] for item in root]
                    y = [item[0][1] for item in root]
                    x_min = min(x) - d
                    x_max = max(x) + d
                    y_min = min(y) - d
                    y_max = max(y) + d

                    cropped = np.copy(image_read[y_min:y_max,x_min:x_max])
                    cropped = cv2.medianBlur(cropped, 5)
                    cropped = cropped.astype(float)

                    dx = ndimage.sobel(cropped, 0)  # horizontal derivative
                    dy = ndimage.sobel(cropped, 1)  # vertical derivative
                    edges = np.hypot(dx, dy).astype(np.uint8)  # magnitude
                    segmentation_image[y_min:y_max,x_min:x_max] = edges

                #blur edge detection and make a 8bit grayscale
                segmentation_image = cv2.GaussianBlur(segmentation_image,(9,9),0)
                segmentation_image = cv2.cvtColor(segmentation_image, cv2.COLOR_BGR2GRAY)

                blank = np.zeros_like(segmentation_image)
                threshold = [segmentation_image < 30]
                segmentation_image[tuple(threshold)] = blank[tuple(threshold)]

                #Invert and threshold (adaptive) image
                segmentation_image = np.invert(segmentation_image)
                segmentation_image = cv2.adaptiveThreshold(segmentation_image, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 25, 2)


                #if root point in segmented root, place in main root
                main_root_list = []
                for root in RootData:
                    main_root = [item for item in root if segmentation_image[item[0][1],item[0][0]] == 0]
                    # draw.line(tuple([item[0] for item in main_root]), (255,0,0), 1)
                    # for item in main_root:
                    #         draw.point(item[0], (0,255,0))
                    main_root_list.append(main_root)

                # del draw
                # im.save(os.path.join(folder, "Result_images", file.split("/")[-1] + ".png"))
                XML_writer(main_root_list, file)

def PathItems(input_path): #Script to find all tiff files in directory of .py file
    return [item for item in os.listdir(input_path) if item.endswith("tiff")]

def transfer_splitter(image_files, rsml_files):
    image_filesNoExt = [os.path.splitext(os.path.join(*item))[0] for item in image_files]
    rsml_filesNoExt = [os.path.splitext(os.path.join(*item))[0] for item in rsml_files]

    intersect_index = [-1] + [image_filesNoExt.index(value) for value in image_filesNoExt if value in rsml_filesNoExt]
    intersect_index = [[intersect_index[i-1]+1,intersect_index[i]] for i in range(1,len(intersect_index)) if intersect_index[i-1]+1 != intersect_index[i]]
    return intersect_index

#READ ONLY THE LAST RSML FILE
def RSML_reader(RSML_file):
    last_file_rsml = open(RSML_file, "r")
    TotalRSML = BeautifulSoup(last_file_rsml, 'html.parser')

    #FIND ALL ROOTS AND PUT IN LIST
    if len(TotalRSML.findAll("root")) > 0:
        root_list = [str(m) for m in TotalRSML.findAll("root")]

    root_list_coordinates = []
    for root in root_list:
        RootRSML = BeautifulSoup(root, 'html.parser')
        coordinates = str(RootRSML.findAll("polyline"))
        coordinates = BeautifulSoup(coordinates, 'html.parser')
        points = coordinates.findAll("point")
        reg = re.compile('"(.*?)"') #compiler; . = anychar, * = any length, ? = small as possible. Everything in between "" (brackets for in between)
        point_list = []
        for item in points:
            point = reg.findall(str(item))
            point = (int(round(float(point[0]))), int(round(float(point[1]))))
            point_list.append(point)

        diameter_list = []
        diameter = RootRSML.find("function", {"name":"diameter"})
        samples = diameter.findAll("sample")
        reg = re.compile('>(.*?)<')
        for item in samples:
            diameter = reg.findall(str(item))
            diameter_list.append(int(round(float(diameter[0])/2))+1)

        root_list_coordinates.append(tuple(zip(point_list,diameter_list)))
    return root_list_coordinates

#Writing the rsml file
def XML_writer(total_list, file_name):
    root = Element('rsml')
    root.set('xmlns:po', 'http://www.plantontology.org/xml-dtd/po.dtd')
    metadata = SubElement(root, 'metadata')

    version = SubElement(metadata, 'version')
    version.text = '1'

    unit = SubElement(metadata, 'unit')
    unit.text = 'inch'

    unit = SubElement(metadata, 'resolution')
    unit.text = '300.0'

    unit = SubElement(metadata, 'last-modified')
    unit.text = 'today'

    unit = SubElement(metadata, 'software')
    unit.text = 'smartroot'

    unit = SubElement(metadata, 'user')
    unit.text = 'globet'

    unit = SubElement(metadata, 'file-key')
    unit.text = 'myimage'

    x = SubElement(metadata, 'property-definitions')

    list = [['diameter', 'float', 'cm'], ['length', 'float', 'cm'], ['pixel', 'float', 'none'],
            ['angle', 'float', 'degree'], ['insertion', 'float', 'cm'], ['lauz', 'float', 'cm'],
            ['lbuz', 'float', 'cm'], ['node-orientation', 'float', 'radian']]
    for i in range(len(list)):
        entry = SubElement(x, 'property-definition')
        label = SubElement(entry, 'label')
        label.text = list[i][0]
        label = SubElement(entry, 'type')
        label.text = list[i][1]
        label = SubElement(entry, 'unit')
        label.text = list[i][2]

    image = SubElement(metadata, 'image')
    label = SubElement(image, 'captured')
    label.text = 'today'
    label = SubElement(image, 'label')
    label.text = file_name

    scene = SubElement(root, 'scene')
    plant = SubElement(scene, 'plant')

    reg = re.compile('[0-9]+')
    plate_no = reg.findall(file_name)[-1]

    count = 0
    for roots in sorted(total_list):
        main_root = [item[0] for item in roots]
        ID_string = "Pos{}_Root{}".format(plate_no,count)
        label_string = 'root_' + str(count)

        main_root_xml = SubElement(plant, 'root')
        main_root_xml.set('ID', ID_string)
        main_root_xml.set('label', label_string)
        main_root_xml.set('po:accession', 'PO:0009005')

        geometry = SubElement(main_root_xml, 'geometry')
        polyline = SubElement(geometry, 'polyline')

        for i in range(0, len(main_root)):
            item = main_root[i]
            root2 = SubElement(polyline, 'point')
            root2.set('x', str(item[0]))
            root2.set('y', str(item[1]))

        functions = SubElement(main_root_xml, 'functions')
        function1 = SubElement(functions, 'function')
        function1.set('name', 'diameter')
        function1.set('domain', 'polyline')

        diameter_list = [item[1] for item in roots]
        for i in range(0, len(diameter_list)):
            diameter = SubElement(function1, 'sample')
            diameter.text = str(diameter_list[i])

        #annotations = SubElement(root1, 'annotations')

        count+= 1

    prettify(root,file_name)

#Creating a structured rsml
def prettify(elem,file_name):
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)

    reparsed = reparsed.toprettyxml(indent='  ')
    f = open(os.path.join(file_name[:-5]+'.rsml'), 'w')
    f.write(reparsed)
    f.close()

if __name__ == "__main__":
    main()
