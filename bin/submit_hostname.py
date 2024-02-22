#!/usr/bin/env python

from pipebox import pipeline

# initialize and get options
print("Collecting data...")
hostname = pipeline.HostName()
args  = hostname.args

# create JIRA ticket
hostname.ticket()

# write submit file
hostname.make_templates()

# submit submit file or save submit bash script
hostname.submit_or_save()
