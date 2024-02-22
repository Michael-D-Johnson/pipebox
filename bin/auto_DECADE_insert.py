#!/usr/bin/env python

from pipebox import pipequery

# Create db connection
pipeline = pipequery.PipeQuery('db-decade')

# Get operations propids and programs for query 
propid = pipeline.get_propids()

# Insert exposures into mjohns44.auto_queue
pipeline.insert_auto_queue(propid=propid, n=50)
