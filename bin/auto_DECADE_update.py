#!/usr/bin/env python

from pipebox import pipequery

# Create db connection
pipeline = pipequery.PipeQuery('db-decade')

# Find unitnames that have been successfully processed and update auto_queue
pipeline.update_auto_queue(project='DEC_Taiga')

