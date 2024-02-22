import os
from configargparse import ArgParser

class PipeArgs(object):

    @staticmethod 
    def argument_parser():
        # Create command line arguments
        parser = ArgParser()
        # General arguments
        parser.add('--db_section',required=True,help = "Database section in your \
                             .desservices.ini file, e.g., db-desoper or db-destest")
        parser.add("--user", action="store", default=os.environ['USER'],
                            help="username that will submit")
        parser.add('--paramfile',is_config_file=True,help='Key = Value file that can be used to replace\
                             command-line')
        parser.add('--csv',help='CSV of exposures and information specified by user. If specified, \
                             code will use exposures in csv to submit jobs. Must also specify \
                             --delimiter')
        parser.add('--exclude_list',help='A comma-separated list or line-separated file of exposures \
                             to exclude from the dataframe')
        parser.add('--delimiter',default=',',help='The delimiter if specifying csv and is not \
                             comma-separated')
        parser.add('--campaign',required=True, help='Directory in pipebox where templates are \
                             stored, e.g., $PIPEBOX_DIR/templates/pipelines/finalcut/-->Y2A1dev<--')
        parser.add('--savefiles',action='store_true',help='Saves submit files to submit later.')
        parser.add('--queue_size',default=1000,help='If set and savefiles is not specified, code \
                             will submit specified runs up until queue_size is reached. Code \
                             will wait until queue drops below limit to submit next job')
        parser.add('--total_queue',action='store_true',help='If specified, total jobs per \
                             pipeline per machine will be counted and user will be ignored')
        parser.add('--labels',help='Human-readable labels to "mark" a given processing attempt')
        parser.add('--template_name',help='submitwcl template within pipeline/campaign')
        parser.add('--configfile',help='Name of user cfg file')
        parser.add('--out',help='Output directory for submit files')
        parser.add('--auto',action='store_true',help='Will run autosubmit mode if specified')
        parser.add('--resubmit_failed',action='store_true',help='Will ressubmit failed runs')
        parser.add('--resubmit_max',default=99,help='Set max attempt number for resubmit-failed.')
        parser.add('--ignore_processed',action='store_true',help='Will skip any expnum \
                             that has been attempted to process, pass/fail.')
        parser.add('--wait',default=30,help='Wait time (seconds) between dessubmits. \
                                             Default=30s')
        
        # Archive arguments
        parser.add('--target_site',required=True,help='Computing node, i.e., fermigrid-sl6')
        parser.add('--priority_site', help='Computing node for high priority exposures')
        parser.add('--archive_name',help='Home archive to store products, e.g., \
                             desar2home,prodbeta,...')
        parser.add('--project',default='ACT',help='Archive directory where runs are \
                             stored, e.g., $ARCHIVE/-->ACT<--/finalcut/')
        parser.add('--rundir',help='Archive directory structure')
        parser.add('--http',help='The machine to copy files through: desar0, desar1,desar2')
        
        # JIRA arguments
        parser.add('--jira_parent',help='JIRA parent ticket under which\
                             new ticket will be created.')
        parser.add('--jira_description',help='Description of ticket\
                             found in JIRA')
        parser.add('--jira_project',default='DESOPS',help='JIRA project where \
                             ticket will be created, e.g., DESOPS')
        parser.add('--jira_summary',help='Title of JIRA ticket. To submit multiple \
                             exposures under same ticket you can specify jira_summary')
        parser.add('--jira_user',help='JIRA username')
        parser.add('--jira_section',default='jira-desdm',help='JIRA section \
                             in .desservices.ini file')
        parser.add('--ignore_jira',default=False,action='store_true',help="If specified will not \
                            connect to JIRA, but must specify reqnum and jira_parent.")
        parser.add('--reqnum',help='Part of processing unique identifier. Tied to JIRA ticket \
                             number')
        parser.add('--decade', action='store_true', help='Uses the DECADE subsection of WCL')
        parser.add('--assign_reqnum', action='store_true', help='Ignore jira and create reqnum based on JIRA_RECORDS table')
 
        # EUPS arguments
        parser.add('--eups_stack',action='append',nargs='+', required=True,help='EUPS production stack, \
                                                                               e.g., finalcut Y2A1+4')
        
        # Science arguments
        parser.add('--ccdnum',help='CCDs to be processed.')
        parser.add('--minsigma',help='Specify minsigma for immask (defaults to 6.0)')
        parser.add('--nite',help='For auto mode: if specified will submit all exposures found \
                         from nite')
        parser.add('--niterange',nargs='+',action='append',help='Specify a range of nites')
        parser.add('--RA','-ra',nargs='+',action='append',help='RA in deg., in the order of min max')
        parser.add('--Dec','-dec',nargs='+',action='append',help='Dec in deg., in the order of min max')
        parser.add('--epoch',help='Observing epoch. If not specified, will be calculated. E.g.,\
                         SVE1,SVE2,Y1E1,Y1E2,Y2E1,Y2E2...')
        parser.add('--inputcals_file',help='Key=Var list of calibrations to be used in processing. \
                         $PIPEBOX_DIR/templates/inputcals for a sample')

        # glide in options
        parser.add('--time_to_live',default=None,type=float,help='The amount of time-to-live (in hours)\
                          for the job to grab a glidein')
        
        # Transfers
        parser.add('--nginx',action='store_true',help='Use nginx?')

        # Condor options
        parser.add('--request_memory',default=8000,help='Amount of memory (MB) to use for processing.\
                                        Default (8000) is set for finalcut on fermigrid-ce nodes. For \
                                        supercal on fermigrid-ce nodes try 32000.')
        parser.add('--request_disk',default=90000000,help='Amount of disk space (MB) to use for \
                                        processing. Default (90000000) is set for finalcut on \
                                        fermigrid-ce nodes. For supercal on fermigrid-ce nodes try \
                                        200000000.')
        parser.add('--request_cpus',default=1,help='# of cpus to use for processing. Default (1) is \
                                        set for finalcut on fermigrid-ce nodes.')
        
        return parser

class SuperNova(PipeArgs):

    def cmdline(self):
        parser = super(SuperNova,self).argument_parser()

        # Science arguments
        parser.add('--triplet',help='A single triplet formated as "nite,field,filter" (e.g. "20160114,C3,g")')
        parser.add('--list',help='File of line-separated triplets (no commas)')
        # Reasonable certain we don't want this
        # parser.add('--exptag',help='Grab all expnums with given tag in exposuretag table')
        parser.add('--calnite',help='bias/flat calibration nite/niterange,\
                                          i.e., 20151020 or 20151020t1030')
        parser.add('--calrun',help='bias/flat calibration run, i.e., r1948p03')
        parser.add('--caltag',help='Tag in OPS_PROCTAG to use if you \
                         calnite/calrun not specified')

        args = parser.parse_args()

        return args


class MultiEpoch(PipeArgs):

    def cmdline(self):
        parser = super(MultiEpoch,self).argument_parser()
        
        parser.add('--after_merge',action='store_true',help='Run in mode to directly insert\
                            objects into SE_OBJECT table')
        # Science arguments
        parser.add('--tile',help='A single tile or comma-separated list of tiles')
        parser.add('--list',help='File of line-separated tiles')
        parser.add('--proctag',help='Tag of processed expnums (proctag table) to use for coaddition')
        parser.add('--nthreads',default=8,help='Amount of parallelization')
        parser.add('--bands',default='g,r,i,z,Y')
        parser.add('--det_bands',default='r,i,z')
        parser.add('--single_chip',action='store_true')
        parser.add('--coadd_id',help='pfw_attempt_id of coadd for meds stand-alone')
        args = parser.parse_args()

        return args
       

class WideField(PipeArgs):

    def cmdline(self):
        parser = super(WideField,self).argument_parser()
        
        parser.add('--after_merge',action='store_true',help='Run in mode to directly insert\
                            objects into SE_OBJECT table')
        parser.add('--count',action='store_true',help='print number exposures found') 
       # Science arguments
        parser.add('--expnum',help='A single expnum or comma-separated list of expnums')
        parser.add('--list',help='File of line-separated expnums')
        parser.add('--exptag',help='Grab all expnums with given tag in exposuretag table')
        parser.add('--calnite',help='bias/flat calibration nite/niterange,\
                                          i.e., 20151020 or 20151020t1030')
        parser.add('--calrun',help='bias/flat calibration run, i.e., r1948p03')
        parser.add('--caltag',help='Tag in OPS_PROCTAG to use if you \
                         calnite/calrun not specified')
       
        # Exposure query for args.nite
        parser.add('--propid',help="Propid in exposure table to filter expnums \
                        on by nite")
        parser.add('--program',help="Programs in \
                        exposure table to filter expnums on by nite")
        parser.add('--process_all',action='store_true',help="Ignore propid and program when processing \
                        by nite.")
        parser.add('--check_logs',action='store_true', help="Check log files for failed exposures")
        parser.add('--interactive', action='store_true', help="Check logs with interactive interface")

        args = parser.parse_args()

        return args

class NitelyCal(PipeArgs):

    def cmdline(self):
        parser = super(NitelyCal,self).argument_parser()

        # Science arguments
        parser.add('--biaslist',help='list of line-separated bias expnums')
        parser.add('--flatlist',help='list of line-separated flat expnums')
        parser.add('--minnite',help='to create a supercal or many precals specify minnite\
                         along with maxnite')
        parser.add('--maxnite',help='to create a supercal or many precals specify maxnite\
                         along with minnite')
        parser.add('--combine',action='store_true',help='combine all exposures found into one submit')
        parser.add('--count',action='store_true',help='print number of calibrations found')
        parser.add('--bands',default='u,g,r,i,z,Y,VR',help='Bands to process')
        parser.add('--min_per_sequence',type=int,default=5,help='minimun number of exposures per band')
        parser.add('--max_num',type=int,default=150,help='maximum number of exposures per obstype and band')
        args = parser.parse_args()

        return args

class HostName(PipeArgs):

    def cmdline(self):
        parser = super(HostName,self).argument_parser()
        args = parser.parse_args()

        return args

class PreBPM(PipeArgs):

    def cmdline(self):
        parser = super(PreBPM,self).argument_parser()
        
        # Science arguments
        parser.add('--expnum',help='A single expnum or comma-separated list of expnums')
        parser.add('--list',help='File of line-separated expnums')
        parser.add('--exptag',help='Grab all expnums with given tag in exposuretag table')
        parser.add('--calnite',help='bias/flat calibration nite/niterange,\
                                          i.e., 20151020 or 20151020t1030')
        parser.add('--calrun',help='bias/flat calibration run, i.e., r1948p03')
        parser.add('--caltag',help='Tag in OPS_PROCTAG to use if you \
                         calnite/calrun not specified')
       
        args = parser.parse_args()

        return args

class PhotoZ(PipeArgs):

    def cmdline(self):
        parser = super(PhotoZ,self).argument_parser()
        
        # Science arguments
        parser.add('--tile')
        parser.add('--num_chunks',help='Total number of chunks')
        parser.add('--chunk_size',help='Number of tiles per chunk')
        parser.add('--n_jobs',default=8,help='Number of cores to run bpz')
        parser.add('--mof_table',default='nsevilla.y3a2_mof_tmp',help='MOF table to query on')
        parser.add('--list',help='File of line-separated tiles')
        parser.add('--proctag',help='Tag of processed expnums (proctag table) to use for coaddition')
        parser.add('--nthreads',default=8,help='Amount of parallelization')
        parser.add('--bands',default='g,r,i,z,Y')
        parser.add('--det_bands',default='r,i,z')
        args = parser.parse_args()

        return args
       

