#!/usr/bin/env python

from pipebox import pipeline

# initialize and get options
print("Collecting data...")
prebpm = pipeline.PreBPM()
args = prebpm.args

# create JIRA ticket per nite found (default)
if args.exptag:
    prebpm.ticket(args,groupby='tag')
else:
    prebpm.ticket(args)
# write submit files and submit if necessary
# columns should only be values that change per submit (groupby)
prebpm.make_templates(columns=['nite','expnum','band'],groupby='expnum')
