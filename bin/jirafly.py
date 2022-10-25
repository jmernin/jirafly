#!/usr/bin/env python3
######################################################################
#
# Script to enable command-line access to a JIRA project.
#
# Prerequisites
#  $ sudo -H pip install jira
#
# Sample Usage
#  $./jirafly.py --action target --server https://issues.redhat.com \
#     --username jmernin --token ********** [--password ******] --project ACME
#  $./jirafly.py --action issue-<create|delete|read> --key ACME-123
#
# References
# - https://pythonhosted.org/jira/index.html?highlight=create_issue#examples
#
# Copyright (c) 2017, James Mernin
#
######################################################################

#################################
# LIBRARIES
#################################
import urllib.request
import base64
from datetime import datetime
import json
import argparse
import sys
import os
from jira import JIRA
from jira.exceptions import JIRAError

######################################################################
# GLOBALS
######################################################################
DEBUG = 0
QUIET = 1

MYHOME           = os.environ['HOME']
CACHED_CREDS     = MYHOME + "/.jf/jira.creds"
JIRA_TEMPLATES   = MYHOME + "/.jf/templates.json"

CMD_TARGET       = "target"

CMD_ISSUE_CREATE  = "issue-create"
CMD_ISSUE_READ    = "issue-read"
CMD_ISSUE_UPDATE  = "issue-update"
CMD_ISSUE_DELETE  = "issue-delete"
CMD_ISSUE_COMMENT = "issue-comment"
CMD_ISSUE_ASSIGN  = "issue-assign"
CMD_ISSUE_UPDATE_SPRINT   = "issue-update-sprint"
CMD_ISSUE_UPDATE_EPIC     = "issue-update-epic"
CMD_ISSUE_UPDATE_REPORTER = "issue-update-reporter"
CMD_ISSUE_UPDATE_DUE_DATE = "issue-update-due-date"
CMD_ISSUE_WATCHER_ADD     = "issue-watcher-add"
CMD_ISSUE_WATCHER_REMOVE  = "issue-watcher-remove"

CMD_COMPONENT_ADD    = "component-add"
CMD_COMPONENT_REMOVE = "component-remove"
CMD_LABEL_ADD        = "label-add"
CMD_LABEL_REMOVE     = "label-remove"

CMD_TEMPLATE_CREATE = "template-create"
CMD_TEMPLATE_LIST   = "template-list"

COMMANDS = sorted([ CMD_TARGET, CMD_ISSUE_CREATE, CMD_ISSUE_READ, CMD_ISSUE_UPDATE, CMD_ISSUE_DELETE, CMD_ISSUE_COMMENT, CMD_ISSUE_ASSIGN, CMD_ISSUE_UPDATE_EPIC, CMD_ISSUE_UPDATE_SPRINT, CMD_ISSUE_UPDATE_REPORTER, CMD_ISSUE_UPDATE_DUE_DATE, CMD_ISSUE_WATCHER_ADD, CMD_ISSUE_WATCHER_REMOVE, CMD_COMPONENT_ADD, CMD_COMPONENT_REMOVE, CMD_LABEL_ADD, CMD_LABEL_REMOVE, CMD_TEMPLATE_CREATE, CMD_TEMPLATE_LIST ])

ACTION_ADD       = "add"
ACTION_REMOVE    = "remove"

PRIORITY_BLOCKER  = "Blocker"
PRIORITY_CRITICAL = "Critical"
PRIORITY_MAJOR    = "Major"
PRIORITY_MINOR    = "Minor"
PRIORITY_TRIVIAL  = "Trivial"
PRIORITIES = sorted([ PRIORITY_BLOCKER, PRIORITY_CRITICAL, PRIORITY_MAJOR, PRIORITY_MINOR, PRIORITY_TRIVIAL ])

ISSUE_TYPE_EPIC        = "Epic"
ISSUE_TYPE_BUG         = "Bug"
ISSUE_TYPE_ENHANCEMENT = "Enhancement"
ISSUE_TYPE_FEATURE     = "Feature"
ISSUE_TYPE_TASK        = "Task"
ISSUE_TYPE_SUBTASK     = "Sub-task"
ISSUE_TYPES = sorted([ ISSUE_TYPE_EPIC, ISSUE_TYPE_BUG, ISSUE_TYPE_ENHANCEMENT, ISSUE_TYPE_FEATURE, ISSUE_TYPE_TASK, ISSUE_TYPE_SUBTASK ])

######################################################################
######################################################################
##### FUNCTIONS
######################################################################
######################################################################

######################################################################
# Log stuff (to file, syslog or wherever)
######################################################################
def logit(msg):
  if DEBUG == 1:
   now = datetime.now()
   stamp = now.strftime("%Y-%m-%d %H:%M:%S")
   print ("[" + stamp + "] " + str(msg))

######################################################################
# Handle command-line arguments
######################################################################
def genParser():

  args = argparse.ArgumentParser()
  args.add_argument("--action",   required=True,  choices=COMMANDS)
  args.add_argument("--server",   required=False, default="https://issues.redhat.com" )
  args.add_argument("--username", required=False, default=None )
  args.add_argument("--password", required=False, default=None )
  args.add_argument("--token",    required=False, default=None )
  args.add_argument("--project",  required=False, default=None )
  args.add_argument("--parent",   required=False, default=None )
  args.add_argument("--summary",  required=False, default=None )
  args.add_argument("--assignee", required=False, default=None )
  args.add_argument("--reporter", required=False, default=None )
  args.add_argument("--duedate",  required=False, default=None )
  args.add_argument("--watcher",  required=False, default=None )
  args.add_argument("--message",  required=False, default=None )

  args.add_argument("--key",         required=False, default=None )
  args.add_argument("--description", required=False, default=None )
  args.add_argument("--issuetype",   required=False, choices=ISSUE_TYPES, default="Task" )
  args.add_argument("--priority",    required=False, choices=PRIORITIES, default="Major" )
  args.add_argument("--components",  required=False, default=None )
  args.add_argument("--labels",      required=False, default=None )
  args.add_argument("--template",    required=False, default=None )

  args.add_argument("-v", "--verbose", required=False, action="store_true")
  args.add_argument("-q", "--quiet",   required=False, action="store_true")
  return args

######################################################################
# ISSUE::Create
######################################################################
def doIssueCreate(jira, project, issuetype, parent, priority, summary, description, assignee, components, labels):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " PROJECT=" + str(project))

  data = {}
  fields = {}

  # Non-array/complex fields (or ones we provide a tangible default for)
  fields["project"]     = { "key": project }
  fields["issuetype"]   = { "name": issuetype }
  fields["priority"]    = { "name": priority }
  fields["summary"]     = summary
  fields["assignee"]    = { "name": assignee }

  # Other/Optional fields
  if description is not None:
    fields["description"] = description

  if components is not None:
    fields["components"] = []
    for c in components:
      fields["components"].append({ "name": c})

  if labels is not None:
    fields["labels"] = []
    for l in labels:
      fields["labels"].append(l)

  # Epics need an extra name field (which it seems needs to be specified in a custom field)
  if ISSUE_TYPE_EPIC == issuetype:
    fields["customfield_12311141"] = summary

  # Is this a sub-task (needs a parent)?
  if ISSUE_TYPE_SUBTASK == issuetype and parent is not None:
    fields["parent"] = { "key": parent }

  data["fields"] = fields
  logit(sys._getframe().f_code.co_name + "::DATA=" + str(data))

  # Try to create the issue
  try:
    issue = jira.create_issue(fields, True)
    logit(sys._getframe().f_code.co_name + "::ISSUE=" + str(issue))
  except JIRAError as e:
    print ("ERROR: Could not create issue: " + e.text)
    sys.exit(1)

  # Maybe try to add the created issue to an epic
  if ISSUE_TYPE_SUBTASK != issuetype and parent is not None:
    try:
      logit(sys._getframe().f_code.co_name + "::Adding issue to EPIC=" + str(parent))
      jira.add_issues_to_epic(parent, [issue.key])
    except JIRAError as e:
      print ("ERROR: Could not link issue to epic: " + e.text)
      sys.exit(1)

  return issue

######################################################################
# ISSUE::Read
######################################################################
def doIssueRead(jira, project, key):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " PROJECT=" + str(project) + " KEY=" + str(key))

  # Locate issue first, then delete it
  try:
    issue = jira.issue(key)
    logit(sys._getframe().f_code.co_name + "::ISSUE=" + str(issue))
  except JIRAError as e:
    print ("ERROR: Specified JIRA key does not exist: " + e.text)
    sys.exit(1)

  return issue.raw["fields"]

######################################################################
# ISSUE::Update
######################################################################
def doIssueUpdate(jira, aProject, aKey, aIssueType, aPriority, aSummary, aDescription, aReporter, aComponents, aLabels):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " PROJECT=" + str(aProject) + " KEY=" + str(aKey))

  print ("ERROR: This functionlity in unsupported at this time")
  sys.exit(1)

######################################################################
# ISSUE::Delete
######################################################################
def doIssueDelete(jira, project, key):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " PROJECT=" + str(project) + " KEY=" + str(key))

  # Locate issue first, then delete it
  try:
    issue = jira.issue(key)
    logit(sys._getframe().f_code.co_name + "::ISSUE=" + str(issue))
    issue.delete()
    print ("OK: JIRA issue deleted successfully.")
  except JIRAError as e:
    print ("ERROR: Specified JIRA key does not exist: " + e.text)
    sys.exit(1)

  return True

######################################################################
# ISSUE::Comment
######################################################################
def doIssueComment(jira, project, key, message):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " PROJECT=" + str(project) + " KEY=" + str(key) + " MESSAGE=" + str(message))

  if message is None:
    print ("ERROR: A valid message must be specified.")
    sys.exit(1)

  # Locate issue first, then add comment to it
  try:
    issue = jira.issue(key)
    logit(sys._getframe().f_code.co_name + "::ISSUE=" + str(issue))
    jira.add_comment(issue, message)
    print ("OK: Issue " + str(issue.key) + " updated successfully with comment: " + str(message))
  except JIRAError as e:
    print ("ERROR: Failed to add issue comment: " + e.text)
    sys.exit(1)

  return True

######################################################################
# ISSUE::Assign
######################################################################
def doIssueAssign(jira, project, key, assignee):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " PROJECT=" + str(project) + " KEY=" + str(key) + " ASSIGNEE=" + str(assignee))

  if assignee is None:
    print ("ERROR: A valid assignee must be specified.")
    sys.exit(1)

  # Locate issue first, then update assignee
  try:
    issue = jira.issue(key)
    logit(sys._getframe().f_code.co_name + "::ISSUE=" + str(issue))
    jira.assign_issue(issue, assignee)
    print ("OK: Issue " + str(issue.key) + " updated successfully with assignee: " + str(assignee))
  except JIRAError as e:
    print ("ERROR: Failed to update issue assignee: " + e.text)
    sys.exit(1)

  return True

######################################################################
# ISSUE::Update Epic
######################################################################
def doIssueUpdateEpic(jira, key, epic):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " KEY=" + str(key) + " EPIC=" + str(epic))

  # Locate issue first, then link it to epic
  try:
    issue = jira.issue(key)
    logit(sys._getframe().f_code.co_name + "::ISSUE=" + str(issue))
  except JIRAError as e:
    print ("ERROR: Specified issue does not exist: " + e.text)
    sys.exit(1)

  # Now try to link to our epic
  try:
    logit(sys._getframe().f_code.co_name + "::Adding issue to EPIC=" + str(epic))
    jira.add_issues_to_epic(epic, [issue.key])
    print ("OK: Issue " + str(issue.key) + " updated successfully with epic: " + str(epic))
  except JIRAError as e:
    print ("ERROR: Could not link issue to epic: " + e.text)
    sys.exit(1)

  return True

######################################################################
# ISSUE::Update Sprint
#  The value for the spring parameter must be an id, not a string.
######################################################################
def doIssueUpdateSprint(jira, key, sprint):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " KEY=" + str(key) + " SPRINT=" + str(sprint))

  # Locate issue first, then link it to epic
  try:
    issue = jira.issue(key)
    logit(sys._getframe().f_code.co_name + "::ISSUE=" + str(issue))
  except JIRAError as e:
    print ("ERROR: Specified issue does not exist: " + e.text)
    sys.exit(1)

  # Now try to link to our sprint
  try:
    logit(sys._getframe().f_code.co_name + "::Adding issue to SPRINT=" + str(sprint))
    jira.add_issues_to_sprint(sprint, [issue.key])
    print ("OK: Issue " + str(issue.key) + " updated successfully with sprint: " + str(sprint))
  except JIRAError as e:
    print ("ERROR: Could not link issue to sprint: " + e.text)
    sys.exit(1)

  return True

######################################################################
# ISSUE::Update Reporter
#  Update the reporter field for the specified issue
######################################################################
def doIssueUpdateReporter(jira, key, reporter):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " KEY=" + str(key) + " REPORTER=" + str(reporter))

  # Locate issue first, then alter it's reporter field
  try:
    issue = jira.issue(key)
    logit(sys._getframe().f_code.co_name + "::ISSUE=" + str(issue))
  except JIRAError as e:
    print ("ERROR: Specified issue does not exist: " + e.text)
    sys.exit(1)

  # Now try to alter it's reporter
  try:
    logit(sys._getframe().f_code.co_name + "::Adjusting issue to REPORTER=" + str(reporter))
    issue.update(reporter={"name": reporter})
    print ("OK: Issue " + str(issue.key) + " updated successfully with reporter: " + str(reporter))
  except JIRAError as e:
    print ("ERROR: Could not update " + str(issue.key) + " reporter: " + e.text)
    sys.exit(1)

  return True

######################################################################
# ISSUE::Update Due Date
#  Update the duedate field for the specified issue
######################################################################
def doIssueUpdateDueDate(jira, key, duedate):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " KEY=" + str(key) + " DUEDATE=" + str(duedate))

  # Locate issue first, then alter it's reporter field
  try:
    issue = jira.issue(key)
    logit(sys._getframe().f_code.co_name + "::ISSUE=" + str(issue))
  except JIRAError as e:
    print ("ERROR: Specified issue does not exist: " + e.text)
    sys.exit(1)

  # Now try to alter it's duedate
  try:
    logit(sys._getframe().f_code.co_name + "::Adjusting issue to DUEDATE=" + str(duedate))
    issue.update(duedate=str(duedate))
    print ("OK: Issue " + str(issue.key) + " updated successfully with due date: " + str(duedate))
  except JIRAError as e:
    print ("ERROR: Could not update " + str(issue.key) + " due date: " + e.text)
    sys.exit(1)

  return True

######################################################################
# ISSUE::Remove Watcher
#  Remove watcher from the specified issue
######################################################################
def doIssueWatcherRemove(jira, key, watcher):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " KEY=" + str(key) + " WATCHER=" + str(watcher))

  # Locate issue first, then update the watchers
  try:
    issue = jira.issue(key)
    logit(sys._getframe().f_code.co_name + "::ISSUE=" + str(issue))
  except JIRAError as e:
    print ("ERROR: Specified issue does not exist: " + e.text)
    sys.exit(1)

  # Now try to alter it's watchers
  try:
    logit(sys._getframe().f_code.co_name + "::Removing WATCHER=" + str(watcher))
    jira.remove_watcher(issue, watcher)
    print ("OK: Issue " + str(issue.key) + " updated successfully with watcher: " + str(watcher))
  except JIRAError as e:
    print ("ERROR: Could not update " + str(issue.key) + " watcher: " + e.text)
    sys.exit(1)

  return True

######################################################################
# ISSUE::Add Watcher
#  Add a watcher to the specified issue
######################################################################
def doIssueWatcherAdd(jira, key, watcher):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " KEY=" + str(key) + " WATCHER=" + str(watcher))

  # Locate issue first, then update the watchers
  try:
    issue = jira.issue(key)
    logit(sys._getframe().f_code.co_name + "::ISSUE=" + str(issue))
  except JIRAError as e:
    print ("ERROR: Specified issue does not exist: " + e.text)
    sys.exit(1)

  # Now try to alter it's watchers
  try:
    logit(sys._getframe().f_code.co_name + "::Adding WATCHER=" + str(watcher))
    jira.add_watcher(issue, watcher)
    print ("OK: Issue " + str(issue.key) + " updated successfully with watcher: " + str(watcher))
  except JIRAError as e:
    print ("ERROR: Could not update " + str(issue.key) + " watcher: " + e.text)
    sys.exit(1)

  return True

######################################################################
# COMPONENT::Add or Remove
#  Note the difference in JSON format between this and a label
#  (i.e. need a "name": key in component object).
######################################################################
def doComponentManage(jira, key, component, action):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " KEY=" + str(key) + " COMPONENT=" + str(component) + " ACTION=" + str(action))

  if component is None:
    print ("ERROR: A valid component value must be specified.")
    sys.exit(1)

  try:
    # Locate issue first
    issue = jira.issue(key)
    logit(sys._getframe().f_code.co_name + "::ISSUE=" + str(issue))

    # Extract current components
    components = []
    for c in issue.fields.components:
      components.append({"name": c.name})
    logit(sys._getframe().f_code.co_name + ":: EXISTING COMPONENTS=" + str(components))

    # Now, either add or remove something from this array, remembering that
    # the "component" variable is in itself an array
    if ACTION_ADD == action:
      for c in component:
        components.append({"name": c})
    if ACTION_REMOVE == action:
      for c in component:
        components.remove({"name": c})
    logit(sys._getframe().f_code.co_name + ":: NEW COMPONENTS=" + str(components))

    # And finally, write back the updated list
    issue.update(fields={"components": components})
    print ("OK: Issue components are now: " + str(issue.fields.components))
  except JIRAError as e:
    print ("ERROR: Failed to manage issue components: " + e.text)
    sys.exit(1)

  return True

######################################################################
# LABEL::Add or Remove
#  Note the difference in JSON format between this and a component
#  (i.e. no need for "name": key in a label object).
######################################################################
def doLabelManage(jira, key, label, action):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " KEY=" + str(key) + " LABEL=" + str(label) + " ACTION=" + str(action))

  if label is None:
    print ("ERROR: A valid label value must be specified.")
    sys.exit(1)

  try:
    # Locate issue first
    issue = jira.issue(key)
    logit(sys._getframe().f_code.co_name + "::ISSUE=" + str(issue))

    # Extract current label
    labels = []
    for l in issue.fields.labels:
      labels.append(l)
    logit(sys._getframe().f_code.co_name + ":: EXISTING LABELS=" + str(labels))

    # Now, either add or remove something from this array, remembering that
    # the "label" variable is in itself an array
    if ACTION_ADD == action:
      for l in label:
        labels.append(l)
    if ACTION_REMOVE == action:
      for l in label:
        labels.remove(l)
    logit(sys._getframe().f_code.co_name + ":: NEW LABELS=" + str(labels))

    # And finally, write back the updated list
    issue.update(fields={"labels": labels})
    print ("OK: Issue labels are now: " + str(issue.fields.labels))
  except JIRAError as e:
    print ("ERROR: Failed to manage issue labels: " + e.text)
    sys.exit(1)

  return True

######################################################################
# TEMPLATE::Create
######################################################################
def doTemplateCreate(jira, project, tid, suffix, assignee):
  logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira) + " PROJECT=" + str(project) + " TEMPLATE=" + str(tid) + " SUFFIX=" + str(suffix))

  # Load all available templates
  with open(JIRA_TEMPLATES) as f:
    templates = json.load(f)
  logit(sys._getframe().f_code.co_name + "::TEMPLATES=" + str(templates))

  # Fetch the template we want
  template = templates[tid]
  logit(sys._getframe().f_code.co_name + "::TEMPLATE=" + str(template))

  if assignee is None:
    assignee = ""

  # Create Parent
  #  The summary will be that of the parent, with the supplied suffix "appended".
  #  The description will be that of the parent, with the supplied suffix "inserted".
  parent = template['parent']
  logit(sys._getframe().f_code.co_name + "::PARENT=" + str(parent))
  try:
    summary = parent['summary'] + ": " + suffix
  except:
    summary = parent['summary']  # No extra summary supplied/required

  try:
    description = parent['description'] % (suffix)
  except TypeError:
    description = parent['description']  # The description probably does not contain any % formatting special characters

  if project is None:
      project = parent['project']

  # If a Standard Operating Procedure (SOP) was supplied, include that in description too.
  if parent['sop'] != "-":
    description = "%s\n\nFurther details on what this entails and why it is important are available at:\n\n* %s" % (description, parent['sop'])

  try:
    if parent["be_unique"]:
      # Search for this issue existing already
      search_string = 'project=%s and summary~"%s"' % (project, summary)
      issues = jira.search_issues(search_string)
      if len(issues):
        print ("Issue already exists with key(s): ")
        for issue in issues:
          print (issue.key)
        sys.exit(0)
  except KeyError:
    # The be_unique key does not exist, do nothing
    pass

  logit(sys._getframe().f_code.co_name + "::PARENT_SUMMARY=" + str(summary) + " PARENT_DESCRIPTION=" + str(description))
  parentIssue = doIssueCreate(jira, project, parent['type'], None, PRIORITY_MAJOR, summary, description, assignee, parent['components'], parent['labels'])
  logit(sys._getframe().f_code.co_name + "::PARENT_ISSUE=" + str(parentIssue))

  # Create Children
  for child in parent['children']:
    logit(sys._getframe().f_code.co_name + "::CHILD=" + str(child))
    summary = child['summary'] + ": " + suffix

    # The description field may/not be a (very simple) format string, so needs special care
    if child['description'].find("%s") >= 0:
      description = child['description'] % (suffix)
      logit(sys._getframe().f_code.co_name + "::CHILD_SUMMARY=" + str(summary) + " CHILD_DESCRIPTION_FORMATTED=" + str(description))
    else:
      description = child['description']
      logit(sys._getframe().f_code.co_name + "::CHILD_SUMMARY=" + str(summary) + " CHILD_DESCRIPTION_UNFORMATTED=" + str(description))

    # If a Standard Operating Procedure (SOP) was supplied, include that in description too.
    if child['sop'] != "-":
      description = "%s\n\nFurther details on what this entails and why it is important are available at:\n\n* %s" % (description, child['sop'])

    childIssue = doIssueCreate(jira, project, child['type'], parentIssue.key, PRIORITY_MAJOR, summary, description, assignee, child['components'], child['labels'])
    logit(sys._getframe().f_code.co_name + "::CHILD_ISSUE=" + str(childIssue))

  return parentIssue

######################################################################
# TEMPLATE::List
######################################################################
def doTemplateList():

  # Load all available templates
  with open(JIRA_TEMPLATES) as f:
    templates = json.load(f)
  logit(sys._getframe().f_code.co_name + "::TEMPLATES=" + str(templates))

  # Fetch the list of template ids
  keys = sorted(templates.keys())
  logit(sys._getframe().f_code.co_name + "::KEYS=" + str(keys))

  return keys

#################################
# MAIN
#################################
def main():
  global DEBUG
  global QUIET

  args   = genParser().parse_args()
  action = args.action
  DEBUG  = args.verbose
  QUIET  = args.quiet

  #
  # The "target" command needs special handling early on
  #
  if CMD_TARGET == action:
    try:
      options = { "server": args.server }
      jira = JIRA(options, token_auth=args.token)
      #jira = JIRA(options, basic_auth=(args.username, args.password))
      logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira))
      creds = { "server": args.server, "username": args.username, "token": args.token, "project": args.project }
      with open(CACHED_CREDS, 'w') as outfile:
        json.dump(creds, outfile)
    except JIRAError as e:
      print ("ERROR: Failed to validate JIRA credentials for " + args.username + " on " + str(args.server) + " - " + str(e.text))
      sys.exit(1)

  #
  # Convert some input arguments into JSON structures
  #
  components = None
  if args.components is not None:
    components = args.components.split(",")

  labels = None
  if args.labels is not None:
    labels = args.labels.split(",")

  #
  # Normal Operation...
  # Try to load JIRA credentials from local/cached file (but support override of project value therein too)
  #
  project = args.project
  if CMD_TEMPLATE_LIST != action:
    try:
      with open(CACHED_CREDS) as creds_file:
        creds = json.load(creds_file)
        logit(sys._getframe().f_code.co_name + "::CREDS=" + str(creds))
        options = { "server": creds["server"] }
        #jira = JIRA(options, basic_auth=(creds["username"], creds["password"]))
        jira = JIRA(options, token_auth=creds["token"])
        project = creds["project"]
        logit(sys._getframe().f_code.co_name + "::JIRA=" + str(jira))
    except:
      print ("ERROR: Could not load credentials from " + CACHED_CREDS + ". You may need to target the JIRA server first.")
      sys.exit(1)

  # Assume the project was specified in the credentials file, but allow it to be overridden here
  if args.project is not None:
    project = args.project

  #
  # Standard Actions
  #
  if CMD_ISSUE_CREATE == action:
    issue = doIssueCreate(jira, project, args.issuetype, args.parent, args.priority, args.summary, args.description, args.assignee, components, labels)
    print (str(creds["server"]) + "/browse/" + str(issue))

  if CMD_ISSUE_READ == action:
    fields = doIssueRead(jira, project, args.key)
    print (json.dumps(fields, indent=2))

  if CMD_ISSUE_UPDATE == action:
    doIssueUpdate(jira, project, args.key, args.issuetype, args.priority, args.summary, args.description, args.assignee, components, labels)

  if CMD_ISSUE_DELETE == action:
    doIssueDelete(jira, project, args.key)

  if CMD_ISSUE_COMMENT == action:
    doIssueComment(jira, project, args.key, args.message)

  if CMD_ISSUE_ASSIGN == action:
    doIssueAssign(jira, project, args.key, args.assignee)

  if CMD_ISSUE_UPDATE_EPIC == action:
    doIssueUpdateEpic(jira, args.key, args.parent)

  if CMD_ISSUE_UPDATE_SPRINT == action:
    doIssueUpdateSprint(jira, args.key, args.parent)

  if CMD_ISSUE_UPDATE_REPORTER == action:
    doIssueUpdateReporter(jira, args.key, args.reporter)

  if CMD_ISSUE_UPDATE_DUE_DATE == action:
    doIssueUpdateDueDate(jira, args.key, args.duedate)

  if CMD_ISSUE_WATCHER_ADD == action:
    doIssueWatcherAdd(jira, args.key, args.watcher)

  if CMD_ISSUE_WATCHER_REMOVE == action:
    doIssueWatcherRemove(jira, args.key, args.watcher)

  if CMD_COMPONENT_ADD == action:
    doComponentManage(jira, args.key, components, ACTION_ADD)

  if CMD_COMPONENT_REMOVE == action:
    doComponentManage(jira, args.key, components, ACTION_REMOVE)

  if CMD_LABEL_ADD == action:
    doLabelManage(jira, args.key, labels, ACTION_ADD)

  if CMD_LABEL_REMOVE == action:
    doLabelManage(jira, args.key, labels, ACTION_REMOVE)

  if CMD_TEMPLATE_CREATE == action:
    issue = doTemplateCreate(jira, project, args.template, args.summary, args.assignee)
    print (str(creds["server"]) + "/browse/" + str(issue))

  if CMD_TEMPLATE_LIST == action:
    templates = doTemplateList()
    print (templates)

if __name__ == "__main__":
  main()
