#! /usr/bin/env python

import sys
from jira import JIRA
from despyserviceaccess.serviceaccess import parse

class Jira:
    def __init__(self,section):
        jiradict=parse(None,section)
        jirauser=jiradict['user']
        jirapasswd=jiradict['passwd']
        jiraserver=jiradict['server']
        jira=JIRA(options={'server':jiraserver},basic_auth=(jirauser,jirapasswd))
        self.jira = jira
        self.server = jiraserver
        self.user = jirauser

    def search_for_issue(self,parent,summary):
        jql = 'summary ~ "\\"%s\\"" and parent = "%s"' % (summary,parent)
        issue = self.jira.search_issues(jql)
        count = len(issue)
        return (issue,count)
 
    def search_for_parent(self,project,summary):
        jql = 'project = "%s" and summary ~ "%s"' % (project, summary)
        issue = self.jira.search_issues(jql)
        count = len(issue)
        return (issue,count)
   
    def get_issue(self,key):
        issue_info = self.jira.issue(key)
        return issue_info

    def create_jira_subtask(self,parent,summary,description,assignee):
        try:
            parent_issue = self.jira.issue(parent)
        except:
            warning= 'Parent issue %s does not exist!' % parent
            print(warning)
            sys.exit()

        subtask_dict = {'project':{'key':parent_issue.fields.project.key},
		    'summary': summary,
		    'issuetype':{'name':'Sub-task'},
		    'description': description,
		    'parent':{'key': parent_issue.key},
		    'assignee':{'name': assignee},
		    }	
        subtask = self.jira.create_issue(fields=subtask_dict)
        return subtask.key	

    def create_jira_ticket(self,project,summary,description,assignee):
        ticket_dict = {'project':{'key':project},
		    'summary': summary,
		    'issuetype':{'name':'Processing Request'},
		    'description': description,
		    'assignee':{'name': assignee},
		    }	
        ticket = self.jira.create_issue(fields=ticket_dict)
        return ticket.key	

    def add_jira_comment(self,issue,comment):
        self.jira.add_comment(issue,comment)

