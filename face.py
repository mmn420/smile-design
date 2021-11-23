from numpy.lib.type_check import imag
import message as Message
import helper as Helper
import os
import io
import cv2
import time
from google.cloud import vision
from PIL import Image, ImageFilter, ImageDraw, ImageQt

import numpy as np

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"setup/config.json"
mouthImagePath = "cached/mouth.png"
midlineImagePath = "cached/midline.png"
teethColorImagePath = "cached/teethColor.png"


def mouthDetection(self, imagePath):
    client = vision.ImageAnnotatorClient()

    with io.open(imagePath, "rb") as image_file:
        content = image_file.read()

    image = vision.Image(content=content)
    response = client.face_detection(image=image)
    face = response.face_annotations[0]

    upper_lip_index = 8
    mouth_left_index = 10
    lower_lip_index = 9
    mouth_right_index = 11
    eyes_center_index = 6
    mouth_center_index = 12

    left = face.landmarks[mouth_left_index].position.x
    top = face.landmarks[upper_lip_index].position.y
    right = face.landmarks[mouth_right_index].position.x
    bottom = face.landmarks[lower_lip_index].position.y

    mouth_x = int(face.landmarks[mouth_center_index].position.x)
    mouth_y = int(face.landmarks[mouth_center_index].position.y)
    eyes_x = int(face.landmarks[eyes_center_index].position.x)
    eyes_y = int(face.landmarks[eyes_center_index].position.y)
    ratio = int(right - int(left))

    ratio = int(ratio / 5)

    drawMidline(self, imagePath, mouth_x, mouth_y, eyes_x, eyes_y, ratio)
    mouthCrop(imagePath, (left, top, right, bottom))
    mouthEnhance()


def mouthCrop(imagePath, area):
    image = Image.open(imagePath).crop(area).filter(ImageFilter.SMOOTH_MORE)

    if not os.path.exists("cached"):
        os.makedirs("cached")
    image.save(mouthImagePath)


def mouthEnhance():
    basewidth = 300
    image = Image.open(mouthImagePath)

    wpercent = basewidth / float(image.size[0])
    hsize = int((float(image.size[1]) * float(wpercent)))

    image = image.resize((basewidth, hsize), Image.ANTIALIAS)
    image.save(mouthImagePath)


def drawMidline(self, imagePath, mouth_x, mouth_y, eyes_x, eyes_y, ratio):
    midline = []
    final_midlines = []
    img = cv2.imread(imagePath)
    image = cv2.line(
        img,
        (eyes_x, eyes_y - 150),
        (eyes_x, eyes_y + 400),
        color=(255, 255, 255),
        thickness=1,
    )
    for i in range(-1 * ratio, ratio):
        bgr = np.array(image[mouth_y][mouth_x + i])
        midline.append([bgr[0], mouth_x + i])

    midline.sort()

    for idx, x in enumerate(midline):
        for elem in midline[idx + 1 :]:
            if (elem[1] < x[1] + 10) and (elem[1] > x[1] - 10):
                midline.remove(elem)

    for i in range(0, 3):
        if abs(midline[i][1] - eyes_x) < 5:
            final_midlines.clear()
            Message.info(
                self, "Facial and Dental midline are almost identical. No shift found."
            )
            break
        final_midlines.append(midline[i])

    for x in final_midlines:
        image = cv2.line(
            img,
            (x[1], mouth_y - 200),
            (x[1], mouth_y + 100),
            color=(0, 0, 255),
            thickness=1,
        )
    cv2.imwrite(midlineImagePath, image)


def checkMidline(self):
    Helper.plotImage(self, midlineImagePath)


def checkDiscoloration(self):
    image = cv2.imread(mouthImagePath)

    minBGR = np.array([160, 160, 160])
    maxBGR = np.array([255, 255, 255])

    maskBGR = cv2.inRange(image, minBGR, maxBGR)
    resultBGR = cv2.bitwise_and(image, image, mask=maskBGR)
    # cv2.imshow("Masked Image",resultBGR)
    yellowCount = 0
    blackCount = 0
    count = 0
    cleanArr = []
    rows, cols, _ = image.shape
    for i in range(rows):
        for j in range(cols):
            pixel = resultBGR[i, j]
            if pixel[0] == 0 and pixel[1] == 0 and pixel[2] == 0:
                blackCount += 1
            else:
                cleanArr.append(pixel)
                if pixel[0] < 180:
                    yellowCount += 1
    std = np.std(cleanArr)

    # print(np.mean(cleanArr, axis=0))
    upper = np.mean(cleanArr, axis=0) + std
    # print(upper)
    lower = np.mean(cleanArr, axis=0) - std
    # print(lower)
    index = 0
    for pixel in cleanArr:
        if (
            (pixel[0] < lower[0] or pixel[0] > upper[0])
            and (pixel[1] < lower[1] or pixel[1] > upper[1])
            and (pixel[2] < lower[2] or pixel[2] > upper[2])
        ):
            cleanArr.pop(index)
            count += 1
        index += 1

    # print(np.median(cleanArr, axis=0))
    # print(np.mean(cleanArr, axis=0))
    # print(blackCount, rows*cols)
    mean = np.mean(cleanArr, axis=0)
    createTeethColorImage((int(mean[2]), int(mean[1]), int(mean[0])))
    ratio = yellowCount / ((rows * cols) - blackCount)

    # print(ratio)
    # print(count)
    # print(yellowCount)
    # print(((rows * cols) - blackCount))

    discolorationResult = ""
    if ratio > 0.5:
        discolorationResult = "There is a discoloration"
    else:
        discolorationResult = "There is no discoloration"
    self.colorsWidget.setVisible(True)
    Helper.plotTeethColor(self)
    Message.info(self, discolorationResult)


def createTeethColorImage(rgb):
    w, h = 50, 50
    shape = [(0, 0), (w, h)]
    img = Image.new("RGB", (w, h))

    img1 = ImageDraw.Draw(img)
    img1.rectangle(shape, fill=rgb)
    img.save(teethColorImagePath)
