#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# @author: Manuel Guenther <Manuel.Guenther@idiap.ch>
# @date: Thu Jul 19 17:09:55 CEST 2012
#
# Copyright (C) 2011-2012 Idiap Research Institute, Martigny, Switzerland
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os

def read_annotations(file_name, annotation_type):
  """This function reads the given file of annotations.
  It returns a dictionary with the keypoint name as key and the position (y,x) as value.
  Depending on the annotation type, different file formats are supported."""

  if not file_name:
    return None

  if not os.path.exists(file_name):
    raise IOError("The annotation file '%s' was not found"%file_name)
  f = open(file_name, 'r')

  annotations = {}

  if str(annotation_type) == 'eyecenter':
    # only the eye positions are written, all are in the first row
    line = f.readline()
    positions = line.split()
    assert len(positions) == 4
    annotations['reye'] = (int(positions[1]),int(positions[0]))
    annotations['leye'] = (int(positions[3]),int(positions[2]))

  elif str(annotation_type) == 'multipie':
    # multiple lines, one header line, each line contains one position
    # use position names from:  /idiap/group/biometric/databases/multipie/README.txt
    # see also annotation examples in /idiap/group/biometric/databases/multipie/annotations_examples

    # Left and right is always being seen from the subjects perspective.
    # the abbreviations are:
    # - 'l...', 'r...': left and right object (usually the eyes only)
    # - '...l', '...r': left and part of the object (usually the mouth)
    # - '...t', '...b': top and bottom part of the object (usually the mouth)
    # - '...o', '...i': outer and inner label of the object (eyes and eyebrows)
    # example: 'reyei': label of the *i*nner corner of the *r*ight *eye*
    count = int(f.readline())

    if count == 6:
      # profile annotations
      labels = ['eye', 'nose', 'mouth', 'lipt', 'lipb', 'chin']
    elif count == 8:
      # half profile annotations
      labels = ['reye', 'leye', 'nose', 'mouthr', 'mouthl', 'lipt', 'lipb', 'chin']
    elif count == 16:
      # frontal image annotations
      labels = ['reye', 'leye', 'reyeo', 'reyei', 'leyei', 'leyeo', 'nose', 'mouthr', 'mouthl', 'lipt', 'lipb', 'chin', 'rbrowo', 'rbrowi', 'lbrowi', 'lbrowo']
    elif count == 2:
      labels = ['reye', 'leye']
      print "WARNING! Labels of file '%s' are incomplete"%file_name
    else:
      raise ValueError("The number %d of annotations in file '%s' is not handled."%(count, file_name))

    for i in range(count):
      line = f.readline()
      positions = line.split()
      assert len(positions) == 2
      annotations[labels[i]] = (int(positions[1]),int(positions[0]))

  elif str(annotation_type) == 'scface':
    # multiple lines, no header line, each line contains one position
    i = 0
    for line in f:
      positions = line.split()
      assert len(positions) == 2
      if i == 0:
        # first line is the right eye
        annotations['reye'] = (int(positions[1]),int(positions[0]))
      elif i == 1:
        # second line is the left eye
        annotations['leye'] = (int(positions[1]),int(positions[0]))
      else:
        # enumerate all other annotations
        annotations['key%d'%(i-1)] = (int(positions[1]),int(positions[0]))

  elif str(annotation_type) == 'named':
    # multiple lines, no header line, each line contains annotation and position
    for line in f:
      positions = line.split()
      assert len(positions) == 3
      annotations[positions[0]] = (int(positions[2]),int(positions[1]))

  elif str(annotation_type) == 'cosmin':
    # special file format of cosmin
    count = int(f.readline())
    assert count == 1
    line = f.readline()
    # parse the line...
    parts = line.split()
    # skip the first 7 items: type, pos, id, bounding-box
    for i in range(7,len(parts),3):
      annotations[parts[i]] = (int(parts[i+2]),int(parts[i+1]))

    # HACK! left and right eye positions are exchanged; change them
    if 'leye' in annotations and 'reye' in annotations:
      annotations['leye'], annotations['reye'] = annotations['reye'], annotations['leye']

    # WARNING! The labels of the other annotations might also be exchanged between left and right
    # WARNING! These labels might be WRONG

  if 'leye' in annotations and 'reye' in annotations and annotations['leye'][1] < annotations['reye'][1]:
    print "Warning: the eye annotations in file '" + file_name + "' might be exchanged!"

  return annotations