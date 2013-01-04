#!/usr/bin/env python

import xbob.db.banca
import facereclib

database = facereclib.databases.DatabaseXBobZT(
    database = xbob.db.banca.Database(),
    name = "banca",
    image_directory = "/idiap/group/biometric/databases/banca/english/images/images/",
    image_extension = ".ppm",
    annotation_directory = "/idiap/group/biometric/annotations/banca/english/images/annotations/",
    annotation_type = 'eyecenter',
    protocol = 'P'
)