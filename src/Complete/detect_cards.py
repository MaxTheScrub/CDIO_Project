import cv2 as cv
import argparse
import numpy as np
import sys
import time
from classes import *
from testing import *
from prediction import *
from threading import Thread
if sys.version_info[0] == 2:
    import Queue as queue
else:
    import queue

from common import *
from tf_text_graph_common import readTextMessage
from tf_text_graph_ssd import createSSDGraph
from tf_text_graph_faster_rcnn import createFasterRCNNGraph

# for sorting cards in tableau
from operator import attrgetter

backends = (cv.dnn.DNN_BACKEND_DEFAULT, cv.dnn.DNN_BACKEND_HALIDE, cv.dnn.DNN_BACKEND_INFERENCE_ENGINE, cv.dnn.DNN_BACKEND_OPENCV)
targets = (cv.dnn.DNN_TARGET_CPU, cv.dnn.DNN_TARGET_OPENCL, cv.dnn.DNN_TARGET_OPENCL_FP16, cv.dnn.DNN_TARGET_MYRIAD)

parser = argparse.ArgumentParser(add_help=False)
parser.add_argument('--zoo', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models.yml'),
                    help='An optional path to file with preprocessing parameters.')
parser.add_argument('--input', help='Path to input image or video file. Skip this argument to capture frames from a camera.')
parser.add_argument('--out_tf_graph', default='graph.pbtxt',
                    help='For models from TensorFlow Object Detection API, you may '
                         'pass a .config file which was used for training through --config '
                         'argument. This way an additional .pbtxt file with TensorFlow graph will be created.')
parser.add_argument('--framework', choices=['caffe', 'tensorflow', 'torch', 'darknet', 'dldt'],
                    help='Optional name of an origin framework of the model. '
                         'Detect it automatically if it does not set.')
parser.add_argument('--thr', type=float, default=0.5, help='Confidence threshold')
parser.add_argument('--nms', type=float, default=0.4, help='Non-maximum suppression threshold')
parser.add_argument('--backend', choices=backends, default=cv.dnn.DNN_BACKEND_DEFAULT, type=int,
                    help="Choose one of computation backends: "
                         "%d: automatically (by default), "
                         "%d: Halide language (http://halide-lang.org/), "
                         "%d: Intel's Deep Learning Inference Engine (https://software.intel.com/openvino-toolkit), "
                         "%d: OpenCV implementation" % backends)
parser.add_argument('--target', choices=targets, default=cv.dnn.DNN_TARGET_CPU, type=int,
                    help='Choose one of target computation devices: '
                         '%d: CPU target (by default), '
                         '%d: OpenCL, '
                         '%d: OpenCL fp16 (half-float precision), '
                         '%d: VPU' % targets)
parser.add_argument('--async', type=int, default=0,
                    dest='asyncN',
                    help='Number of asynchronous forwards at the same time. '
                         'Choose 0 for synchronous mode')
args, _ = parser.parse_known_args()
add_preproc_args(args.zoo, parser, 'object_detection')
parser = argparse.ArgumentParser(parents=[parser],
                                 description='Use this script to run object detection deep learning networks using OpenCV.',
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
args = parser.parse_args()

args.model = findFile(args.model)
args.config = findFile(args.config)
args.classes = findFile(args.classes)

# Card variables
CARD_WIDTH = 280
CARD_HEIGHT = 350
DUPLICATE_THRESHOLD = 50
NUMBER_ARRAY = ("FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH")
STOCKPILE_THRESHOLD = 500


def setupGameComputerVision(game):
    game.playingCards = []
    game.tableauPiles = []
    game.foundationPiles = []
    for pileNumber in range(1, 8):
        currentPile = TableauPile(pileNumber)
        game.tableauPiles.append(currentPile)
    for suit in Suit:
        newFoundationPile = FoundationPile(suit)
        newFoundationPile.nextCard = Value.ACE
        game.foundationPiles.append(newFoundationPile)

game = Game()

setupGameComputerVision(game) #Sauce?
#for tableapile in range(1, 8):
 #   game.tableauPiles.append(TableauPile(tableapile))
#game.tableauPiles = [TableauPile(1),TableauPile(2),TableauPile(3),TableauPile(4),TableauPile(5),TableauPile(6),TableauPile(7)]
#game.foundationPiles = (FoundationPile(None),FoundationPile(None),FoundationPile(None),FoundationPile(None))

# If config specified, try to load it as TensorFlow Object Detection API's pipeline.
config = readTextMessage(args.config)
if 'model' in config:
    print('TensorFlow Object Detection API config detected')
    if 'ssd' in config['model'][0]:
        print('Preparing text graph representation for SSD model: ' + args.out_tf_graph)
        createSSDGraph(args.model, args.config, args.out_tf_graph)
        args.config = args.out_tf_graph
    elif 'faster_rcnn' in config['model'][0]:
        print('Preparing text graph representation for Faster-RCNN model: ' + args.out_tf_graph)
        createFasterRCNNGraph(args.model, args.config, args.out_tf_graph)
        args.config = args.out_tf_graph


# Load names of classes
classes = None
if args.classes:
    with open(args.classes, 'rt') as f:
        classes = f.read().rstrip('\n').split('\n')

# Load a network
net = cv.dnn.readNet(cv.samples.findFile(args.model), cv.samples.findFile(args.config), args.framework)
net.setPreferableBackend(args.backend)
net.setPreferableTarget(args.target)
outNames = net.getUnconnectedOutLayersNames()

confThreshold = args.thr
nmsThreshold = args.nms

def ID_to_card(subject, leftPos, topPos):
    # Convert a cardID to a card object
    #Attributes for a new card is initialized.
    suit = None
    color = None
    pile = 0
    value = None
    visible = Visible.TRUE
    left = leftPos
    top = topPos
    #Determine suit and color based on offset defined in cards.names.
    if subject < 13:
        suit = Suit.H
        color = Color.RED   
        value = (subject - 13)*(-1)
    elif subject > 12 and subject < 26:
        suit = Suit.D
        color = Color.RED
        value = (subject - 26)*(-1)
    elif subject > 25 and subject < 39:
        suit = Suit.C
        color = Color.BLACK
        value = (subject - 39)*(-1)
    elif subject > 38:
        suit = Suit.S
        color = Color.BLACK
        value = (subject - 52)*(-1)

    card = create_card(value, suit, pile, color, left, top) 
    return card

def check_duplicate_BJH_BJH(element, elements, height):
    count = 0
    for duplicate in elements: 
        if element.suit == duplicate.suit:
            if element.value == duplicate.value:
                count += 1
                if count == 2:
                    if duplicate.top - (element.top+height) > DUPLICATE_THRESHOLD or duplicate.top - (element.top+height) < (-DUPLICATE_THRESHOLD):
                        return True
    return False

def check_duplicate_BJH(element, elements, height):
    for duplicate in elements: 
        if duplicate.to_string() == element.to_string():
            if duplicate.top - element.top+height > DUPLICATE_THRESHOLD or duplicate.top - element.top+height < (-DUPLICATE_THRESHOLD):
                #print("Duplicate found for: " + duplicate.to_string() + " distance between duplicate: " + str(duplicate.top - element.top+height))
                count = 1
            return True
    return False    

def check_stockpile():
    stockpileFrame = frame[0:CARD_HEIGHT,0:CARD_WIDTH]
    stockpileFrameGrey = cv.cvtColor(stockpileFrame, cv.COLOR_BGR2GRAY)
    _, thresh = cv.threshold(stockpileFrameGrey, 127, 255, 0)
    contours, _ = cv.findContours(thresh, cv.RETR_TREE, cv.CHAIN_APPROX_SIMPLE)
    
    #print(len(contours))
    #cv.drawContours(stockpileFrame, contours, -1, (255,0,0), 3)
    #cv.imshow(winName, stockpileFrame)
    
    if len(contours) > STOCKPILE_THRESHOLD:
        #print("Stockpile is not empty")
        return False
    else:
        #print("Stockpile is empty")    
        return True

def check_win():
    if check_stockpile():
        if len(game.stock.cards) == 0:
            return True
    else:
        return False

def check_duplicate(element, elements, height):
    count = 0

    #if len(elements) == 0: # If pile is empty, there is no duplicate. Return True
   #     return True

    for duplicate in elements:
        if element.value == duplicate.value and element.suit == duplicate.suit:
            count = count + 1
            #print(str(len(elements)))
            #print("Count: " + str(count) + str(duplicate.value) + str(duplicate.suit))
            if count == 2:
                #print("count er 2")
                if duplicate.top - element.top+height > DUPLICATE_THRESHOLD or duplicate.top - element.top+height < (-DUPLICATE_THRESHOLD):
                    print("Duplicate found for: " + duplicate.to_string() + " distance between duplicate: " + str(duplicate.top - element.top+height))
                    return True
    
    #print("den falske luder") 
    return False

#def check_tableau()

detectedCards = [] # card objects with no pile
detectedTableau = [] # Fuck 3 ugers og sut en ged

def postprocess(frame, outs, game):
    frameHeight = frame.shape[0]
    frameWidth = frame.shape[1]

    def drawPred(classId, conf, left, top, right, bottom):
        # Draw a bounding box.
        cv.rectangle(frame, (left, top), (right, bottom), (0, 255, 0))

        label = '%.2f' % conf

        # Print a label of class.
        if classes:
            assert(classId < len(classes))
            label = '%s: %s' % (classes[classId], label)

        labelSize, baseLine = cv.getTextSize(label, cv.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        top = max(top, labelSize[1])
        cv.rectangle(frame, (left, top - labelSize[1]), (left + labelSize[0], top + baseLine), (255, 255, 255), cv.FILLED)
        cv.putText(frame, label, (left, top), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0))

    layerNames = net.getLayerNames()
    lastLayerId = net.getLayerId(layerNames[-1])
    lastLayer = net.getLayer(lastLayerId)

    classIds = []
    confidences = []
    boxes = []
    if lastLayer.type == 'DetectionOutput':
        # Network produces output blob with a shape 1x1xNx7 where N is a number of
        # detections and an every detection is a vector of values
        # [batchId, classId, confidence, left, top, right, bottom]
        for out in outs:
            for detection in out[0, 0]:
                confidence = detection[2]
                if confidence > confThreshold:
                    left = int(detection[3])
                    top = int(detection[4])
                    right = int(detection[5])
                    bottom = int(detection[6])
                    width = right - left + 1
                    height = bottom - top + 1
                    if width <= 2 or height <= 2:
                        left = int(detection[3] * frameWidth)
                        top = int(detection[4] * frameHeight)
                        right = int(detection[5] * frameWidth)
                        bottom = int(detection[6] * frameHeight)
                        width = right - left + 1
                        height = bottom - top + 1
                    classIds.append(int(detection[1]) - 1)  # Skip background label
                    confidences.append(float(confidence))
                    boxes.append([left, top, width, height])

    elif lastLayer.type == 'Region':
        # Network produces output blob with a shape NxC where N is a number of
        # detected objects and C is a number of classes + 4 where the first 4
        # numbers are [center_x, center_y, width, height]
        for out in outs:
            for detection in out:
                scores = detection[5:]
                classId = np.argmax(scores)
                confidence = scores[classId]
                if confidence > confThreshold:
                    center_x = int(detection[0] * frameWidth)
                    center_y = int(detection[1] * frameHeight)
                    width = int(detection[2] * frameWidth)
                    height = int(detection[3] * frameHeight)
                    left = int(center_x - width / 2)
                    top = int(center_y - height / 2)
                    classIds.append(classId)
                    confidences.append(float(confidence))
                    boxes.append([left, top, width, height])
                
    else:
        print('Unknown output layer type: ' + lastLayer.type)
        exit()

    # NMS is used inside Region layer only on DNN_BACKEND_OPENCV for another backends we need NMS in sample
    # or NMS is required if number of outputs > 1
    if len(outNames) > 1 or lastLayer.type == 'Region' and args.backend != cv.dnn.DNN_BACKEND_OPENCV:
        indices = []
        classIds = np.array(classIds)
        boxes = np.array(boxes)
        confidences = np.array(confidences)
        unique_classes = set(classIds)
        for cl in unique_classes:
            class_indices = np.where(classIds == cl)[0]
            conf = confidences[class_indices]
            box  = boxes[class_indices].tolist()
            nms_indices = cv.dnn.NMSBoxes(box, conf, confThreshold, nmsThreshold)
            nms_indices = nms_indices[:, 0] if len(nms_indices) else []
            indices.extend(class_indices[nms_indices])
    else:
        indices = np.arange(0, len(classIds))


    
    #print("Detected cards reset")
    for i in indices:
        box = boxes[i]
        left = box[0]
        top = box[1]
        width = box[2]
        height = box[3]
        drawPred(classIds[i], confidences[i], left, top, left + width, top + height)
        card = None

        if confidences[i] > 0.95: # Filter out moving cards. Is not entirely reliable at 28k iterations (or 90k)
            
            #Create card objects
            card = ID_to_card(classIds[i], left, top)
            if not detectedCards:
                    detectedCards.append(card)
            else:
                for oldCard in detectedCards:
                    if card.value.value == oldCard.value.value and card.suit == oldCard.suit:
                        oldCard.top = card.top
                        oldCard.left = card.left
                        card = oldCard
                        detectedTableau = oldCard.pile
                        break
                    else:
                        detectedCards.append(card)

            #print("Appended card: " + str(card.value) + " " + str(card.suit))
            #heckDupValue = check_duplicate_BJH(card, detectedCards, height)
            if check_duplicate_BJH(card, detectedCards, height): # Only add card if all of the tags are visible on one pile
                
                if card.top < CARD_HEIGHT: # The top cards

                    # Add the stockpile
                    if card.left < CARD_WIDTH*2 and card.left > CARD_WIDTH*1:   
                        if not check_duplicate_BJH(card, game.stock.cards , height):
                            if not check_stockpile():
                                game.stock.cards.append(card)
                                game.stock.frontCard = card
                                print(card.to_string() + " added to stock. Keep adding cards. Confidence " + str(confidences[i]))
                                print("Cards in stock: ")
                                for element in game.stock.cards: 
                                    print(element.to_string())
                            else:
                                print("Stockpile has been loaded. Start playing.")
                    
                    # Add foundation pile
                    elif card.left > CARD_WIDTH*2:
                        foundationNumber = 0
                        placementNumber = 3
                        for foundationPile in game.foundationPiles:
                            if left > CARD_WIDTH*placementNumber and left < CARD_WIDTH*(placementNumber+1):
                                if not check_duplicate_BJH(card, foundationPile.cards, height):
                                #if check_duplicate(card, foundationPile, height):
                                    #foundationPile.cards.append(card)
                                    #foundationPile.frontCard = card

                                    print("Test af foundation")
                                    print("Card: " + card.to_string() + "Card pile: " + str(card.pile.number))
                                    start_add_to_goal(card, card.pile, game)
                                    #elif card.pile == Stock:
                                        
                                    print(card.to_string() + " added to " + NUMBER_ARRAY[foundationNumber] + " foundation pile. Confidence " + str(confidences[i]))
                                    print("Cards in foundation pile: " + str(foundationNumber))

                                    for element in foundationPile.cards: 
                                        print(element.to_string())
                            foundationNumber += 1
                            placementNumber += 1
                    
                # The tableau piles
                elif card.top > CARD_HEIGHT:
                    tableauNumber = 0                
                    for tableauPile in game.tableauPiles:
                        if left > CARD_WIDTH*tableauNumber and left < CARD_WIDTH*(tableauNumber+1): # Add card to second foundation pile                           
                            if not check_duplicate_BJH(card, tableauPile.cards, height):
                                if tableauPile.frontCard == None:
                                    
                                    tableauPile.cards.append(card)
                                    tableauPile.frontCard = card
                                    card.pile = tableauPile

                                elif card.value.value - tableauPile.frontCard.value.value == -1 and card.color != tableauPile.frontCard.color:

                                    tableauPile.cards.append(card)
                                    tableauPile.frontCard = card

                                    if card.to_string() != card.pile.frontCard.to_string():
                                        for element in card.pile.cards:
                                            remove_from_tableau_pile(element, card.pile)
                                    else:
                                        remove_from_tableau_pile(card, card.pile)

                                    card.pile = tableauPile

                                elif not(card.value.value - tableauPile.frontCard.value.value == -1 and card.color != tableauPile.frontCard.color):
                                    print("Cards do not match! " + card.to_string() + " | " + tableauPile.frontCard.to_string())
                                    
                        tableauNumber += 1
    
    
                
# Process inputs
winName = 'Deep learning object detection in OpenCV'
cv.namedWindow(winName, cv.WINDOW_NORMAL)

def callback(pos):
    global confThreshold
    confThreshold = pos / 100.0

cv.createTrackbar('Confidence threshold, %', winName, int(confThreshold * 100), 99, callback)

#cap = cv.VideoCapture('http://192.168.31.97:8080/video')
cap = cv.VideoCapture(cv.samples.findFileOrKeep(args.input) if args.input else 0)

class QueueFPS(queue.Queue):
    def __init__(self):
        queue.Queue.__init__(self)
        self.startTime = 0
        self.counter = 0

    def put(self, v):
        queue.Queue.put(self, v)
        self.counter += 1
        if self.counter == 1:
            self.startTime = time.time()

    def getFPS(self):
        return self.counter / (time.time() - self.startTime)


process = True

#
# Frames capturing thread
#
framesQueue = QueueFPS()
def framesThreadBody():
    global framesQueue, process

    while process:
        hasFrame, frame = cap.read()
        if not hasFrame:
            break
        framesQueue.put(frame)

#
# Frames processing thread
#
processedFramesQueue = queue.Queue()
predictionsQueue = QueueFPS()
def processingThreadBody():
    global processedFramesQueue, predictionsQueue, args, process

    futureOutputs = []
    while process:
        # Get a next frame
        frame = None
        try:
            frame = framesQueue.get_nowait()

            if args.asyncN:
                if len(futureOutputs) == args.asyncN:
                    frame = None  # Skip the frame
            else:
                framesQueue.queue.clear()  # Skip the rest of frames
        except queue.Empty:
            pass


        if not frame is None:
            frameHeight = frame.shape[0]
            frameWidth = frame.shape[1]

            # Create a 4D blob from a frame.
            inpWidth = args.width if args.width else frameWidth
            inpHeight = args.height if args.height else frameHeight
            blob = cv.dnn.blobFromImage(frame, size=(inpWidth, inpHeight), swapRB=args.rgb, ddepth=cv.CV_8U)
            processedFramesQueue.put(frame)

            # Run a model
            net.setInput(blob, scalefactor=args.scale, mean=args.mean)
            if net.getLayer(0).outputNameToIndex('im_info') != -1:  # Faster-RCNN or R-FCN
                frame = cv.resize(frame, (inpWidth, inpHeight))
                net.setInput(np.array([[inpHeight, inpWidth, 1.6]], dtype=np.float32), 'im_info')

            if args.asyncN:
                futureOutputs.append(net.forwardAsync())
            else:
                outs = net.forward(outNames)
                predictionsQueue.put(np.copy(outs))

        while futureOutputs and futureOutputs[0].wait_for(0):
            out = futureOutputs[0].get()
            predictionsQueue.put(np.copy([out]))

            del futureOutputs[0]


framesThread = Thread(target=framesThreadBody)
framesThread.start()

processingThread = Thread(target=processingThreadBody)
processingThread.start()

#
# Postprocessing and rendering loop
#
while cv.waitKey(1) < 0:
    try:
        # Request prediction first because they put after frames
        outs = predictionsQueue.get_nowait()
        frame = processedFramesQueue.get_nowait()

        postprocess(frame, outs, game)

        # Put efficiency information.
        if predictionsQueue.counter > 1:
            label = 'Camera: %.2f FPS' % (framesQueue.getFPS())
            cv.putText(frame, label, (0, 15), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0))

            label = 'Network: %.2f FPS' % (predictionsQueue.getFPS())
            cv.putText(frame, label, (0, 30), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0))

            label = 'Skipped frames: %d' % (framesQueue.counter - predictionsQueue.counter)
            cv.putText(frame, label, (0, 45), cv.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0))

        #Top line
        cv.line(frame,(0,CARD_HEIGHT),(1920,CARD_HEIGHT),(0,0,255),thickness=2)

        for line in range(7):
            cv.line(frame,(CARD_WIDTH*line,0),(CARD_WIDTH*line,1080),(0,0,255),thickness=2)


        cv.imshow(winName, frame)
        give_advice(game)

    except queue.Empty:
        pass

process = False
framesThread.join()
processingThread.join()
