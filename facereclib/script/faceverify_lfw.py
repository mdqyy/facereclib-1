#!/usr/bin/env python
# vim: set fileencoding=utf-8 :
# Manuel Guenther <Manuel.Guenther@idiap.ch>


import sys, os
import argparse
import numpy
import bob

from . import ToolChainExecutor
from .. import toolchain

class ToolChainExecutorLFW (ToolChainExecutor.ToolChainExecutor):
  
  def __init__(self, args, protocol):
    # select the protocol
    self.m_protocol = protocol

    # call base class constructor
    ToolChainExecutor.ToolChainExecutor.__init__(self, args)

    # specify the file selector and tool chain objects to be used by this class (and its base class) 
    self.m_file_selector = toolchain.FileSelectorZT(self.m_configuration, self.m_database_config)
    self.m_tool_chain = toolchain.ToolChainZT(self.m_file_selector)
    

  def protocol_specific_configuration(self):
    """Special configuration for GBU protocol"""
    self.m_configuration.img_input_dir = self.m_database_config.img_input_dir  
    self.m_database_config.protocol = self.m_protocol
    self.m_configuration.models_dir = os.path.join(self.m_configuration.base_output_TEMP_dir, self.m_args.model_dir, self.m_database_config.protocol)
  
    self.m_configuration.default_extension = ".hdf5"
    
    self.m_configuration.scores_nonorm_dir = os.path.join(self.m_configuration.base_output_USER_dir, self.m_args.score_sub_dir, self.m_database_config.protocol) 
    if self.m_args.result_file:
      self.m_configuration.result_file = self.m_args.result_file 
    else:
      self.m_configuration.result_file = os.path.join(self.m_configuration.base_output_USER_dir, self.m_args.score_sub_dir, 'results.txt') 

    # each fold might have its own feature extraction training and feature projection training, 
    # so we have to overwrite the default directories
    self.m_configuration.preprocessed_dir = os.path.join(self.m_configuration.base_output_TEMP_dir, self.m_args.preprocessed_dir, 'view1' if self.m_database_config.protocol == 'view1' else 'view2')
    self.m_configuration.features_dir = os.path.join(self.m_configuration.base_output_TEMP_dir, self.m_args.features_dir, self.m_database_config.protocol)
    self.m_configuration.projected_dir = os.path.join(self.m_configuration.base_output_TEMP_dir, self.m_args.projected_dir, self.m_database_config.protocol)
    
    
  def execute_tool_chain(self):
    """Executes the desired tool chain on the local machine"""
    # preprocessing
    if not self.m_args.skip_preprocessing:
      self.m_tool_chain.preprocess_images(self.m_preprocessor, force = self.m_args.force)
    # feature extraction
    if not self.m_args.skip_feature_extraction_training and hasattr(self.m_feature_extractor, 'train'):
      self.m_tool_chain.train_extractor(self.m_feature_extractor, force = self.m_args.force)
    if not self.m_args.skip_feature_extraction:
      self.m_tool_chain.extract_features(self.m_feature_extractor, force = self.m_args.force)
    # feature projection
    if not self.m_args.skip_projection_training and hasattr(self.m_tool, 'train_projector'):
      self.m_tool_chain.train_projector(self.m_tool, force = self.m_args.force)
    if not self.m_args.skip_projection and hasattr(self.m_tool, 'project'):
      self.m_tool_chain.project_features(self.m_tool, force = self.m_args.force, extractor = self.m_feature_extractor)
    # model enrollment
    if not self.m_args.skip_enroler_training and hasattr(self.m_tool, 'train_enroler'):
      self.m_tool_chain.train_enroler(self.m_tool, force = self.m_args.force)
    if not self.m_args.skip_model_enrolment:
      self.m_tool_chain.enrol_models(self.m_tool, compute_zt_norm = False, force = self.m_args.force)
    # score computation
    if not self.m_args.skip_score_computation:
      self.m_tool_chain.compute_scores(self.m_tool, compute_zt_norm = False, preload_probes = self.m_args.preload_probes, force = self.m_args.force)
    self.m_tool_chain.concatenate(compute_zt_norm = False)
    

  def add_jobs_to_grid(self, external_dependencies, perform_preprocessing):
    # collect job ids
    job_ids = {}
  
    # if there are any external dependencies, we need to respect them
    deps = external_dependencies[:]
    
    protocol = self.m_database_config.protocol
    default_opt = ' --protocol %s'%protocol
    # image preprocessing; never has any dependencies.
    if not self.m_args.skip_preprocessing and perform_preprocessing:
      job_ids['preprocessing'] = self.submit_grid_job(
              '--preprocess' + default_opt, 
              name = 'pre-%s'%protocol, 
              list_to_split = self.m_file_selector.original_image_list(), 
              number_of_files_per_job = self.m_grid_config.number_of_images_per_job, 
              dependencies = deps, 
              **self.m_grid_config.preprocessing_queue)
      deps.append(job_ids['preprocessing'])
      
    # feature extraction training
    if not self.m_args.skip_feature_extraction_training and hasattr(self.m_feature_extractor, 'train'):
      job_ids['extraction_training'] = self.submit_grid_job(
              '--feature-extraction-training' + default_opt, 
              name = 'f-train-%s'%protocol, 
              dependencies = deps,
              **self.m_grid_config.training_queue)
      deps.append(job_ids['extraction_training'])
       
    if not self.m_args.skip_feature_extraction:
      job_ids['feature_extraction'] = self.submit_grid_job(
              '--feature-extraction' + default_opt, 
              name = 'extr-%s'%protocol, 
              list_to_split = self.m_file_selector.preprocessed_image_list(), 
              number_of_files_per_job = self.m_grid_config.number_of_features_per_job, 
              dependencies = deps, 
              **self.m_grid_config.extraction_queue)
      deps.append(job_ids['feature_extraction'])
      
    # feature projection training
    if not self.m_args.skip_projection_training and hasattr(self.m_tool, 'train_projector'):
      job_ids['projector_training'] = self.submit_grid_job(
              '--train-projector' + default_opt, 
              name = "p-train-%s"%protocol, 
              dependencies = deps, 
              **self.m_grid_config.training_queue)
      deps.append(job_ids['projector_training'])
      
    if not self.m_args.skip_projection and hasattr(self.m_tool, 'project'):
      job_ids['feature_projection'] = self.submit_grid_job(
              '--feature-projection' + default_opt, 
              list_to_split = self.m_file_selector.feature_list(), 
              number_of_files_per_job = self.m_grid_config.number_of_projections_per_job, 
              dependencies = deps, 
              name="pro-%s"%protocol, 
              **self.m_grid_config.projection_queue)
      deps.append(job_ids['feature_projection'])
      
    # model enrolment training
    if not self.m_args.skip_enroler_training and hasattr(self.m_tool, 'train_enroler'):
      job_ids['enrolment_training'] = self.submit_grid_job(
              '--train-enroler' + default_opt, 
              dependencies = deps, 
              name="e-train-%s"%protocol, 
              **self.m_grid_config.training_queue)
      deps.append(job_ids['enrolment_training'])
      
    # enrol models
    groups = ['dev'] if protocol=='view1' else self.m_args.groups
    if not self.m_args.skip_model_enrolment:
      for group in groups:
        job_ids['enrol-%s'%group] = self.submit_grid_job(
                '--enrol-models --group %s'%group + default_opt, 
                list_to_split = self.m_file_selector.model_ids(group), 
                number_of_files_per_job = self.m_grid_config.number_of_models_per_enrol_job, 
                dependencies = deps, 
                name = "enrol-%s-%s"%(protocol,group),
                **self.m_grid_config.enrol_queue)
        deps.append(job_ids['enrol-%s'%group])
  
    # compute scores
    if not self.m_args.skip_score_computation:
      for group in groups:
        job_ids['score-%s'%group] = self.submit_grid_job(
                '--compute-scores --group %s'%group + default_opt, 
                list_to_split = self.m_file_selector.model_ids(group), 
                number_of_files_per_job = self.m_grid_config.number_of_models_per_score_job, 
                dependencies = deps, 
                name = "score-%s-%s"%(protocol,group), 
                **self.m_grid_config.score_queue)
        deps.append(job_ids['score-%s'%group])
      
    # concatenate results
    job_ids['concatenate'] = self.submit_grid_job(
            '--concatenate' + default_opt, 
            dependencies = deps, 
            name = "concat-%s"%protocol)
        
    # return the job ids, in case anyone wants to know them
    return job_ids 
  
  def add_average_job_to_grid(self, external_dependencies):
    """Adds the job to average the results of the runs"""
    return {'average' : \
        self.submit_grid_job(\
              '--average-results --protocol view1',\
              dependencies = external_dependencies,\
              name = "average")}
    
  
  def execute_grid_job(self):
    """This function executes the grid job that is specified on the command line."""
    # preprocess
    if self.m_args.preprocess:
      self.m_tool_chain.preprocess_images(
          self.m_preprocessor, 
          indices = self.indices(self.m_file_selector.original_image_list(), self.m_grid_config.number_of_images_per_job), 
          force = self.m_args.force)
      
    if self.m_args.feature_extraction_training:
      self.m_tool_chain.train_extractor(
          self.m_feature_extractor, 
          force = self.m_args.force)
      
    # extract features
    if self.m_args.feature_extraction:
      self.m_tool_chain.extract_features(
          self.m_feature_extractor, 
          indices = self.indices(self.m_file_selector.preprocessed_image_list(), self.m_grid_config.number_of_features_per_job), 
          force = self.m_args.force)
      
    # train the feature projector
    if self.m_args.train_projector:
      self.m_tool_chain.train_projector(
          self.m_tool, 
          force = self.m_args.force)
      
    # project the features
    if self.m_args.projection:
      self.m_tool_chain.project_features(
          self.m_tool, 
          extractor = self.m_feature_extractor,
          indices = self.indices(self.m_file_selector.preprocessed_image_list(), self.m_grid_config.number_of_projections_per_job), 
          force = self.m_args.force)
      
    # train model enroler
    if self.m_args.train_enroler:
      self.m_tool_chain.train_enroler(
          self.m_tool, 
          force = self.m_args.force)
      
    # enrol models
    if self.m_args.enrol_models:
      self.m_tool_chain.enrol_models(
          self.m_tool,
          groups = (self.m_args.group,),
          compute_zt_norm = False,
          indices = self.indices(self.m_file_selector.model_ids(self.m_args.group), self.m_grid_config.number_of_models_per_enrol_job), 
          force = self.m_args.force)
        
    # compute scores
    if self.m_args.compute_scores:
      self.m_tool_chain.compute_scores(
          self.m_tool, 
          groups = (self.m_args.group,),
          compute_zt_norm = False,
          indices = self.indices(self.m_file_selector.model_ids(self.m_args.group), self.m_grid_config.number_of_models_per_score_job), 
          preload_probes = self.m_args.preload_probes, 
          force = self.m_args.force)
  
    # concatenate
    if self.m_args.concatenate:
      self.m_tool_chain.concatenate(compute_zt_norm = False)
      
    # average
    if self.m_args.average_results:
      self.average_results()

  def __classification_result__(self, negatives, positives, threshold):
    return (\
        bob.measure.correctly_classified_negatives(negatives, threshold).sum(dtype=numpy.float64) +\
        bob.measure.correctly_classified_positives(positives, threshold).sum(dtype=numpy.float64)\
      ) / float(len(positives) + len(negatives))

  def average_results(self):
    """Iterates over all the folds of the current view and computes the average result"""
    file = open(self.m_configuration.result_file, 'w')
    if 'view1' in self.m_args.views:
      # process the single result of view 1
      self.m_database_config.protocol = 'view1'
      res_file = self.m_file_selector.no_norm_result_file('dev')
      
      negatives, positives = bob.measure.load.split_four_column(res_file)
      threshold = bob.measure.eer_threshold(negatives, positives)
      
      far, frr = bob.measure.farfrr(negatives, positives, threshold)
      hter = (far + frr)/2.0
      
      file.write("On view1 (dev set only):\n\nFAR = %f;\tFRR = %f;\tHTER = %f;\tthreshold = %f\n"%(far, frr, hter, threshold))
      file.write("Classification Success:%f%%\n\n"%(self.__classification_result__(negatives, positives, threshold) * 100.))
      
    if 'view2' in self.m_args.views:
      file.write("On view2 (eval set only):\n\n")
      # iterate over all folds of view 2
      errors = numpy.ndarray((10,), numpy.float64)
      for f in range(1,11):
        # configure the file selector with the current protocol
        self.m_protocol = 'fold%d'%f
        self.protocol_specific_configuration()
        dev_res_file = self.m_file_selector.no_norm_result_file('dev')
        eval_res_file = self.m_file_selector.no_norm_result_file('eval')
      
        # compute threshold on dev data
        dev_negatives, dev_positives = bob.measure.load.split_four_column(dev_res_file)
        threshold = bob.measure.eer_threshold(dev_negatives, dev_positives)
        
        # compute FAR and FRR for eval data
        eval_negatives, eval_positives = bob.measure.load.split_four_column(eval_res_file)
        
        far, frr = bob.measure.farfrr(eval_negatives, eval_positives, threshold)
        hter = (far + frr)/2.0
        
        file.write("On fold%d:\n\nFAR = %f;\tFRR = %f;\tHTER = %f;\tthreshold = %f\n"%(f, far, frr, hter, threshold))
        result = self.__classification_result__(eval_negatives, eval_positives, threshold)
        file.write("Classification Success:%f%%\n\n"%(result * 100.))
        errors[f-1] = result
      
      # compute mean and std error
      mean = numpy.mean(errors)
      std = numpy.std(errors)
      file.write("\nOverall classification success: %f (with std %f)\n"%(mean,std))
        
      
      
  
  
def parse_args(command_line_arguments = sys.argv[1:]):
  """This function parses the given options (which by default are the command line options)"""
  # sorry for that.
  global parameters
  parameters = command_line_arguments

  # set up command line parser
  parser = argparse.ArgumentParser(description=__doc__,
      formatter_class=argparse.ArgumentDefaultsHelpFormatter)
  
  # add the arguments required for all tool chains
  config_group, dir_group, file_group, sub_dir_group, other_group, skip_group = ToolChainExecutorLFW.required_command_line_options(parser)

  sub_dir_group.add_argument('--model-directory', type = str, metavar = 'DIR', dest='model_dir', default = 'models',
      help = 'Subdirectories (of temp directory) where the models should be stored')
  
  file_group.add_argument('--result-file', '-r', type = str, metavar = 'FILE',
      help = 'The file where the final results should be written into. By default, \'results.txt\' in the USER directory.')
  
  #######################################################################################
  ############################ other options ############################################
  other_group.add_argument('-f', '--force', action='store_true',
      help = 'Force to erase former data if already exist')
  other_group.add_argument('-w', '--preload-probes', action='store_true', dest='preload_probes',
      help = 'Preload probe files during score computation (needs more memory, but is faster and requires fewer file accesses). WARNING! Use this flag with care!')
  other_group.add_argument('--views', type = str, nargs = '+', choices = ('view1', 'view2'), default = 'view1',
      help = 'The views to be used, by default only the "view1" is executed.')
  other_group.add_argument('--groups', type = str, nargs = '+', choices = ('dev', 'eval'), default = ('dev','eval'),
      help = 'The groups to compute the scores for.')

  #######################################################################################
  #################### sub-tasks being executed by this script ##########################
  parser.add_argument('--execute-sub-task', action='store_true',
      help = argparse.SUPPRESS) #'Executes a subtask (FOR INTERNAL USE ONLY!!!)'
  parser.add_argument('--preprocess', action='store_true', 
      help = argparse.SUPPRESS) #'Perform image preprocessing on the given range of images'
  parser.add_argument('--group', type=str, choices=['dev','eval'],
      help = argparse.SUPPRESS) #'The subset of the data for which the process should be executed'
  parser.add_argument('--protocol', type=str, choices=['view1','fold1','fold2','fold3','fold4','fold5','fold6','fold7','fold8','fold9','fold10'],
      help = argparse.SUPPRESS) #'The protocol which should be used in this sub-task'
  parser.add_argument('--feature-extraction-training', action='store_true',
      help = argparse.SUPPRESS) #'Perform feature extraction for the given range of preprocessed images'
  parser.add_argument('--feature-extraction', action='store_true',
      help = argparse.SUPPRESS) #'Perform feature extraction for the given range of preprocessed images'
  parser.add_argument('--train-projector', action='store_true',
      help = argparse.SUPPRESS) #'Perform feature extraction training'
  parser.add_argument('--feature-projection', action='store_true', dest = 'projection',
      help = argparse.SUPPRESS) #'Perform feature projection'
  parser.add_argument('--train-enroler', action='store_true',
      help = argparse.SUPPRESS) #'Perform enrolment training'
  parser.add_argument('--enrol-models', action='store_true',
      help = argparse.SUPPRESS) #'Generate the given range of models from the features'
  parser.add_argument('--compute-scores', action='store_true',
      help = argparse.SUPPRESS) #'Compute scores for the given range of models'
  parser.add_argument('--concatenate', action='store_true',
      help = argparse.SUPPRESS) #'Concatenates the results of all scores of the given group'
  parser.add_argument('--average-results', action='store_true',
      help = argparse.SUPPRESS) #'Concatenates the results of all scores of the given group'
  
  return parser.parse_args(command_line_arguments)


def face_verify(args, external_dependencies = [], external_fake_job_id = 0):
  """This is the main entry point for computing face verification experiments.
  You just have to specify configuration scripts for any of the steps of the toolchain, which are:
  -- the database
  -- feature extraction (including image preprocessing)
  -- the score computation tool
  -- and the grid configuration (in case, the function should be executed in the grid).
  Additionally, you can skip parts of the toolchain by selecting proper --skip-... parameters.
  If your probe files are not too big, you can also specify the --preload-probes switch to speed up the score computation.
  If files should be re-generated, please specify the --force option (might be combined with the --skip-... options)"""
  
  if args.execute_sub_task:
    # execute the desired sub-task
    executor = ToolChainExecutorLFW(args, protocol=args.protocol)
    executor.execute_grid_job()
    return []
  
  elif args.grid:

    # get the name of this file 
    this_file = __file__
    if this_file[-1] == 'c':
      this_file = this_file[0:-1]
      
    # initialize the executor to submit the jobs to the grid 
    global parameters
    
    # for the first protocol, we do not have any own dependencies
    dependencies = external_dependencies
    resulting_dependencies = {}
    average_dependencies = []
    perform_preprocessing = True
    dry_run_init = external_fake_job_id
    # determine which protocols should be used
    protocols=[]
    if 'view1' in args.views:
      protocols.append('view1')
    if 'view2' in args.views:
      protocols.extend(['fold%d'%i for i in range(1,11)])

    # execute all desired protocols
    for protocol in protocols:
      # create an executor object
      executor = ToolChainExecutorLFW(args, protocol)
      executor.set_common_parameters(calling_file = this_file, parameters = parameters, fake_job_id = dry_run_init)

      # add the jobs
      new_dependencies = executor.add_jobs_to_grid(dependencies, perform_preprocessing)
      resulting_dependencies.update(new_dependencies)
      average_dependencies.append(new_dependencies['concatenate'])
      # perform preprocessing only once for view 2
      if perform_preprocessing and protocol != 'view1':
        dependencies.append(new_dependencies['preprocessing'])
        perform_preprocessing = False

      dry_run_init += 30
      
    # at the end, compute the average result
    last_dependency = executor.add_average_job_to_grid(average_dependencies)
    resulting_dependencies.update(last_dependency)
    # at the end of all protocols, return the list of dependencies
    return resulting_dependencies
  else:
    # not in a grid, use default tool chain sequentially

    # determine which protocols should be used
    protocols=[]
    if 'view1' in args.views:
      protocols.append('view1')
    if 'view2' in args.views:
      protocols.extend(['fold%d'%i for i in range(1,11)])
    
    for protocol in protocols:
      # generate executor for the current protocol
      executor = ToolChainExecutorLFW(args, protocol)
      # execute the tool chain locally
      executor.execute_tool_chain()
    
    # after all protocols have been processed, compute average result 
    executor.average_results()
    # no dependencies since we executed the jobs locally
    return []
    

def main():
  """Executes the main function"""
  # do the command line parsing
  args = parse_args()
  # perform face verification test
  face_verify(args)
        
if __name__ == "__main__":
  main()  
