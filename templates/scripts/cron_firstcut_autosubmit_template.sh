#!/bin/bash

# Source global definitions
if [ -f /etc/bashrc ]; then
    . /etc/bashrc
fi

#.desservices sections
export DES_SERVICES=/home/{{ args.user }}/.desservices.ini
export DES_DB_SECTION={{ args.db_section }}

# Grid proxy
export X509_USER_PROXY=/home/{{ args.user }}/.globus/osg/user.proxy

### Setup EUPS ENV ###
unset EUPS_DIR
unset EUPS_PATH
source /work/apps/RHEL6/dist/eups/desdm_eups_setup.sh

setup --nolocks {{ args.eups_stack[0] }} {{ args.eups_stack[1] }}
setup --nolocks jirapython 
setup --nolocks pandas
setup -r {{ args.pipebox_dir }}

export PIPEBOX_WORK={{ args.pipebox_work }}

{{ args.pipebox_dir }}/bin/write_firstcut_wcl.py --auto --campaign {{ args.campaign }} --precalnite {{ args.precalnite }} --precalrun {{ args.precalrun }} --precaltag {{ args.precaltag }} --target_site {{ args.target_site }} --archive_name {{ args.archive_name }} --jira_parent {{ args.jira_parent }} --jira_user {{ args.jira_user }} --jira_section {{ args.jira_section }} --eups_stack {{ args.eups_stack[0] }} {{ args.eups_stack[1] }} --project {{ args.project }} --db_section {{ args.db_section }} --queue_size {{ args.queue_size }}
