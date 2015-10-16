#!/usr/bin/env python

import os,sys
from argparse import ArgumentParser
import pandas as pd
from PipeBox import pipebox_utils,jira_utils,query,templates_dir
from autosubmit import nitelycal

def cmdline():
    # Create command line arguments
    parser = ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['manual','auto'])
    parser.add_argument('--db_section',help = "e.g., db-desoper or db-destest")
    parser.add_argument('--biaslist',help='')
    parser.add_argument('--flatlist',help='')
    parser.add_argument('--target_site',help='')
    parser.add_argument('--http_section',help='')
    parser.add_argument('--archive_name',help='')
    parser.add_argument('--schema',help='')
    parser.add_argument('--jira_parent',help='')
    parser.add_argument('--jira_description',help='')
    parser.add_argument('--jira_project',default='DESOPS',help='')
    parser.add_argument('--jira_summary',help='')
    parser.add_argument('--jira_user',help='')
    parser.add_argument('--jira_section',help='')
    parser.add_argument('--eups_product',help='')
    parser.add_argument('--eups_version',help='')
    parser.add_argument('--campaign',help='')
    parser.add_argument('--project',default='ACT',help='')
    parser.add_argument('--queue_size',help='')
    parser.add_argument("--user", action="store", default=os.environ['USER'],
                        help="username that will submit")
    parser.add_argument('--savefiles',action='store_true',help='Saves submit files to submit later.')
    parser.add_argument('--bias',help='')
    parser.add_argument('--flat',help='')
    parser.add_argument('--csv',help='')
    parser.add_argument('--delimiter',default=',',help='csv')
    parser.add_argument('--ccdnum',default=pipebox_utils.ALL_CCDS,help='')
    parser.add_argument('--reqnum',help='')
    parser.add_argument('--nite',help='')
    parser.add_argument('--maxnite')
    parser.add_argument('--minnite')
    parser.add_argument('--paramfile',help='')
    parser.add_argument('--combine',help='')

    args = parser.parse_args()
    return args

if __name__ == "__main__":
   
    args = cmdline()
    
    if args.paramfile:
        args = pipebox_utils.update_from_param_file(args)
        args = pipebox_utils.replace_none_str(args)
    
    try:
        args.pipebox_work = os.environ['PIPEBOX_WORK']
        args.pipebox_dir = os.environ['PIPEBOX_DIR']
    except:
        print "must declare $PIPEBOX_WORK"
        sys.exit(1)    

    if args.mode=='auto':
        # Set crontab path
        cron_template_path = os.path.join('scripts',"cron_nitelycal_autosubmit_template.sh")
        cron_submit_path = os.path.join(args.pipebox_work,"cron_nitelycal_autosubmit_rendered_template.sh")
        if args.savefiles:
            # Writing template
            pipebox_utils.write_template(cron_template_path,cron_submit_path,args)
            os.chmod(cron_submit_path, 0755)
            pipebox_utils.print_cron_info('nitelycal',site=args.target_site,
                                                      pipebox_work=args.pipebox_work,
                                                      cron_path=cron_submit_path)
        else:
            # Run autosubmit code directly
            # Will run once, but if put in crontab will run however you specify in cron
            nitelycal.run(args)
            pass
    
    if args.mode=='manual': 
        # For each use-case create bias/flat list and dataframe
        if args.bias: 
            args.bias_list = args.bias.split(',')
        if args.flat:
            args.flat_list =  args.flat.split(',')
        if args.biaslist:
            with open(args.biaslist) as listfile:
                args.bias_list = listfile.read().splitlines()
            args.bias_df = pd.DataFrame(args.exposure_list,columns=['expnum'])
        if args.flatlist: 
            with open(args.flatlist) as listfile:
                args.flat_list = listfile.read().splitlines()
            args.flat_df = pd.DataFrame(args.exposure_list,columns=['expnum'])
       
        args.dataframe = pd.concat([args.flat_df,args.bias_df],ignore_index=True)
        # Update dataframe for each exposure and add band,nite if not exists
        cur = query.NitelyCal(args.db_section)
        #cur.update_df(args.exposure_df) 
        if args.combine:
            # create one ticket
            args.niterange = "writerangehere"
            # Create JIRA ticket
            new_reqnum,new_jira_parent = jira_utils.create_ticket(args.jira_section,args.jira_user,
                                                  description=args.jira_description,
                                                  summary=args.niterange,
                                                  ticket=args.reqnum,parent=args.jira_parent,
                                                  use_existing=True)

        if not args.combine:
            # create  JIRA ticket for each nite found (precal-like)
            nite_group = args.exposure_df.groupby(by=['nite'])
            for nite,group in nite_group:
                # create JIRA ticket per nite and add jira_id,reqnum to dataframe
                index = args.exposure_df[args.exposure_df['nite'] == nite].index
                if not args.jira_summary: 
                    args.jira_summary = str(nite)
                if not args.reqnum:
                    try:
                        args.reqnum = str(int(args.exposure_df.loc[index,('reqnum')].unique()[1]))
                    except: 
                        args.reqnum = None
                if not args.jira_parent:
                    try:
                        args.jira_parent = args.exposure_df.loc[index,('jira_parent')].unique()[1]
                    except: 
                        args.jira_parent = None
                # Create JIRA ticket
                new_reqnum,new_jira_parent = jira_utils.create_ticket(args.jira_section,args.jira_user,
                                                  description=args.jira_description,
                                                  summary=args.jira_summary,
                                                  ticket=args.reqnum,parent=args.jira_parent,
                                                  use_existing=True)
                # Update dataframe with reqnum, jira_id
                # If row exists replace value, if not insert new column/value
                try:
                    args.exposure_df.loc[index,('reqnum')] = new_reqnum
                except: 
                    args.exposure_df.insert(index[0],'reqnum',new_reqnum)
                try:
                    args.exposure_df.loc[index,('jira_parent')] = new_jira_parent
                except: 
                    args.exposure_df.insert(index[0],'jira_parent',new_jira_parent)
    
        # Render and write templates
        campaign_path = "pipelines/nitelycal/%s/submitwcl" % args.campaign
        submit_template_path = os.path.join(campaign_path,"nitelycal_submit_template.des")
        bash_template_path = os.path.join("scripts","submitme_template.sh")
        args.rendered_template_path = []
        # Create templates for each entry in dataframe
        for index,row in args.exposure_df.iterrows():
            args.expnum,args.band,args.nite,args.reqnum= row['expnum'],row['band'],row['nite'],int(row['reqnum'])
            output_name = "%s_%s_r%s_nitelycal_rendered_template.des" % (args.expnum,args.band,args.reqnum)
            output_path = os.path.join(args.pipebox_work,output_name)
            # Writing template
            pipebox_utils.write_template(submit_template_path,output_path,args)

            if args.savefiles:
                # Current schema of writing dessubmit bash script 
                bash_script_name = "submitme_%s_%s.sh" % (args.reqnum,args.target_site)
                bash_script_path= os.path.join(args.pipebox_work,bash_script_name)
                args.rendered_template_path.append(output_path)
            else:
                # If less than queue size submit exposure
                if pipebox_utils.less_than_queue('nitelycal',args.queue_size):
                    pipebox_utils.submit_exposure(output_name)

        if args.savefiles:
            # Writing bash submit scripts
            pipebox_utils.write_template(bash_template_path,bash_script_path,args)
            os.chmod(bash_script_path, 0755)
            pipebox_utils.print_submit_info('nitelycal',site=args.target_site,
                                                        eups_product=args.eups_product,
                                                        eups_version=args.eups_version,
                                                        submit_file=bash_script_path)