#!/usr/bin/env python

import os, sys
from pipebox import ask_string,check_file,write_template

args = {}
# User name
user = ask_string('Enter Username: ', default=os.environ['USER'], check=None)
args['USER'] = user
# Email
email = ask_string('Enter email: ', default='%s@illinois.edu' % user, check=None)
args['EMAIL'] = email
# DES Services file
des_services_path = ask_string('Enter DESservices path: ',
                               default=os.path.join(os.environ['HOME'],".desservices.ini"),
                               check=check_file)
args['DES_SERVICES_PATH'] = des_services_path
# Fermi ID (optional)
fermi_id = ask_string('Fermi ID: ', default='FERMI_ID', check=None)
args['FERMI_ID'] = fermi_id

# Define PIPEBOX_WORK
try:
    pipebox_work = os.environ['PIPEBOX_WORK']
except:
    pipebox_work = os.path.join(os.environ['HOME'],'PIPEBOX_WORK')
pipebox_work_path = ask_string('Enter PIPEBOX_WORK location: ', default=pipebox_work)

# user configuration template
template = "supportwcl/generic_cfg.des"
#template = os.path.join(os.environ['PIPEBOX_DIR'],"supportwcl/generic_cfg.des")

# Define the output name
user_config_file = "%s/config/%s_cfg.des" % (pipebox_work_path,user)

# Make sure directory exists
dirname = os.path.dirname(user_config_file)
if not os.path.exists(dirname):
    os.makedirs(dirname)

write_template(template,user_config_file,args)

# Add jira to the .desservices.ini
jira_user   = ask_string('DESDM Jira username: ', default=user, check=None)
jira_passwd = ask_string('DESDM Jira password: ', default='', check=None, passwd=True)

with open(des_services_path, "a") as desservices:
    desservices.write("\n")
    desservices.write("[jira-desdm]\n")
    desservices.write("user = %s\n" % jira_user)
    desservices.write("passwd = %s\n" % jira_passwd)
    desservices.write("server = https://opensource.ncsa.illinois.edu/jira/\n")
    desservices.write("\n")
    desservices.close()

print("\nDES services file:\n\t%s" % des_services_path)
print("\thas been updated with the JIRA information:\n")
print("\nConfiguration file written to:\n\t%s" % user_config_file)
print("\nMake sure you setup PIPEBOX_WORK environmental variable:")
print("\texport PIPEBOX_WORK=%s" % pipebox_work_path)
print("\tor")
print("\tsetenv PIPEBOX_WORK %s" % pipebox_work_path)
