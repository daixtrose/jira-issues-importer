#!/usr/bin/env python

import sys
import argparse
import getpass
import shlex
from collections import namedtuple
from lxml import objectify
from project import Project
from importer import Importer
from github import Github


def read_xml_sourcefile(file_name):
    all_text = open(file_name).read()
    return objectify.fromstring(all_text)


def import_project(jira_project_name, file_name) -> Project:
    """Import the information from the XML file"""
    all_xml = read_xml_sourcefile(file_name)
    project = Project(jira_project_name)

    for item in all_xml.channel.item:
        project.add_item(item)

    project.merge_labels_and_components()
    project.prettify()

    return project


def main() -> int:
    """Echo the input arguments to standard output"""
    parser = argparse.ArgumentParser(
        prog='jira-issues-importer',
        description='Reads the XMl export of JIRA and imports the issues contained to GitHUb',
        epilog='Text at the bottom of help')
    # positional argument
    parser.add_argument('-f', '--filename', help='the JIRA XML export file.')
    parser.add_argument('-j', '--jira-project', required=True,
                        help='the JIRA project name.')
    parser.add_argument('-t', '--access-token', required=True,
                        help='The GitHub access token.')
    parser.add_argument('-r', '--repository', required=True,
                        help='The repository to which the isses are to be added.')
    parser.add_argument('-o', '--owner', required=True,
                        help='The owner or organization of the repository.')
    parser.add_argument('-v', '--verbose',
                        action='store_true')  # on/off flag

    args = parser.parse_args()

    print("==> '{}'".format(args.jira_project))

    project = import_project(
        jira_project_name=args.jira_project, file_name=args.filename)

    github = Github(args.access_token)

    repo = github.get_repo(args.owner + "/" + args.repository)

    '''
    Steps:
      1. Create any milestones
      2. Create any labels
      3. Create each issue with comments, linking them to milestones and labels
      4: Post-process all comments to replace issue id placeholders with the real ones
    '''
    importer = Importer(github_connector=github, repo=repo, project=project)

    importer.import_milestones()
    importer.import_labels()
    importer.import_issues()
    importer.post_process_comments()

    # github = Github(args.access_token)
    # for repo in github.get_user().get_repos():
    #     print(repo.name)

    # print("==> '{}'".format(args.repository))
    #repo = github.get_repo({owner: args.owner, repo: args.repository})

    # repo = github.get_repo(args.owner + "/" + args.repository)
    # print("==> '{}'".format(repo.git_url))

    # repo.create_issue("This is a test", body="Hello World!",
    #                   assignee="daixtrose")

    #print(args.filename, args.access_token, args.verbose)

    return 0


if __name__ == '__main__':
    sys.exit(main())  # next section explains the use of sys.exit
