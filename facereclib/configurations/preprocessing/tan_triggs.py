#!/usr/bin/env python

import facereclib

# copy the settings of the face cropping
import os
execfile(os.path.join(os.path.dirname(__file__), 'face_crop.py'))

# we use the Tan&Triggs algorithm with default parameters
preprocessor = facereclib.preprocessing.TanTriggs(
    cropped_image_size = (CROPPED_IMAGE_HEIGHT, CROPPED_IMAGE_WIDTH),
    cropped_positions = {'leye' : LEFT_EYE_POS, 'reye' : RIGHT_EYE_POS, 'eye' : EYE_POS, 'mouth' : MOUTH_POS}
)

