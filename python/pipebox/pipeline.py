import os
import sys
import datetime
import time
import pandas as pd
import numpy as np
import string
from pipebox import pipequery,pipeargs,pipeutils,jira_utils,nitelycal_lib, reqnum_utils

class PipeLine(object):
    # Setup key arguments and environment here instead of write_*.sh
    if not os.getenv('PIPEBOX_WORK') or not os.getenv('PIPEBOX_DIR'):
        print("Please set $PIPEBOX_DIR & $PIPEBOX_WORK in your environment!")
        sys.exit(1)
    else:
        pipebox_work = os.environ['PIPEBOX_WORK']
        pipebox_dir = os.environ['PIPEBOX_DIR']

    def update_args(self,args):
        """ Update pipeline's arguments with template paths"""

        args.pipebox_dir,args.pipebox_work=self.pipebox_dir,self.pipebox_work
        args.submit_time = datetime.datetime.now()
        
        if self.args.ignore_jira:
            if not self.args.reqnum or not self.args.jira_parent:
                print("Must specify both --reqnum and --jira_parent to avoid using JIRA!")
                sys.exit(1)
        else:
            if not self.args.jira_user:
                self.args.jira_user = jira_utils.get_jira_user()
        
        # Format RA and Dec if given
        if self.args.RA or self.args.Dec:
            if not (self.args.RA and self.args.Dec):
                print("Must specify both RA and Dec.")
                sys.exit(1)

        for a in ['RA','Dec','niterange','eups_stack']:
            if getattr(args,a):
                if len(getattr(args,a)[0]) > 1:
                    setattr(args,a,getattr(args,a)[0])
                else:
                    setattr(args,a,getattr(args,a)[0][0].split())
        
        # Setting niterange
        if self.args.nite and self.args.niterange:
            print("Warning: Both nite and niterange are specified. Only nite will be used.")
        if self.args.nite:
            self.args.nitelist = self.args.nite.strip().split(',')
        if self.args.niterange:
            self.args.nitelist = pipeutils.create_nitelist(self.args.niterange[0],self.args.niterange[1]) 
        # If ngix -- cycle trough server's list
        if self.args.nginx:
            self.args.nginx_server = pipeutils.cycle_list_index(index,['desnginx', 'dessub'])
        if args.configfile: 
            if '/' in args.configfile:
                pass
            else:
                args.configfile = os.path.join(os.getcwd(),args.configfile) 

        # Checking if exclude list is a comma-separated list of line-separated file
    
        if args.exclude_list:
            exclude_file = os.path.isfile(args.exclude_list)
            if exclude_file:
                args.exclude_list =  list(pipeutils.read_file(args.exclude_list))
            else:
                try: 
                    args.exclude_list = args.exclude_list.split(',')
                    dig = args.exclude_list[0]
                except IOError:
                   print("{0} does not exist!".format(args.exclude_list))
       
        # Setting template path(s) 
        if args.decade:
            campaign_path = "pipelines/%s/DECADE/%s" % (args.pipeline,args.campaign)
        else:
            campaign_path = "pipelines/%s/%s" % (args.pipeline,args.campaign)

        if args.template_name:
            args.submit_template_path = os.path.join(campaign_path,args.template_name)
        else:
            args.submit_template_path = os.path.join(campaign_path,
                                        "{0}_submit_template.des".format(args.pipeline))
        args.rendered_template_path = []

    def prepare_submission(self, name, group,columns):
        # Setting jira parameters
        if not self.args.ignore_jira:
            self.args.reqnum, self.args.jira_parent= group['reqnum'].unique()[0],group['jira_parent'].unique()[0]

        self.args.unitname = group['unitname'].unique()[0]
        if self.args.pipeline != 'multiepoch' and  self.args.pipeline != 'photoz':
            self.args.band = group['band'].unique()[0]
        # Finding epoch of given data
        if self.args.epoch:
            self.args.epoch_name = self.args.epoch
        else:
            if self.args.pipeline == 'widefield':
                firstexpnum = group['expnum'].unique()[0]
                self.args.epoch_name = self.args.cur.find_epoch(firstexpnum, decade=self.args.decade)
            elif self.args.pipeline != 'multiepoch' and self.args.pipeline != 'photoz':
                firstexpnum = group['firstexp'].unique()[0]
                self.args.epoch_name = self.args.cur.find_epoch(firstexpnum, decade=self.args.decade)
            elif self.args.pipeline == 'prebpm':
                firstexpnum = group['expnum'].unique()[0]
                self.args.epoch_name = self.args.cur.find_epoch(firstexpnum, decade=self.args.decade)
            else:
                self.args.epoch_name = firstexpnum = None
        if self.args.epoch_name:
            self.args.cal_df = self.args.cur.get_cals_from_epoch(self.args.epoch_name,
                                                                  band = self.args.band,
                                                                  campaign = self.args.campaign,
                                                                  decade=self.args.decade)
        # Adding column values to args
        for c in columns:
            setattr(self.args,c, group[c].unique()[0])

        #Add filename base, useful for NIR campaign, for which filename does not correspond to expnum
        if self.args.campaign=='NIR':
            self.args.nirfilename = group.filename.unique()[0].split("_st.")[0]

        # Making output directories and filenames
        if self.args.out:
            if not os.path.isdir(self.args.out):
                os.makedirs(self.args.out)
            self.args.output_dir = self.args.out
        else:
            req_dir = 'r%s' % self.args.reqnum
            self.args.output_dir = os.path.join(self.args.pipebox_work,req_dir)
            if not os.path.isdir(self.args.output_dir):
                os.makedirs(self.args.output_dir)
            
        # Creating output name
        output_name_suffix = "r%s_%s_%s_rendered_template.des" % \
                            (self.args.reqnum,self.args.target_site,self.args.pipeline)
        str_base = []

        for i,k in enumerate(self.args.output_name_keys):
            st = "%s" % getattr(self.args,k)
            str_base.append(st)
        output_name_base = '_'.join(str_base)
        output_name = output_name_base + '_' + output_name_suffix
        output_path = os.path.join(self.args.output_dir,output_name)
        self.args.submitfile = output_path


        # Writing template
        pipeutils.write_template(self.args.submit_template_path,output_path,self.args)
        self.args.rendered_template_path.append(output_path)
        if not self.args.savefiles:
            #super(self.__class__,self).submit(self.args)
            # Make comment in JIRA
            if  self.args.ignore_jira==False and self.args.assign_reqnum==False:
                connected = False
                while not connected:
                    num_retry = 1
                    try:
                        con=jira_utils.get_con(self.args.jira_section)
                        connected = True
                    except:
                        print("JIRA Connection Error...Retry #{num}".format(num=num_retry))
                        time.sleep(10)
                        connected = False
                        if num_retry == 4:
                            print("Reached 4 JIRA connection attempts. Quitting...")
                            break
                        num_retry += 1

                if not jira_utils.does_comment_exist(con,reqnum=self.args.reqnum):
                    jira_utils.make_comment(con,datetime=datetime.datetime.now(),
                                            reqnum=self.args.reqnum)
        
    def make_templates(self,columns=[],groupby=None):
        """ Loop through dataframe and write submitfile for each exposures"""

           
        if self.args.ignore_processed:
            # Check what was processed and drop it from input dataframe
            for uname, gdf in self.args.dataframe.groupby(by=groupby, sort=False):
                if self.args.cur.check_submitted(uname,gdf['reqnum'].unique()[0]):
                    print("Unit %s is already processd under reqnum=%i and will be ignored" % (uname, int(gdf['reqnum'].unique()[0])))
                    self.args.dataframe = self.args.dataframe[self.args.dataframe['unitname']!=uname]

        runsites = self.args.target_site.split(",")
        qsizes = self.args.queue_size.split(",")
        
        if self.args.total_queue:
            desstat_user = None
            desstat_reqnum = None
        else:
            desstat_user = self.args.jira_user
            desstat_reqnum = self.args.reqnum        

        # Updating args for each row
        its = 0 # index for the first priority site
        for uname, gdf in self.args.dataframe.groupby(by=groupby, sort=False):
            # Check if unit was already processed

            # Check if there is a spot in a queue to submit
            submitted = False
            while not submitted:
                if pipeutils.less_than_queue(pipeline=self.args.desstat_pipeline,reqnum=desstat_reqnum,
                                         user=desstat_user,queue_size=qsizes[its],runsite=runsites[its]):
                    self.args.target_site = runsites[its]
                    super(self.__class__,self).prepare_submission(uname, gdf, columns)
                    if not self.args.savefiles: 
                        self.args.unitname,self.args.attnum = pipeutils.submit_command(self.args.submitfile,wait=float(self.args.wait))
                    submitted = True
                    pipeutils.rename_file(self.args)
                else:
                    # The queue is full
                    print("The %s is full." % runsites[its] )
                    if len(runsites) > 1:
                        if runsites[its] != runsites[-1]:
                            its = its+1
                        else:
                            its=0
                            print("Sleeping for 1 minute(s) before checking queues again")
                            time.sleep(60)
                    else:
                        print("Sleeping for 1 minute(s) before checking queues again")
                        time.sleep(60)
           

        if self.args.auto:
            if not self.args.rendered_template_path: 
                print("No new data found on %s..." % datetime.datetime.now())
            else: print("%s data found on %s..." % (len(self.args.rendered_template_path),
                                                         datetime.datetime.now()))

        if self.args.savefiles:
            super(self.__class__,self).save(self.args)

    
    def ticket(self,args,groupby='nite'):
        """ Create  JIRA ticket for each group specified"""
        try:
            args.dataframe
        except:
            print("Must specify input data!")
            sys.exit(1)
        args.dataframe['user'] = args.jira_user
        
        group = args.dataframe.groupby(by=[groupby])

        for name,vals in group:
            # create JIRA ticket per nite and add jira_id,reqnum to dataframe
            index = args.dataframe[args.dataframe[groupby] == name].index
          
            if args.jira_summary:
                jira_summary = args.jira_summary
            else:
                jira_summary = str(name)
            if args.reqnum:
                reqnum = args.reqnum
            else:
                reqnum = None
            if args.jira_parent:
                jira_parent = args.jira_parent
            else:
                jira_parent = None

            if args.ignore_jira:
                new_reqnum,new_jira_parent = (reqnum,jira_parent)
            elif args.assign_reqnum:
                new_reqnum, new_jira_parent = reqnum_utils.create_ticket(args.jira_user,
                                              summary=jira_summary,
                                              ticket=reqnum,
                                              parent=jira_parent,
                                              use_existing=True)
            else:
                # Create JIRA ticket
                new_reqnum,new_jira_parent = jira_utils.create_ticket(args.jira_section,args.jira_user,
                                              description=args.jira_description,
                                              summary=jira_summary,
                                              ticket=reqnum,parent=jira_parent,
                                              use_existing=True)
            
            # Update dataframe with reqnum, jira_id
            # If row exists replace value, if not insert new column/value
            try:
               args.dataframe.loc[index,('reqnum')] = new_reqnum
            except:
               args.dataframe.insert(len(args.dataframe.columns),'reqnum',None)
               args.dataframe.loc[index,'reqnum'] = new_reqnum
            try:
               args.dataframe.loc[index,('jira_parent')] = new_jira_parent
            except:
               args.dataframe.insert(len(args.dataframe.columns),'jira_parent',None)
               args.dataframe.loc[index,'jira_parent'] = new_jira_parent

        return args.dataframe        
    
    def auto(self,args):
        """ Sets up cronfile if necessary and runs auto-submit routine for given pipeline"""
        # Set crontab path
        cron_template_path = os.path.join('scripts',
                                    "cron_{0}_autosubmit_template.sh".format(args.pipeline))
        cron_submit_path = os.path.join(args.pipebox_work,
                                    "cron_{0}_autosubmit_rendered_template.sh".format(args.pipeline))
        if args.savefiles:
            # Writing template
            pipeutils.write_template(cron_template_path,cron_submit_path,args)
            os.chmod(cron_submit_path, 0o755)
            pipeutils.print_cron_info(args.pipeline,site=args.target_site,
                                                   pipebox_work=args.pipebox_work,
                                                   cron_path=cron_submit_path)

    def save(self,args):
        bash_template_path = os.path.join("scripts","submitme_template.sh")
        # Writing bash submit scripts
        reqnum_count = len(args.dataframe.groupby(by=['reqnum']))
        if reqnum_count > 1:
            bash_script_name = "submitme_%s_%s.sh" % (datetime.datetime.now().strftime('%Y-%m-%dT%H:%M'),
                                                          args.target_site)
        else:
            bash_script_name = "submitme_%s_%s.sh" % (args.reqnum,args.target_site)
        bash_script_path= os.path.join(args.output_dir,bash_script_name)

        pipeutils.write_template(bash_template_path,bash_script_path,args)
        os.chmod(bash_script_path, 0o755)
        pipeutils.print_submit_info(args.pipeline,site=args.target_site,
                                               eups_stack=args.eups_stack,
                                               submit_file=bash_script_path) 


class SuperNova(PipeLine):

    def __init__(self):
        """ Initialize arguments and configure"""

        # Setting global parameters
        self.args = pipeargs.SuperNova().cmdline()
        self.args.pipebox_dir,self.args.pipebox_work=self.pipebox_dir,self.pipebox_work
        self.args.pipeline = self.args.desstat_pipeline = "sne"
        self.args.output_name_keys = ['nite','field','band']

        super(SuperNova,self).update_args(self.args)         
        self.args.cur = pipequery.SuperNova(self.args.db_section)
        
        # If auto-submit mode on
        if self.args.auto:
            self.args.ignore_processed=True
            pipeutils.stop_if_already_running('submit_{0}.py'.format(self.args.pipeline))
            self.args.nite = self.args.cur.get_max_nite()
            print(self.args.nite)
            self.args.nitelist = self.args.nite.split(',')
        if self.args.resubmit_failed:
            self.args.ignore_processed=False
            self.args.triplet_list = self.args.cur.get_failed_triplets(self.args.nitelist,int(self.args.resubmit_max))
            self.args.dataframe = pd.DataFrame(self.args.triplet_list,columns=['nite','field','band'])
        elif self.args.nite:
            self.args.triplet_list = self.args.cur.get_triplets_from_nite(self.args.nitelist)
            self.args.dataframe = pd.DataFrame(self.args.triplet_list,columns=['nite','field','band'])
        elif self.args.triplet:
            self.args.triplet_list = np.array(self.args.triplet.split(',')).reshape([-1,3])
            self.args.dataframe = pd.DataFrame(self.args.triplet_list,columns=['nite','field','band'])
            
        elif self.args.list:
            self.args.triplet_list = np.array(string.join(pipeutils.read_file(self.args.list)).split(' ')).reshape([-1,3])
            self.args.dataframe = pd.DataFrame(self.args.triplet_list,columns=['nite','field','band'])
        elif self.args.csv:
            self.args.dataframe = pd.read_csv(self.args.csv,sep=self.args.delimiter)
            self.args.dataframe.columns = [col.lower() for col in self.args.dataframe.columns]
            self.args.triplet_list = np.array(self.args.dataframe[['nite','field','band']].values)


# Making sure field name are formatted correctly C2 -> SN-C2
        for num in range(self.args.dataframe['field'].size):
          self.args.dataframe['field'][num] ='SN-'+self.args.dataframe['field'][num][-2:]

        nrows=len(self.args.dataframe)
        self.args.dataframe['expnums']=np.zeros(nrows, dtype=str)
        self.args.dataframe['firstexp']=np.zeros(nrows, dtype=str)
        self.args.dataframe['unitname']=np.zeros(nrows, dtype=str)
        self.args.dataframe['single']=np.ones(nrows, dtype=bool)
        self.args.dataframe['fringe']=np.zeros(nrows, dtype=bool)
        self.args.dataframe['ccdnum']=np.zeros(nrows, dtype=str)
        self.args.dataframe['seqnum']=np.ones(nrows, dtype=int)
        self.args.dataframe = self.args.cur.update_df(self.args.dataframe)
        self.args.dataframe = self.args.dataframe.fillna(False)

class MultiEpoch(PipeLine):

    def __init__(self):
        """ Initialize arguments and configure"""
        # Setting global parameters
        self.args = pipeargs.MultiEpoch().cmdline()
        self.args.pipeline = self.args.desstat_pipeline = "multiepoch"

        super(MultiEpoch,self).update_args(self.args)
        self.args.output_name_keys = ['tile']
       
        self.args.cur = pipequery.MultiEpoch(self.args.db_section)

        # Checking processing tag and setting default
        if not self.args.proctag:
            self.args.proctag = self.args.campaign.upper() + '_FINALCUT'
            if self.args.cur.check_proctag(self.args.proctag):
                pass
            else:
                print("{tag} does not exist! Please specify proper proctag...".format(tag=self.args.proctag))
                sys.exit()
 
        # Creating dataframe from tiles
        if self.args.resubmit_failed:
            self.args.ignore_processed=False
            self.args.tile_list = self.args.cur.get_failed_tiles(self.args.reqnum,int(self.args.resubmit_max))
            if self.args.tile_list:
                self.args.dataframe = pd.DataFrame(self.args.tile_list,columns=['tile'])
            else:
                print('No tiles left to submit...')
                sys.exit()
        elif self.args.tile:
            self.args.tile_list = self.args.tile.split(',')
            self.args.dataframe = pd.DataFrame(self.args.tile_list,columns=['tile'])
        elif self.args.list:
            self.args.tile_list = list(pipeutils.read_file(self.args.list))
            self.args.dataframe = pd.DataFrame(self.args.tile_list,columns=['tile'])
        elif self.args.csv:
            self.args.dataframe = pd.read_csv(self.args.csv,sep=self.args.delimiter)
            self.args.dataframe.columns = [col.lower() for col in self.args.dataframe.columns]
            self.args.tile_list = list(self.args.dataframe['tile'].values)
        elif self.args.RA and self.args.Dec:
            self.args.tile_list = self.args.cur.get_tiles_from_radec(self.args.RA, self.args.Dec)
            self.args.dataframe = pd.DataFrame(self.args.tile_list, columns=['tile'])

        # Update dataframe for each exposure and add band,nite if not exists
        try:
            self.args.dataframe = self.args.cur.update_df(self.args.dataframe)
            self.args.dataframe = self.args.dataframe.fillna(False)
        except: 
            pass


class WideField(PipeLine):

    def __init__(self):
        """ Initialize arguments and configure"""
        # Setting global parameters
        self.args = pipeargs.WideField().cmdline()
        self.args.pipeline = "widefield"
        if 'N' in self.args.campaign and self.args.campaign != 'NIR':
            self.args.desstat_pipeline = "firstcut"
        else:
            self.args.desstat_pipeline = "finalcut" 

        super(WideField,self).update_args(self.args)
        self.args.output_name_keys = ['nite','expnum','band']#,'filename']
        self.args.cur = pipequery.WideField(self.args.db_section)
        if not self.args.propid:
            self.args.propid = self.args.cur.get_propids()
        else:   
            self.args.propid = [self.args.propid]
 
        # If auto-submit mode on
        if self.args.auto:
            #self.args.ignore_processed=True
            pipeutils.stop_if_already_running('submit_{0}.py'.format(self.args.pipeline))
            
            try:
                if self.args.db_section=='db-decade':
                    p_tab = self.args.cur.get_expnums_from_auto_queue(project='DEC')
                else:
                    p_tab = self.args.cur.get_expnums_from_auto_queue()
                self.args.expnum = ','.join([str(e) for e in p_tab['expnum'].values.tolist()])
            except:
                print("{time}: No exposures found!".format(time=datetime.datetime.now()))
                sys.exit(0)
            
            if self.args.resubmit_failed:
                self.args.reqnum = jira_utils.get_reqnum_from_nite(self.args.jira_parent,
                                                                   self.args.nite)

            """
            if not self.args.calnite:
                precal = self.args.cur.find_precal(self.args.nite,threshold=7,override=True,
                                                   tag=self.args.caltag)
                self.args.calnite,self.args.calrun = precal[0],precal[1]
            """


        # Creating dataframe from exposures - this dataframe will have one columns with number of exposures
        if self.args.resubmit_failed:
            self.args.ignore_processed=False
            self.args.exposure_list = self.args.cur.get_failed_expnums(self.args.reqnum,int(self.args.resubmit_max))
            self.args.dataframe = pd.DataFrame(self.args.exposure_list,columns=['expnum'])
        elif self.args.exptag:
            self.args.exposure_list = self.args.cur.get_expnums_from_tag(self.args.exptag)
            self.args.dataframe = pd.DataFrame(self.args.exposure_list,columns=['expnum','tag']).sort_values(by=['tag','expnum'],ascending=True)
        elif self.args.expnum:
            self.args.exposure_list = self.args.expnum.split(',')
            self.args.dataframe = pd.DataFrame(self.args.exposure_list,columns=['expnum'])
        elif self.args.nite or self.args.niterange:
            exposures = self.args.cur.get_expnums_from_nites(self.args.nitelist,propid=self.args.propid,
                                process_all=self.args.process_all)
            if not exposures:
                print("No exposures found for given nite. Please check nite.")
                sys.exit(1)
            self.args.exposure_list = [expnum for expnum in exposures]
            self.args.dataframe = pd.DataFrame(self.args.exposure_list,columns=['expnum'])
        elif self.args.list:
            self.args.exposure_list = list(pipeutils.read_file(self.args.list))
            self.args.dataframe = pd.DataFrame(self.args.exposure_list,columns=['expnum'])
        elif self.args.csv:
            self.args.dataframe = pd.read_csv(self.args.csv,sep=self.args.delimiter)
            self.args.dataframe.columns = [col.lower() for col in self.args.dataframe.columns]
            self.args.exposure_list = list(self.args.dataframe['expnum'].values)
        elif self.args.RA and self.args.Dec:
            self.args.exposure_list = self.args.cur.get_expnums_from_radec(self.args.RA, self.args.Dec)
            self.args.dataframe = pd.DataFrame(self.args.exposure_list, columns=['expnum'])
        
        if self.args.check_logs:
            interactive = self.args.interactive
            self.args.dataframe = self.args.cur.check_log_files(self.args.dataframe, interactive=interactive)
    
        # Remove unwanted exposures 
        if self.args.exclude_list:
            self.args.dataframe = self.args.dataframe[~self.args.dataframe.expnum.isin(self.args.exclude_list)]
        
        # Update dataframe for each exposure and add band,nite if not exists
        try:
            self.args.dataframe = self.args.cur.update_df(self.args)
            self.args.dataframe = self.args.dataframe.fillna(False)
        except: 
            pass
        #try:
        #    if not self.args.dataframe:
        #        print( "No new exposures found in DB!")
        #        sys.exit(1)
        #except:
        #    print( "No exposures found in DB!")
        #    sys.exit(1)
        print(self.args.dataframe)
#        exit()     
        if self.args.count:
            print("Data found in database:")
         
            self.args.cur.count_by_obstype(self.args.nitelist)
            print("\nData to be processed: %s" % ','.join(self.args.nitelist))
            grouped = self.args.dataframe.groupby(by=['obstype','band']).agg(['count'])['expnum']
            print(grouped)
            sys.exit(0)

        if self.args.auto:
            self.args.dataframe = pd.merge(self.args.dataframe, p_tab, on=['expnum'], how='inner')


class NitelyCal(PipeLine):

    def __init__(self):
        """ Initialize arguments and configure"""
        self.args = pipeargs.NitelyCal().cmdline()
        self.args.pipeline = "nitelycal"

        super(NitelyCal,self).update_args(self.args)
        self.args.cur = pipequery.NitelyCal(self.args.db_section)
        self.args.bands = self.args.bands.strip().split(',') 
        self.args.output_name_keys = ['niterange']
        # If auto-submit mode on
        if self.args.auto:
            self.args.ignore_processed=True
            pipeutils.stop_if_already_running('submit_{0}.py'.format(self.args.pipeline))
            self.args.nite = self.args.cur.get_max_nite()[1] 

        if (self.args.maxnite or self.args.minnite) and self.args.niterange:
            print('Warning: if specifying minnite and/or maxnite, do not use niterange') 
            sys.exit()

        # Create remaining list of nites if necessary
        self.args.calculate_nites = False
        if self.args.nite:
            if len(self.args.nitelist) == 1:
                self.args.calculate_nites = True
        if self.args.maxnite and not self.args.minnite:
            self.args.nitelist = self.args.maxnite.split(',')
            self.args.calculate_nites = True
        elif self.args.minnite and not self.args.maxnite:
            self.args.nitelist = self.args.minnite.split(',')
            self.args.calculate_nites = True
        elif self.args.minnite and self.args.maxnite:
            self.args.nitelist = pipeutils.create_nitelist(self.args.minnite,self.args.maxnite)

        # For each use-case create bias/flat list and dataframe
        if self.args.biaslist and not self.args.flatlist:
            # create biaslist from file
            self.args.bias_list = list(pipeutils.read_file(self.args.biaslist))
            self.args.bias_df = pd.DataFrame(self.args.bias_list,columns=['expnum'])
            self.args.bias_df['obstype'] = 'zero'
            self.args.nitelist = self.args.cur.get_nites(self.args.bias_list)

            cal_query = self.args.cur.get_cals(self.args.nitelist,exclude='B')
            self.args.flat_df = nitelycal_lib.create_clean_df(cal_query)

            self.args.dataframe = pd.concat([self.args.flat_df[['expnum','obstype']],self.args.bias_df],ignore_index=True)

            self.args.cur.update_df(self.args.dataframe)

        if self.args.flatlist and not self.args.biaslist:
            # create flatlist from file
            self.args.flat_list = list(pipeutils.read_file(self.args.flatlist))
            self.args.flat_df = pd.DataFrame(self.args.flat_list,columns=['expnum'])
            self.args.flat_df['obstype'] = 'dome flat'
            self.args.nitelist = self.args.cur.get_nites(self.args.flat_list)

            cal_query = self.args.cur.get_cals(self.args.nitelist,exclude='F')
            self.args.bias_df = nitelycal_lib.create_clean_df(cal_query)

            self.args.dataframe = pd.concat([self.args.flat_df,self.args.bias_df[['expnum','obstype']]],ignore_index=True)

            self.args.cur.update_df(self.args.dataframe)

        if self.args.flatlist and self.args.biaslist:
            self.args.bias_list = list(pipeutils.read_file(self.args.biaslist))
            self.args.bias_df = pd.DataFrame(self.args.bias_list,columns=['expnum'])
            self.args.bias_df['obstype'] = 'zero'

            self.args.flat_list = list(pipeutils.read_file(self.args.flatlist))
            self.args.flat_df = pd.DataFrame(self.args.flat_list,columns=['expnum'])
            self.args.flat_df['obstype'] = 'dome flat'
            total_list = self.args.flat_list + self.args.bias_list
            self.args.nitelist = self.args.cur.get_nites(total_list)

            self.args.dataframe = pd.concat([self.args.flat_df,self.args.bias_df],ignore_index=True)

            self.args.cur.update_df(self.args.dataframe)

        if self.args.csv:
            self.args.dataframe = pd.read_csv(self.args.csv,sep=self.args.delimiter)
            self.args.dataframe.columns = [col.lower() for col in self.args.dataframe.columns]
            self.args.cur.update_df(self.args.dataframe)
            self.args.bias_list,self.args.flat_list = nitelycal_lib.create_lists(self.args.dataframe)

        if not self.args.biaslist and not self.args.flatlist and not self.args.csv:
            cal_query = self.args.cur.get_cals(self.args.nitelist)
            self.args.dataframe = nitelycal_lib.create_clean_df(cal_query)
            if self.args.combine:
                if self.args.calculate_nites:
                    _,not_enough_exp = nitelycal_lib.trim_excess_exposures(self.args.dataframe,
                                                                           self.args.bands,
                                                                           k=self.args.max_num)

                    # If not enough exposures per band +/- one day until enough are found
                    while not_enough_exp: 
                        oneday = datetime.timedelta(days=1)
                        low_nite = datetime.datetime.strptime(self.args.nitelist[0],'%Y%m%d').date()
                        high_nite = datetime.datetime.strptime(self.args.nitelist[-1],'%Y%m%d').date()
                        if self.args.nite:
                            self.args.nitelist.insert(0,str(low_nite-oneday).replace('-',''))
                            self.args.nitelist.append(str(high_nite+oneday).replace('-',''))
                        if self.args.maxnite and not self.args.minnite:
                            self.args.nitelist.insert(0,str(low_nite-oneday).replace('-',''))
                        if self.args.minnite and not self.args.maxnite:
                            self.args.nitelist.append(str(high_nite+oneday).replace('-',''))

                        cal_query = self.args.cur.get_cals(self.args.nitelist)            
                        self.args.dataframe = nitelycal_lib.create_clean_df(cal_query)
                        _,not_enough_exp = nitelycal_lib.trim_excess_exposures(self.args.dataframe,
                                                                               self.args.bands,
                                                                               k=self.args.max_num)
                self.args.niterange = str(self.args.nitelist[0]) + 't' + str(self.args.nitelist[-1])[4:]

            # Removing bands that are not specified
            self.args.dataframe = self.args.dataframe[self.args.dataframe.band.isin(self.args.bands)\
                                                      |self.args.dataframe.obstype.isin(['zero'])]

        if self.args.combine:
            self.args.desstat_pipeline = "supercal"
            self.args.niterange = str(self.args.nitelist[0]) + 't' + str(self.args.nitelist[-1])[4:]
            self.args.dataframe['niterange'] = self.args.niterange
            self.args.dataframe['unitname'] = self.args.niterange
        else:
            self.args.desstat_pipeline = "precal"
            for index,row in self.args.dataframe.iterrows():
                try:
                    self.args.dataframe.loc[index,('niterange')] = str(row['nite'])
                    self.args.dataframe.loc[index, ('unitname')] = str(row['nite'])
                except:
                    self.args.dataframe.insert(len(self.args.dataframe.columns),'niterange',None)
                    self.args.dataframe.loc[index,('niterange')] = str(row['nite'])

                    self.args.dataframe.insert(len(self.args.dataframe.columns), 'unitname', None)
                    self.args.dataframe.loc[index, ('unitname')] = str(row['nite'])
        
        # Remove unwanted exposures
        if self.args.exclude_list:
            self.args.exclude_list = [int(e) for e in self.args.exclude_list]

            self.args.dataframe = self.args.dataframe[~self.args.dataframe.expnum.isin(self.args.exclude_list)]
        if self.args.combine: 
            if not self.args.flatlist and not self.args.biaslist:
                exclude = None
            elif self.args.flatlist and not self.args.biaslist:
                exclude = 'F'
            elif self.args.biaslist and not self.args.flatlist:
                exclude = 'B'
            elif self.args.biaslist and self.args.flatlist:
                exclude = 'FB'
            self.args.dataframe,_ = nitelycal_lib.trim_excess_exposures(
                                                    self.args.dataframe,
                                                    self.args.bands,
                                                    k=self.args.max_num,
                                                    verbose= True,
                                                    exclude = exclude)
        
        # Update dataframe with lists
        try:
            self.args.dataframe.insert(len(self.args.dataframe),'bias_list',None)
            self.args.dataframe.insert(len(self.args.dataframe),'flat_list',None)
        except: pass

        for niterange,group in self.args.dataframe.groupby(by=['niterange']):
            index = group.index
            # Append bias/flat lists to dataframe
            self.args.bias_list,self.args.flat_list = nitelycal_lib.create_lists(group)
            try:
                self.args.firstexp = self.args.flat_list[0]
            except:
                self.args.firstexp = None
            self.args.bias_list = ','.join(str(i) for i in self.args.bias_list)
            self.args.flat_list = ','.join(str(i) for i in self.args.flat_list)
            self.args.dataframe.loc[index,'flat_list'] = self.args.flat_list
            self.args.dataframe.loc[index,'bias_list'] = self.args.bias_list
            self.args.dataframe.loc[index,'firstexp'] = self.args.firstexp
            self.args.dataframe.loc[index,'unitname'] = self.args.dataframe.loc[index,'niterange']
    
        # Update dataframe
        try:
            self.args.cur.update_df(self.args.dataframe)
        except:
            pass
        
        # Exit if there are not at least 5 exposures per band
        if self.args.auto:
            nitelycal_lib.is_count_by_band(self.args.dataframe,bands_to_process=self.args.bands,
                                           min_per_sequence=self.args.min_per_sequence)
        
        
        self.args.dataframe,self.args.nitelist = nitelycal_lib.find_no_data(self.args.dataframe,self.args.nitelist)
        self.args.dataframe.loc[self.args.dataframe.obstype=='zero','band'] = 'NA'
        if self.args.count:
            print("Data found in database:")
            self.args.cur.count_by_band(self.args.nitelist)
            print("\nData to be processed: %s" % ','.join(self.args.nitelist))
            nitelycal_lib.final_count_by_band(self.args.dataframe)
            sys.exit(0)

class HostName(PipeLine):
    
    def __init__(self):
        self.args = pipeargs.HostName().cmdline()
        self.args.pipeline = self.args.desstat_pipeline = "hostname"
        super(HostName,self).update_args(self.args) 
        self.args.submit_template_path = os.path.join("pipelines/{0}".format(self.args.pipeline),
                                                   "{0}_template.des".format(self.args.pipeline)) 
    def ticket(self):
        # Create JIRA ticket
        new_reqnum,new_jira_parent = jira_utils.create_ticket(self.args.jira_section,
                                          self.args.jira_user,
                                          description=self.args.jira_description,
                                          summary=self.args.jira_summary,
                                          ticket=self.args.reqnum,parent=self.args.jira_parent,
                                          use_existing=True)

        self.args.reqnum,self.args.jira_parent = new_reqnum,new_jira_parent

    def make_templates(self):
        req_dir = 'r%s' % self.args.reqnum
        self.args.output_dir = os.path.join(self.args.pipebox_work,req_dir)
        if not os.path.isdir(self.args.output_dir):
            os.makedirs(self.args.output_dir)
        output_name = "%s_r%s_%s_rendered_template.des" % (self.args.pipeline,self.args.reqnum,self.args.target_site)
        output_path = os.path.join(self.args.output_dir,output_name)
        self.args.rendered_template_path = []
        self.args.rendered_template_path.append(output_path)
        pipeutils.write_template(self.args.submit_template_path,output_path,self.args)
    
    def submit_or_save(self):
        if self.args.savefiles:
            bash_template_path = os.path.join("scripts","submitme_template.sh")
            # Current schema of writing dessubmit bash script
            bash_script_name = "submitme_%s_%s_%s.sh" % (self.args.pipeline,self.args.reqnum,
                                                         self.args.target_site)
            bash_script_path= os.path.join(self.args.output_dir,bash_script_name)
            # Write bash script
            pipeutils.write_template(bash_template_path,bash_script_path,self.args)
            os.chmod(bash_script_path, 0o755)
            pipeutils.print_submit_info(self.args.pipeline,site=self.args.target_site,
                                        eups_stack=self.args.eups_stack,
                                        submit_file=bash_script_path)

        else:
            for submitfile in self.args.rendered_template_path:
                self.args.submitfile = submitfile
                self.args.unitname,self.args.attnum = pipeutils.submit_command(submitfile,wait=float(self.args.wait))
                # Adding attnum to output_name
                pipeutils.rename_file(self.args)

class PreBPM(PipeLine):

    def __init__(self):
        """ Initialize arguments and configure"""
        # Setting global parameters
        self.args = pipeargs.PreBPM().cmdline()
        self.args.pipeline = self.args.desstat_pipeline = "prebpm"

        super(PreBPM,self).update_args(self.args)
        self.args.output_name_keys = ['nite','expnum','band']
       
        self.args.cur = pipequery.PreBPM(self.args.db_section)
        
        # Creating dataframe from exposures 
        if self.args.resubmit_failed:
            self.args.ignore_processed=False
            self.args.exposure_list = self.args.cur.get_failed_expnums(self.args.reqnum,int(self.args.resubmit_max))
            self.args.dataframe = pd.DataFrame(self.args.exposure_list,columns=['expnum'])
        elif self.args.exptag:
            self.args.exposure_list = self.args.cur.get_expnums_from_tag(self.args.exptag)
            self.args.dataframe = pd.DataFrame(self.args.exposure_list,columns=['expnum','tag']).sort_values(by=['tag','expnum'],ascending=True)
        elif self.args.expnum:
            self.args.exposure_list = self.args.expnum.split(',')
            self.args.dataframe = pd.DataFrame(self.args.exposure_list,columns=['expnum'])
        elif self.args.list:
            self.args.exposure_list = list(pipeutils.read_file(self.args.list))
            self.args.dataframe = pd.DataFrame(self.args.exposure_list,columns=['expnum'])
        elif self.args.csv:
            self.args.dataframe = pd.read_csv(self.args.csv,sep=self.args.delimiter)
            self.args.dataframe.columns = [col.lower() for col in self.args.dataframe.columns]
            self.args.exposure_list = list(self.args.dataframe['expnum'].values)

        # Remove unwanted exposures 
        if self.args.exclude_list:
            self.args.dataframe = self.args.dataframe[~self.args.dataframe.expnum.isin(self.args.exclude_list)]
        
        # Update dataframe for each exposure and add band,nite if not exists
        try:
            self.args.dataframe = self.args.cur.update_df(self.args.dataframe)
            self.args.dataframe = self.args.dataframe.fillna(False)
        except: 
            pass

        self.args.firstexp = self.args.exposure_list[0]
        #self.args.dataframe.insert(len(self.args.dataframe.columns),'firstexp', None) 
        self.args.dataframe['firstexp'] = self.args.firstexp

class PhotoZ(PipeLine):

    def __init__(self):
        """ Initialize arguments and configure"""
        # Setting global parameters
        self.args = pipeargs.PhotoZ().cmdline()
        self.args.pipeline = self.args.desstat_pipeline = "photoz"

        super(PhotoZ,self).update_args(self.args)
        self.args.output_name_keys = ['chunk']
       
        self.args.cur = pipequery.PhotoZ(self.args.db_section)

        # Checking processing tag and setting default
        if not self.args.proctag:
            self.args.proctag = self.args.campaign.upper() + '_COADD'
            if self.args.cur.check_proctag(self.args.proctag):
                pass
            else:
                print("{tag} does not exist! Please specify proper proctag...".format(tag=self.args.proctag))
                sys.exit()
 
        # Creating dataframe from tiles
        if self.args.resubmit_failed:
            self.args.ignore_processed=False
            self.args.tile_list = self.args.cur.get_failed_chunks(self.args.reqnum,int(self.args.resubmit_max))
            if self.args.tile_list:
                self.args.dataframe = pd.DataFrame(self.args.tile_list,columns=['tile'])
            else:
                print('No tiles left to submit...')
                sys.exit()
        elif self.args.num_chunks:
            self.args.chunks = range(1,int(self.args.num_chunks) + 1)
            self.args.dataframe = pd.DataFrame(self.args.chunks,columns=['chunk'])    
            if self.args.list:
                self.args.tile_list = ','.join(list(pipeutils.read_file(self.args.list)))

        elif self.args.tile:
            self.args.tile_list = self.args.tile.split(',')
            self.args.dataframe = pd.DataFrame(self.args.tile_list,columns=['tile'])
        elif self.args.list:
            self.args.tile_list = list(pipeutils.read_file(self.args.list))
            self.args.dataframe = pd.DataFrame(self.args.tile_list,columns=['tile'])
        elif self.args.csv:
            self.args.dataframe = pd.read_csv(self.args.csv,sep=self.args.delimiter)
            self.args.dataframe.columns = [col.lower() for col in self.args.dataframe.columns]
            self.args.tile_list = list(self.args.dataframe['tile'].values)

        try:
            self.args.dataframe = self.args.cur.update_df(self.args.dataframe)
            self.args.dataframe = self.args.dataframe.fillna(False)
        except: 
            pass

