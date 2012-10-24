#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Manuel Guenther <Manuel.Guenther@idiap.ch>

import os
import numpy
import bob
from .. import utils

class ToolChain:
  """This class includes functionalities for a default tool chain to produce verification scores"""

  def __init__(self, file_selector):
    """Initializes the tool chain object with the current file selector."""
    self.m_file_selector = file_selector



  def __check_file__(self, filename, force, expected_file_size = 1):
    """Checks if the file exists and has size greater or equal to expected_file_size.
    If the file is to small, or if the force option is set to true, the file is removed.
    This function returns true is the file is there, otherwise false"""
    if os.path.exists(filename):
      if force or os.path.getsize(filename) < expected_file_size:
        utils.debug("  .. Removing old file '%s'." % filename)
        os.remove(filename)
        return False
      else:
        return True
    return False



  def preprocess_images(self, preprocessor, indices=None, force=False):
    """Preprocesses the original images with the given preprocessor."""
    # get the file lists
    image_files = self.m_file_selector.original_image_list()
    preprocessed_image_files = self.m_file_selector.preprocessed_image_list()

    # select a subset of keys to iterate
    if indices != None:
      index_range = range(indices[0], indices[1])
      utils.info("- Preprocessing: splitting of index range %s" % str(indices))
    else:
      index_range = range(len(image_files))

    utils.info("- Preprocessing: processing %d images from directory '%s' to directory '%s'" % (len(index_range), self.m_file_selector.m_database.original_directory, self.m_file_selector.preprocessed_directory))
    # iterate through the images and perform normalization

    # read eye files
    # - note: the resulting value of eye_files may be None
    annotation_list = self.m_file_selector.annotation_list()

    for i in index_range:
      preprocessed_image_file = preprocessed_image_files[i]

      if not self.__check_file__(preprocessed_image_file, force):
        image = preprocessor.read_original_image(str(image_files[i]))
        annotations = None
        if annotation_list != None:
          # read eyes position file
          annotations = annotation_list[i]

        # call the image preprocessor
        preprocessed_image = preprocessor(image, annotations)

        utils.ensure_dir(os.path.dirname(preprocessed_image_file))
        preprocessor.save_image(preprocessed_image, str(preprocessed_image_file))



  def __read_images__(self, files, preprocessor):
    """Reads the preprocessed images from file using the given reader."""
    return [preprocessor.read_image(str(image)) for image in files]

  def __read_images_by_client__(self, files, preprocessor):
    """Reads the preprocessed images from file using the given reader.
    In this case, images are grouped by clients."""
    retval = []
    for client_files in files:
      # images for the client
      retval.append([preprocessor.read_image(str(image)) for image in client_files])
    return retval

  def train_extractor(self, extractor, preprocessor, force = False):
    """Trains the feature extractor using preprocessed images of the 'world' set, if the feature extractor requires training."""
    if extractor.requires_training:
      extractor_file = self.m_file_selector.extractor_file
      if self.__check_file__(extractor_file, force, 1000):
        utils.info("- Extraction: extractor '%s' already exists." % extractor_file)
      else:
        # read training files
        if extractor.split_training_images_by_client:
          train_files = self.m_file_selector.training_list('preprocessed', 'train_extractor', sort_by_client = True)
          train_images = self.__read_images_by_client__(train_files, preprocessor)
          utils.info("- Extraction: training extractor '%s' using %d identities: " %(extractor_file, len(train_files)))
        else:
          train_files = self.m_file_selector.training_list('preprocessed', 'train_extractor')
          train_images = self.__read_images__(train_files, preprocessor)
          utils.info("- Extraction: training extractor '%s' using %d training files: " %(extractor_file, len(train_files)))
        # train model
        utils.ensure_dir(os.path.dirname(extractor_file))
        extractor.train(train_images, extractor_file)



  def extract_features(self, extractor, preprocessor, indices = None, force=False):
    """Extracts the features from the preprocessed images using the given extractor."""
    extractor.load(str(self.m_file_selector.extractor_file))
    image_files = self.m_file_selector.preprocessed_image_list()
    feature_files = self.m_file_selector.feature_list()

    # select a subset of indices to iterate
    if indices != None:
      index_range = range(indices[0], indices[1])
      utils.info("- Extraction: splitting of index range %s" % str(indices))
    else:
      index_range = range(len(image_files))

    utils.info("- Extraction: extracting %d features from directory '%s' to directory '%s'" % (len(index_range), self.m_file_selector.preprocessed_directory, self.m_file_selector.features_directory))
    for i in index_range:
      image_file = image_files[i]
      feature_file = feature_files[i]

      if not self.__check_file__(feature_file, force):
        # load image
        image = preprocessor.read_image(str(image_file))
        # extract feature
        feature = extractor(image)
        # Save feature
        utils.ensure_dir(os.path.dirname(feature_file))
        extractor.save_feature(feature, str(feature_file))



  def __read_features__(self, files, reader):
    """Reads all features from file using the given reader."""
    return [reader.read_feature(str(file)) for file in files]

  def __read_features_by_client__(self, files, reader):
    """Reads all features from file using the given reader.
    In this case, the features are split up by the according client."""
    retval = []
    for client_files in files:
      # features for the client
      retval.append([reader.read_feature(str(feature)) for feature in client_files])
    return retval

  def train_projector(self, tool, extractor, force=False):
    """Train the feature projector with the extracted features of the world group."""
    if tool.requires_projector_training:
      projector_file = self.m_file_selector.projector_file

      if self.__check_file__(projector_file, force, 1000):
        utils.info("- Projection: projector '%s' already exists." % projector_file)
      else:
        # train projector
        if tool.split_training_features_by_client:
          train_files = self.m_file_selector.training_list('features', 'train_projector', arrange_by_client = True)
          train_features = self.__read_features_by_client__(train_files, extractor)
          utils.info("- Projection: training projector '%s' using %d identities: " %(projector_file, len(train_files)))
        else:
          train_files = self.m_file_selector.training_list('features', 'train_projector')
          train_features = self.__read_features__(train_files, extractor)
          utils.info("- Projection: training projector '%s' using %d training files: " %(projector_file, len(train_files)))

        # perform training
        utils.ensure_dir(os.path.dirname(projector_file))
        tool.train_projector(train_features, str(projector_file))



  def project_features(self, tool, extractor, indices = None, force=False):
    """Projects the features for all files of the database."""
    # load the projector file
    if tool.performs_projection:
      tool.load_projector(str(self.m_file_selector.projector_file))

      feature_files = self.m_file_selector.feature_list()
      projected_files = self.m_file_selector.projected_list()

      # select a subset of indices to iterate
      if indices != None:
        index_range = range(indices[0], indices[1])
        utils.info("- Projection: splitting of index range %s" % str(indices))
      else:
        index_range = range(len(feature_files))

      utils.info("- Projection: projecting %d images from directory '%s' to directory '%s'" % (len(index_range), self.m_file_selector.features_directory, self.m_file_selector.projected_directory))
      # extract the features
      for i in index_range:
        feature_file = feature_files[i]
        projected_file = projected_files[i]

        if not self.__check_file__(projected_file, force):
          # load feature
          feature = extractor.read_feature(str(feature_file))
          # project feature
          projected = tool.project(feature)
          # write it
          utils.ensure_dir(os.path.dirname(projected_file))
          tool.save_feature(projected, str(projected_file))



  def train_enroller(self, tool, extractor, force=False):
    """Trains the model enroller using the extracted or projected features, depending on your setup of the base class Tool."""
    reader = tool if tool.use_projected_features_for_enrollment else extractor
    if tool.requires_enroller_training:
      enroller_file = self.m_file_selector.enroller_file

      if self.__check_file__(enroller_file, force, 1000):
        utils.info("- Enrollment: enroller '%s' already exists." % enroller_file)
      else:
        # first, load the projector
        tool.load_projector(str(self.m_file_selector.projector_file))
        # training models
        train_files = self.m_file_selector.training_list('projected' if tool.use_projected_features_for_enrollment else 'features', 'train_enroller', arrange_by_client = True)
        train_features = self.__read_features_by_client__(train_files, reader)

        # perform training
        utils.info("- Enrollment: training enroller '%s' using %d identities: " %(enroller_file, len(train_features)))
        tool.train_enroller(train_features, str(enroller_file))



  def enroll_models(self, tool, extractor, compute_zt_norm, indices = None, groups = ['dev', 'eval'], types = ['N','T'], force=False):
    """Enroll the models for 'dev' and 'eval' groups, for both models and T-Norm-models.
       This function uses the extracted or projected features to compute the models,
       depending on your setup of the base class Tool."""

    # read the projector file, if needed
    tool.load_projector(self.m_file_selector.projector_file)
    # read the model enrollment file
    tool.load_enroller(self.m_file_selector.enroller_file)

    # which tool to use to read the features...
    reader = tool if tool.use_projected_features_for_enrollment else extractor

    # Create Models
    if 'N' in types:
      for group in groups:
        model_ids = self.m_file_selector.model_ids(group)

        if indices != None:
          model_ids = model_ids[indices[0]:indices[1]]
          utils.info("- Enrollment: splitting of index range %s" % str(indices))

        utils.info("- Enrollment: enrolling models of group '%s'" % group)
        for model_id in model_ids:
          # Path to the model
          model_file = self.m_file_selector.model_file(model_id, group)

          # Removes old file if required
          if not self.__check_file__(model_file, force):
            enroll_files = self.m_file_selector.enroll_files(model_id, group, 'projected' if tool.use_projected_features_for_enrollment else 'features')

            # load all files into memory
            enroll_features = [reader.read_feature(str(enroll_file)) for enroll_file in enroll_files]

            model = tool.enroll(enroll_features)
            # save the model
            utils.ensure_dir(os.path.dirname(model_file))
            tool.save_model(model, str(model_file))

    # T-Norm-Models
    if 'T' in types and compute_zt_norm:
      for group in groups:
        t_model_ids = self.m_file_selector.t_model_ids(group)

        if indices != None:
          t_model_ids = t_model_ids[indices[0]:indices[1]]
          utils.info("- Enrollment: splitting of index range %s" % str(indices))

        utils.info("- Enrollment: enrolling T-models of group '%s'" % group)
        for t_model_id in t_model_ids:
          # Path to the model
          t_model_file = self.m_file_selector.t_model_file(t_model_id, group)

          # Removes old file if required
          if not self.__check_file__(t_model_file, force):
            t_enroll_files = self.m_file_selector.t_enroll_files(t_model_id, group, 'projected' if tool.use_projected_features_for_enrollment else 'features')

            # load all files into memory
            t_enroll_features = [reader.read_feature(str(t_enroll_file)) for t_enroll_file in t_enroll_files]

            t_model = tool.enroll(t_enroll_features)
            # save model
            utils.ensure_dir(os.path.dirname(t_model_file))
            tool.save_model(t_model, str(t_model_file))



  def __scores__(self, model, probe_files):
    """Compute simple scores for the given model."""
    scores = numpy.ndarray((1,len(probe_files)), 'float64')

    # Loops over the probes
    for i in range(len(probe_files)):
      # read probe
      probe = self.m_tool.read_probe(str(probe_files[i]))
      # compute score
      scores[0,i] = self.m_tool.score(model, probe)
    # Returns the scores
    return scores

  def __scores_preloaded__(self, model, preloaded_probes):
    """Compute simple scores for the given model."""
    scores = numpy.ndarray((1,len(preloaded_probes)), 'float64')

    # Loops over the probes
    for i in range(len(preloaded_probes)):
      # take pre-loaded probe
      probe = preloaded_probes[i]
      # compute score
      scores[0,i] = self.m_tool.score(model, probe)

    # Returns the scores
    return scores


  def __probe_split__(self, selected_probe_objects, all_probe_objects, all_preloaded_probes):
    """Helper function required when probe files are preloaded."""
    res = []
    selected_index = 0
    for all_index in range(len(all_probe_objects)):
      if selected_index < len(selected_probe_objects) and selected_probe_objects[selected_index].id == all_probe_objects[all_index].id:
        res.append(all_preloaded_probes[all_index])
        selected_index += 1
    assert selected_index == len(selected_probe_objects)
    assert len(selected_probe_objects) == len(res)

    # return the split database
    return res

  def __save_scores__(self, score_file, scores, probe_objects, client_id):
    """Saves the scores into a text file."""
    f = open(score_file, 'w')
    assert len(probe_objects) == scores.shape[1]
    for i in range(len(probe_objects)):
      probe_object = probe_objects[i]
      f.write(str(client_id) + " " + str(probe_object.client_id) + " " + str(probe_object.path) + " " + str(scores[0,i]) + "\n")
    f.close()

  def __scores_a__(self, model_ids, group, compute_zt_norm, force, preload_probes):
    """Computes A scores. For non-ZT-norm, these are the only scores that are actually computed."""
    # preload the probe files for a faster access (and fewer network load)
    if preload_probes:
      utils.info("- Scoring: preloading probe files of group '%s'" % group)
      all_probe_objects = self.m_file_selector.probe_objects(group)
      all_probe_files = self.m_file_selector.get_paths(self.m_file_selector.probe_objects(group), 'projected' if self.m_use_projected_dir else 'features')
      # read all probe files into memory
      all_preloaded_probes = [self.m_tool.read_probe(str(probe_file)) for probe_file in all_probe_files]

    if compute_zt_norm:
      utils.info("- Scoring: computing score matrix A for group '%s'" % group)
    else:
      utils.info("- Scoring: computing scores for group '%s'" % group)

    # Computes the raw scores for each model
    for model_id in model_ids:
      # test if the file is already there
      score_file = self.m_file_selector.a_file(model_id, group) if compute_zt_norm else self.m_file_selector.no_norm_file(model_id, group)
      if self.__check_file__(score_file, force):
        utils.warn("score file '%s' already exists." % (score_file))
      else:
        # get the probe split
        current_probe_objects = self.m_file_selector.probe_objects_for_model(model_id, group)
        model = self.m_tool.read_model(self.m_file_selector.model_file(model_id, group))
        if preload_probes:
          # select the probe files for this model from all probes
          current_preloaded_probes = self.__probe_split__(current_probe_objects, all_probe_objects, all_preloaded_probes)
          # compute A matrix
          a = self.__scores_preloaded__(model, current_preloaded_probes)
        else:
          current_probe_files = self.m_file_selector.get_paths(current_probe_objects, 'projected' if self.m_use_projected_dir else 'features')
          a = self.__scores__(model, current_probe_files)

        if compute_zt_norm:
          # write A matrix only when you want to compute zt norm afterwards
          bob.io.save(a, self.m_file_selector.a_file(model_id, group))

        # Save scores to text file
        self.__save_scores__(self.m_file_selector.no_norm_file(model_id, group), a, current_probe_objects, self.m_file_selector.client_id(model_id))

  def __scores_b__(self, model_ids, group, force, preload_probes):
    """Computes B scores."""
    # probe files:
    z_probe_objects = self.m_file_selector.z_probe_objects(group)
    z_probe_files = self.m_file_selector.get_paths(z_probe_objects, 'projected' if self.m_use_projected_dir else 'features')
    # preload the probe files for a faster access (and fewer network load)
    if preload_probes:
      utils.info("- Scoring: preloading Z-probe files of group '%s'" % group)
      # read all probe files into memory
      preloaded_z_probes = [self.m_tool.read_probe(str(z_probe_file)) for z_probe_file in z_probe_files]

    utils.info("- Scoring: computing score matrix B for group '%s'" % group)

    # Loads the models
    for model_id in model_ids:
      # test if the file is already there
      score_file = self.m_file_selector.b_file(model_id, group)
      if self.__check_file__(score_file, force):
        utils.warn("score file '%s' already exists." % (score_file))
      else:
        model = self.m_tool.read_model(self.m_file_selector.model_file(model_id, group))
        if preload_probes:
          b = self.__scores_preloaded__(model, preloaded_z_probes)
        else:
          b = self.__scores__(model, z_probe_files)
        bob.io.save(b, score_file)

  def __scores_c__(self, t_model_ids, group, force, preload_probes):
    """Computes C scores."""
    # probe files:
    probe_objects = self.m_file_selector.probe_objects(group)
    probe_files = self.m_file_selector.get_paths(probe_objects, 'projected' if self.m_use_projected_dir else 'features')

    # preload the probe files for a faster access (and fewer network load)
    if preload_probes:
      utils.info("- Scoring: preloading probe files of group '%s'" % group)
      # read all probe files into memory
      preloaded_probes = [self.m_tool.read_probe(str(probe_file)) for probe_file in probe_files]

    utils.info("- Scoring: computing score matrix C for group '%s'" % group)

    # Computes the raw scores for the T-Norm model
    for t_model_id in t_model_ids:
      # test if the file is already there
      score_file = self.m_file_selector.c_file(t_model_id, group)
      if self.__check_file__(score_file, force):
        utils.warn("score file '%s' already exists." % (score_file))
      else:
        t_model = self.m_tool.read_model(self.m_file_selector.t_model_file(t_model_id, group))
        if preload_probes:
          c = self.__scores_preloaded__(t_model, preloaded_probes)
        else:
          c = self.__scores__(t_model, probe_files)
        bob.io.save(c, score_file)

  def __scores_d__(self, t_model_ids, group, force, preload_probes):
    """Computes D scores."""
    # probe files:
    z_probe_objects = self.m_file_selector.z_probe_objects(group)
    z_probe_files = self.m_file_selector.get_paths(z_probe_objects, 'projected' if self.m_use_projected_dir else 'features')

    # preload the probe files for a faster access (and fewer network load)
    if preload_probes:
      utils.info("- Scoring: preloading Z-probe files of group '%s'" % group)
      # read all probe files into memory
      preloaded_z_probes = [self.m_tool.read_probe(str(z_probe_file)) for z_probe_file in z_probe_files]

    utils.info("- Scoring: computing score matrix D for group '%s'" % group)

    # Gets the Z-Norm impostor samples
    z_probe_ids = []
    for z_probe_object in z_probe_objects:
      z_probe_ids.append(z_probe_object.client_id)

    # Loads the T-Norm models
    for t_model_id in t_model_ids:
      # test if the file is already there
      score_file = self.m_file_selector.d_same_value_file(t_model_id, group)
      if self.__check_file__(score_file, force):
        utils.warn("score file '%s' already exists." % (score_file))
      else:
        t_model = self.m_tool.read_model(self.m_file_selector.t_model_file(t_model_id, group))
        if preload_probes:
          d = self.__scores_preloaded__(t_model, preloaded_z_probes)
        else:
          d = self.__scores__(t_model, z_probe_files)
        bob.io.save(d, self.m_file_selector.d_file(t_model_id, group))

        t_client_id = [self.m_file_selector.client_id(t_model_id)]
        d_same_value_tm = bob.machine.ztnorm_same_value(t_client_id, z_probe_ids)
        bob.io.save(d_same_value_tm, score_file)


  def compute_scores(self, tool, compute_zt_norm, force = False, indices = None, groups = ['dev', 'eval'], types = ['A', 'B', 'C', 'D'], preload_probes = False):
    """Computes the scores for the given groups (by default 'dev' and 'eval')."""
    # save tool for internal use
    self.m_tool = tool
    self.m_use_projected_dir = hasattr(tool, 'project')

    # load the projector and the enroller, if needed
    tool.load_projector(self.m_file_selector.projector_file)
    tool.load_enroller(self.m_file_selector.enroller_file)

    for group in groups:
      # get model ids
      model_ids = self.m_file_selector.model_ids(group)
      if compute_zt_norm:
        t_model_ids = self.m_file_selector.t_model_ids(group)

      # compute A scores
      if 'A' in types:
        if indices != None:
          model_ids_short = model_ids[indices[0]:indices[1]]
          utils.info("- Scoring: splitting of index range %s" % str(indices))
        else:
          model_ids_short = model_ids
        self.__scores_a__(model_ids_short, group, compute_zt_norm, force, preload_probes)

      if compute_zt_norm:
        # compute B scores
        if 'B' in types:
          if indices != None:
            model_ids_short = model_ids[indices[0]:indices[1]]
            utils.info("- Scoring: splitting of index range %s" % str(indices))
          else:
            model_ids_short = model_ids
          self.__scores_b__(model_ids_short, group, force, preload_probes)

        # compute C scores
        if 'C' in types:
          if indices != None:
            t_model_ids_short = t_model_ids[indices[0]:indices[1]]
            utils.info("- Scoring: splitting of index range %s" % str(indices))
          else:
            t_model_ids_short = t_model_ids
          self.__scores_c__(t_model_ids_short, group, force, preload_probes)

        # compute D scores
        if 'D' in types:
          if indices != None:
            t_model_ids_short = t_model_ids[indices[0]:indices[1]]
            utils.info("- Scoring: splitting of index range %s" % str(indices))
          else:
            t_model_ids_short = t_model_ids
          self.__scores_d__(t_model_ids_short, group, force, preload_probes)



  def __c_matrix_split_for_model__(self, selected_probe_objects, all_probe_objects, all_c_scores):
    """Helper function to sub-select the c-scores in case not all probe files were used to compute A scores."""
    c_scores_for_model = numpy.ndarray((all_c_scores.shape[0], len(selected_probe_objects)), numpy.float64)
    selected_index = 0
    for all_index in range(len(all_probe_objects)):
      if selected_index < len(selected_probe_objects) and selected_probe_objects[selected_index].id == all_probe_objects[all_index].id:
        c_scores_for_model[:,selected_index] = all_c_scores[:,all_index]
        selected_index += 1
    assert selected_index == len(selected_probe_objects)

    # return the split database
    return c_scores_for_model

  def __scores_c_normalize__(self, model_ids, t_model_ids, group):
    """Compute normalized probe scores using T-model scores."""
    # read all tmodel scores
    c_for_all = None
    for t_model_id in t_model_ids:
      tmp = bob.io.load(self.m_file_selector.c_file(t_model_id, group))
      if c_for_all == None:
        c_for_all = tmp
      else:
        c_for_all = numpy.vstack((c_for_all, tmp))
    # iterate over all models and generate C matrices for that specific model
    all_probe_objects = self.m_file_selector.probe_objects(group)
    for model_id in model_ids:
      # select the correct probe files for the current model
      probe_objects_for_model = self.m_file_selector.probe_objects_for_model(model_id, group)
      c_matrix_for_model = self.__c_matrix_split_for_model__(probe_objects_for_model, all_probe_objects, c_for_all)
      # Save C matrix to file
      bob.io.save(c_matrix_for_model, self.m_file_selector.c_file_for_model(model_id, group))

  def __scores_d_normalize__(self, t_model_ids, group):
    """Compute normalized D scores for the given T-model ids"""
    # initialize D and D_same_value matrices
    d_for_all = None
    d_same_value = None
    for t_model_id in t_model_ids:
      tmp = bob.io.load(self.m_file_selector.d_file(t_model_id, group))
      tmp2 = bob.io.load(self.m_file_selector.d_same_value_file(t_model_id, group))
      if d_for_all == None and d_same_value == None:
        d_for_all = tmp
        d_same_value = tmp2
      else:
        d_for_all = numpy.vstack((d_for_all, tmp))
        d_same_value = numpy.vstack((d_same_value, tmp2))

    # Saves to files
    bob.io.save(d_for_all, self.m_file_selector.d_matrix_file(group))
    bob.io.save(d_same_value, self.m_file_selector.d_same_value_matrix_file(group))



  def zt_norm(self, groups = ['dev', 'eval']):
    """Computes ZT-Norm using the previously generated A, B, C, and D files"""
    for group in groups:
      utils.info("- Scoring: computing ZT-norm for group '%s'" % group)
      # list of models
      model_ids = self.m_file_selector.model_ids(group)
      t_model_ids = self.m_file_selector.t_model_ids(group)

      # first, normalize C and D scores
      self.__scores_c_normalize__(model_ids, t_model_ids, group)
      # and normalize it
      self.__scores_d_normalize__(t_model_ids, group)


      # load D matrices only once
      d = bob.io.load(self.m_file_selector.d_matrix_file(group))
      d_same_value = bob.io.load(self.m_file_selector.d_same_value_matrix_file(group)).astype(bool)
      # Loops over the model ids
      for model_id in model_ids:
        # Loads probe files to get information about the type of access
        probe_objects = self.m_file_selector.probe_objects_for_model(model_id, group)

        # Loads A, B, and C matrices for current model id
        a = bob.io.load(self.m_file_selector.a_file(model_id, group))
        b = bob.io.load(self.m_file_selector.b_file(model_id, group))
        c = bob.io.load(self.m_file_selector.c_file_for_model(model_id, group))

        # compute zt scores
        zt_scores = bob.machine.ztnorm(a, b, c, d, d_same_value)

        # Saves to text file
        self.__save_scores__(self.m_file_selector.zt_norm_file(model_id, group), zt_scores, probe_objects, self.m_file_selector.client_id(model_id))


  def concatenate(self, compute_zt_norm, groups = ['dev', 'eval']):
    """Concatenates all results into one (or two) score files per group."""
    for group in groups:
      utils.info("- Scoring: concatenating score files for group '%s'" % group)
      # (sorted) list of models
      model_ids = self.m_file_selector.model_ids(group)

      f = open(self.m_file_selector.no_norm_result_file(group), 'w')
      # Concatenates the scores
      for model_id in model_ids:
        model_file = self.m_file_selector.no_norm_file(model_id, group)
        if not os.path.exists(model_file):
          f.close()
          os.remove(self.m_file_selector.no_norm_result_file(group))
          raise IOError("The score file '%s' cannot be found. Aborting!" % model_file)

        res_file = open(model_file, 'r')
        f.write(res_file.read())
      f.close()

      if compute_zt_norm:
        f = open(self.m_file_selector.zt_norm_result_file(group), 'w')
        # Concatenates the scores
        for model_id in model_ids:
          model_file = self.m_file_selector.zt_norm_file(model_id, group)
          if not os.path.exists(model_file):
            f.close()
            os.remove(self.m_file_selector.zt_norm_result_file(group))
            raise IOError("The score file '%s' cannot be found. Aborting!" % model_file)

          res_file = open(model_file, 'r')
          f.write(res_file.read())
        f.close()