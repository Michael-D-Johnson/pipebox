#!/usr/bin/env python

from pipebox import pipeline

# initialize and get options
print("Collecting data...")
photoz = pipeline.PhotoZ()
args = photoz.args

# create JIRA ticket per nite found (default)
if not args.jira_summary:
    args.jira_summary = '_'.join([args.user,args.campaign,
                    args.desstat_pipeline,str(args.submit_time)[:10]])
photoz.ticket(args,groupby='user')

# write submit files and submit if necessary
# columns should only be values that change per submit (groupby)
photoz.make_templates(columns=['chunk'],groupby='chunk')
