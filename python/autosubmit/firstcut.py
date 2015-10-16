#! /usr/bin/env python

from os import path,environ
from sys import exit
from time import sleep,strftime
from datetime import datetime
from shlex import split
import time

from PipeBox import pipebox_utils,query,jira_utils
from opstoolkit import jiracmd,common

def make_comment(date,nite,reqnum,campaign):
    comment = """
              Autosubmit started at %s
              -----
              h3. Nite: %s
              -----
              * Reqnum: %s
              * Attnum: 01

              h5. Run Status:

              h6. Merged:
              h6. Tagged:
              h6. Datastate:

              h5. Location:  /archive_data/desarchive/OPS/firstcut/%s/%s-r%s/D00*/p01
              """ % (date,nite,reqnum,campaign,nite,reqnum)
    return comment

def run(args): 
    # Stop execution if last job is currently running
    common.stop_if_already_running()
    
    # Replace any "None" strings with Nonetype
    args = pipebox_utils.replace_none_str(args)
    
    cur = query.Firstcut(args.db_section)
    if not args.nite:
        nite = cur.get_max()[1]
        args.nite = nite
    if not args.precalnite:
        precal = cur.find_precal(args.nite,threshold=7,override=True,tag=args.precaltag)
        args.precalnite,args.precalrun = precal[0],precal[1]
        
    # Create log file if exposures found.
    logname = '%s_firstcut_submit.log' % (nite)
    log = path.join(args.pipebox_work,logname)
    logfile = open(log,'a')
    wakingup = "\n%s: Waking up. Checking if I can submit..." % datetime.now()
    logfile.write(wakingup)
       
    allexpnumnband = cur.get_expnums(nite)
    # If no exposures are found, do nothing.
    if len(allexpnumnband) == 0:
        logfile.write("\nNo exposures found. Exiting...")
        exit(0)
        
    logfile.write("\nChecking if JIRA ticket exists. If not creating one...") 
    #Check to see if Jira ticket exists, if not make one.
    
    if not args.jira_description: 
        args.jira_description = """
            Precalnite: %s
            Precalrun: %s
            """ % (args.precalnite,args.precalrun)

    args.reqnum,args.jira_parent = jira_utils.create_ticket(args.jira_section,args.jira_user,
                                              description=args.jira_description,
                                              summary=args.nite,
                                              ticket=args.reqnum,parent=args.jira_parent,
                                              use_existing=True)
        
    expnums_found = "\n%s exposures found. Seeing what I can submit...\n" % (len(allexpnumnband))
    logfile.write(expnums_found)
    # Keep only exposures that have not already been processed.
    for enb in sorted(allexpnumnband):
        args.expnum,args.band = enb[0], enb[1]
        yesorno = cur.check_submitted(args.expnum,args.reqnum) 
        count_unsubmitted = 0
        if yesorno != 0:
            continue
        else:
            # If under queue_size keep submitting jobs...
            if args.queue_size:
                not_queued = pipebox_utils.less_than_queue('firstcut',queue_size = args.queue_size)
            else:
                not_queued = pipebox_utils.less_than_queue('firstcut')
            if not_queued:
                count_unsubmitted += 1
                submitname = 'firstcut_r%s_%s_%s_%s_submit.des' % (args.reqnum,args.nite,args.expnum,args.band)
                submit = path.join(args.pipebox_work,submitname)
                if not path.isfile(submit):
                    # Add template into newly created submit file.
                    template_relpath = 'pipelines/firstcut/%s/submitwcl' % args.campaign
                    template = path.join(template_relpath,'firstcut_submit_template.des')                                    # Render template
                    pipebox_utils.write_template(template,submit,args)
                    time.sleep(5)

                # Executing dessubmit command... 
                logfile.flush()
                submit_me = pipebox_utils.submit_command(submit,logfile=logfile)
                logfile.write("\nSleeping...\n")
                # Adding comment to JIRA ticket...
                comment = make_comment(datetime.now(),args.nite,args.reqnum,args.campaign)
                key = 'DESOPS-%s' % args.reqnum
                Jira = jiracmd.Jira(args.jira_section)
                jira_tix = Jira.get_issue(key) 
                all_comments = jira_tix.fields.comment.comments
                if len(all_comments) == 0:
                   Jira.add_jira_comment(key,comment)
            
            elif not_queued is False:
                logfile.write("\nReached queue limit! Exiting...")
                exit(0)
        
    # If no unsubmitted exposures found. Print message and quit.
    if count_unsubmitted == 0:
        message = "\nNo new exposures found on %s" % datetime.now()
        logfile.write(message)
        print message
        exit(0)