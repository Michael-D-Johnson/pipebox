#!/usr/bin/env python

from pipebox import pipeutils, pipeline

# initialize and get options
print("Collecting data...")
sn = pipeline.SuperNova()
args = sn.args

# create JIRA ticket per nite found (default)
sn.ticket(args)
# write submit files and submit if necessary
# columns should only be values that change per submit (groupby)
sn.make_templates(columns=['expnums','nite','field','band','firstexp','single','fringe',
                           'seqnum','unitname','ccdnum'],groupby=['nite','field','band'])
