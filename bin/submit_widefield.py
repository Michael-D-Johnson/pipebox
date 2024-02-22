#!/usr/bin/env python

from pipebox import pipeline

# initialize and get options
print("Collecting data...")
widefield = pipeline.WideField()
args = widefield.args

# create JIRA ticket per nite found (default)
print("Creating JIRA ticket...")
if args.exptag:
    widefield.ticket(args,groupby='tag')
elif args.auto:
    widefield.ticket(args)
else:
    if not args.jira_summary:
        args.jira_summary = '_'.join([args.user,args.campaign,
                        args.desstat_pipeline,str(args.submit_time)[:10]])
    if not args.ignore_jira:
        widefield.ticket(args,groupby='user')
    else:
        widefield.ticket(args,groupby='nite')

# write submit files and submit if necessary
# columns should only be values that change per submit (groupby)
print("Creating templates and submitting (if specified)...")
widefield.make_templates(columns=['nite','expnum','band','filename'],groupby='expnum')
