#!/usr/bin/env python

# Picks out the biggest rectangular area for a set of images and crops them out.
# Useful for artbook scans with a white border surrounding a single artwork.

import sys
import os
import os.path
import tqdm
import glob

import cv2
import numpy as np

import glob
import os


dir = sys.argv[1]
if not os.path.isdir(dir):
    print("Invalid directory")
    exit(1)

window_name = "crop"
debug_mode = False


def get_image_width_height(image):
    image_width = image.shape[1]  # current image's width
    image_height = image.shape[0]  # current image's height
    return image_width, image_height


def calculate_scaled_dimension(scale, image):
    image_width, image_height = get_image_width_height(image)
    ratio_of_new_with_to_old = scale / image_width
    dimension = (scale, int(image_height * ratio_of_new_with_to_old))
    return dimension


def rotate_image(image, degree=180):
    image_width, image_height = get_image_width_height(image)
    center = (image_width / 2, image_height / 2)
    M = cv2.getRotationMatrix2D(center, degree, 1.0)
    image_rotated = cv2.warpAffine(image, M, (image_width, image_height))
    return image_rotated


def scale_image(image, size):
    image_resized_scaled = cv2.resize(
        image,
        calculate_scaled_dimension(
            size,
            image
        ),
        interpolation=cv2.INTER_AREA
    )
    return image_resized_scaled

def detect_box(image, cropIt=True):
    # Transform colorspace to YUV
    image_yuv = cv2.cvtColor(image, cv2.COLOR_BGR2YUV)
    image_y = np.zeros(image_yuv.shape[0:2], np.uint8)
    image_y[:, :] = image_yuv[:, :, 0]

    # Blur to filter high frequency noises
    image_blurred = cv2.GaussianBlur(image_y, (5, 5), 0)
    if debug_mode:  show_image(image_blurred, window_name)

    # Apply canny edge-detector
    edges = cv2.Canny(image_blurred, 240, 250, apertureSize=5)
    if debug_mode: show_image(edges, window_name)

    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (7, 7))
    edges = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, kernel)
    if debug_mode:
        show_image(edges, window_name)

    # Find extrem outer contours
    contours, hierarchy = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if debug_mode:
         image2 = image.copy()
         #                                      b  g   r
         cv2.drawContours(image2, contours, -1, (0, 255, 0), 3)
         show_image(image2, window_name)
         del image2

    new_contours = []
    for i, cnt in enumerate(contours):
        # Check if it is an external contour and its area is more than 100
        if hierarchy[0,i,3] == -1 and cv2.contourArea(cnt) > 100:
            # # approximate the contour
            # peri = cv2.arcLength(cnt, True)
            # approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

            # # if the approximated contour has four points, then assume that the
            # # contour is a book -- a book is a rectangle and thus has four vertices
            # if len(approx) == 4:
            x,y,w,h = cv2.boundingRect(cnt)
            new_contours.append(cnt)

    if debug_mode:
         image2 = image.copy()
         #                                          b  g   r
         cv2.drawContours(image2, new_contours, -1, (0, 0, 255), 3)
         show_image(image2, window_name)
         del image2

    # Get overall bounding box
    best_box = [-1, -1, -1, -1]
    size = 0
    for c in new_contours:
        x, y, w, h = cv2.boundingRect(c)
        new_size = cv2.contourArea(c)
        if size < new_size:
            size = new_size
            best_box = [x, y, x + w, y + h]

    if debug_mode:
        cv2.rectangle(image, (best_box[0], best_box[1]), (best_box[2], best_box[3]), (255, 0, 0), 1)
        show_image(image, window_name)

    if cropIt:
        image = image[best_box[1]:best_box[3], best_box[0]:best_box[2]]
        if debug_mode: show_image(image, window_name)

    return image


def show_image(image, window_name):
    # Show image
    p = 1
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.imshow(window_name, image)
    image_width, image_height = get_image_width_height(image)
    cv2.resizeWindow(window_name, image_width, image_height)

    # Wait before closing
    cv2.waitKey(0)
    cv2.destroyAllWindows()

def cut_of_top(image, pixel):
    image_width, image_height = get_image_width_height(image)

    # startY, endY, startX, endX coordinates
    new_y = 0+pixel
    image = image[new_y:image_height, 0:image_width]
    return image

def cut_of_bottom(image, pixel):
    image_width, image_height = get_image_width_height(image)

    # startY, endY, startX, endX coordinates
    new_height = image_height-pixel
    image = image[0:new_height, 0:image_width]
    return image


IMAGE_EXTS = [".png", ".jpg", ".jpeg", ".gif", ".webp", ".avif"]

for ext in IMAGE_EXTS:
    for img in tqdm.tqdm(list(glob.iglob(os.path.join(dir, f"**{ext}"), recursive=True))):
        file_name_ext = os.path.basename(img)
        file_name, file_extension = os.path.splitext(file_name_ext)
        if file_name.endswith(".cropped"):
            continue

        image = cv2.imread(img)

        #image = rotate_image(image)
        #image = cut_of_bottom(image, 1000)

        #image = scale_image(image, size_max_image)
        if debug_mode: show_image(image, window_name)

        image = detect_box(image, True)

        path_out = os.path.join(os.path.dirname(img), "out")
        # Create out path
        if not os.path.exists(path_out):
            os.makedirs(path_out)

        # Build output file path
        file_path = os.path.join(path_out, file_name + '.cropped' + file_extension)

        # Write out file
        cv2.imwrite(file_path, image)
