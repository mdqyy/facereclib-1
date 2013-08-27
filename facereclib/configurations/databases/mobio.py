#!/usr/bin/env python

import xbob.db.mobio
import facereclib

database = facereclib.databases.DatabaseXBobZT(
    database = xbob.db.mobio.Database(),
    name = "mobio",
    original_directory = "/idiap/group/biometric/databases/mobio/still/images/selected-images/",
    original_extension = ".jpg",
    annotation_directory = "/idiap/group/biometric/annotations/mobio/",
    annotation_type = 'eyecenter',
    protocol = 'male'
)
