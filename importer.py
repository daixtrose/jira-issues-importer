#!/usr/bin/env python

import requests
import random
import time
import re
import github
import json
import calendar


class Importer:

    _GITHUB_ISSUE_PREFIX = "GH-"

    _PLACEHOLDER_PREFIX = "@PSTART"

    _PLACEHOLDER_SUFFIX = "@PEND"

    _DEFAULT_TIME_OUT = 120.0

    def __init__(self, github_connector, repo, project):
        self.github_connector = github_connector
        self.repo = repo
        self.project = project
        self.jira_issue_replace_patterns = {'https://java.net/jira/browse/' + self.project.name + r'-(\d+)': r'\1',
                                            self.project.name + r'-(\d+)': Importer._GITHUB_ISSUE_PREFIX + r'\1',
                                            r'Issue (\d+)': Importer._GITHUB_ISSUE_PREFIX + r'\1'}

    def wait_for_rate_limit(self):
        """
        Checks GitHub's rate limit and waits until time is gone
        """
        core_rate_limit = self.github_connector.get_rate_limit().core
        reset_timestamp = calendar.timegm(core_rate_limit.reset.timetuple())
        # add 2 seconds to be sure the rate limit has been reset
        sleep_time = reset_timestamp - calendar.timegm(time.gmtime()) + 2
        print("----> Waiting for rate limit to allow us the next call. Sleeping for {}s".format(sleep_time))
        time.sleep(sleep_time)

    def import_milestones(self):
        """
        Imports the gathered project milestones into GitHub and remembers the created milestone ids
        """
        print('Importing milestones...')
        print()
        for mkey in self.project.get_milestones().keys():
            data = {'title': mkey}

            # TODO: fix milestones
            # r = requests.post(milestone_url, json=data, auth=(
            #     self.options.user, self.options.passwd), timeout=Importer._DEFAULT_TIME_OUT)

            # # overwrite histogram data with the actual milestone id now
            # if r.status_code == 201:
            #     content = r.json()
            #     self.project.get_milestones()[mkey] = content['number']
            #     print(mkey)
            # else:
            #     if r.status_code == 422:  # already exists
            #         ms = requests.get(
            #             milestone_url + '?state=open', timeout=Importer._DEFAULT_TIME_OUT).json()
            #         ms += requests.get(milestone_url + '?state=closed',
            #                            timeout=Importer._DEFAULT_TIME_OUT).json()
            #         f = False
            #         for m in ms:
            #             if m['title'] == mkey:
            #                 self.project.get_milestones()[mkey] = m['number']
            #                 print(mkey, 'found')
            #                 f = True
            #                 break
            #         if not f:
            #             exit('Could not find milestone: ' + mkey)
            #     else:
            #         print('Failure!', r.status_code, r.content, r.headers)

    def import_labels(self):
        """
        Imports the gathered project components and labels as labels into GitHub 
        """
        print("==> Importing labels")
        print('Importing labels...')
        print()
        for lkey in self.project.get_components().keys():
            color = '%.6x' % random.randint(0, 0xffffff)

            try:
                self.repo.create_label(name=lkey, color=color, description='')
            except github.GithubException as ex:
                print('Failure importing label ' + lkey,
                      ex.status, ex.data, ex.headers)

    def import_issues(self):
        """
        Starts the issue import into GitHub:
        First the milestone id is captured for the issue.
        Then JIRA issue relationships are converted into comments.
        After that, the comments are taken out of the issue and 
        references to JIRA issues in comments are replaced with a placeholder    
        """
        print('Importing issues...')
        for issue in self.project.get_issues():
            time.sleep(2)
            if 'milestone_name' in issue:
                issue['milestone'] = self.project.get_milestones()[
                    issue['milestone_name']]
                del issue['milestone_name']

            self.convert_relationships_to_comments(issue)

            issue_comments = issue['comments']
            del issue['comments']
            comments = []
            for comment in issue_comments:
                comments.append(dict((k, self._replace_jira_with_github_id(v))
                                for k, v in list(comment.items())))

            self.import_issue_with_comments(issue, comments)

    def import_issue_with_comments(self, issue, comments):
        """
        Imports a single issue with its comments into GitHub.
        Importing via GitHub's unofficial Issue Import API does not work anymore
        """
        print('Issue ', issue['key'])
        jiraKey = issue['key']
        del issue['key']

        issue = self.upload_github_issue(issue, comments)
        # status_url = response.json()['url']
        # gh_issue_url = self.wait_for_issue_creation(
        #     status_url, headers).json()['issue_url']
        # gh_issue_id = int(gh_issue_url.split('/')[-1])
        # issue['githubid'] = gh_issue_id
        # # print "\nGithub issue id: ", gh_issue_id
        # issue['key'] = jiraKey

    # def upload_github_issue(self, issue, comments) -> Github.Issue.Issue:
    def upload_github_issue(self, issue, comments) -> github.Issue:
        """
        Create a single issue in GitHub repository.
        """
        try:
            print(json.dumps(issue, indent=4))
            self.wait_for_rate_limit()
            github_issue = self.repo.create_issue(
                title=issue["title"], body=issue["body"])

            for comment in comments:
                try:
                    print("===========================================")
                    print(json.dumps(comment, indent=4))
                    print("-------------------------------------------")
                    self.wait_for_rate_limit()
                    github_issue.create_comment(comment["body"])
                except github.GithubException as ex:
                    print('Failure adding a comment to issue ' + issue.id,
                          ex.status, ex.data, ex.headers)

        except github.GithubException as ex:
            print('Failure creating issue ' + issue["title"],
                  ex.status, ex.data, ex.headers)
            pass

        return issue

        # #issue_url = self.github_url + '/import/issues'
        # issue_url = self.github_url + '/issues'

        # print("-------")
        # print(issue_url)

        # issue_data = {'issue': issue, 'comments': comments}

        # response = requests.post(issue_url, json=issue, auth=(
        #     self.options.user, self.options.passwd), headers=headers, timeout=Importer._DEFAULT_TIME_OUT)
        # if response.status_code == 202:
        #     return response
        # elif response.status_code == 422:
        #     raise RuntimeError(
        #         "Initial import validation failed for issue '{}' due to the "
        #         "following errors:\n{}".format(issue['title'], response.json())
        #     )
        # else:
        #     raise RuntimeError(
        #         "Failed to POST issue: '{}' due to unexpected HTTP status code: {}\nerrors:\n{}"
        #         .format(issue['title'], response.status_code, response.json())
        #     )

    def convert_relationships_to_comments(self, issue):
        duplicates = issue['duplicates']
        is_duplicated_by = issue['is-duplicated-by']
        relates_to = issue['is-related-to']
        depends_on = issue['depends-on']
        blocks = issue['blocks']

        for duplicate_item in duplicates:
            issue['comments'].append(
                {"body": "Duplicates: " + self._replace_jira_with_github_id(duplicate_item)})

        for is_duplicated_by_item in is_duplicated_by:
            issue['comments'].append(
                {"body": "Is duplicated by: " + self._replace_jira_with_github_id(is_duplicated_by_item)})

        for relates_to_item in relates_to:
            issue['comments'].append(
                {"body": "Is related to: " + self._replace_jira_with_github_id(relates_to_item)})

        for depends_on_item in depends_on:
            issue['comments'].append(
                {"body": "Depends on: " + self._replace_jira_with_github_id(depends_on_item)})

        for blocks_item in blocks:
            issue['comments'].append(
                {"body": "Blocks: " + self._replace_jira_with_github_id(blocks_item)})

        del issue['duplicates']
        del issue['is-duplicated-by']
        del issue['is-related-to']
        del issue['depends-on']
        del issue['blocks']

    def _replace_jira_with_github_id(self, text):
        result = text
        for pattern, replacement in self.jira_issue_replace_patterns.items():
            result = re.sub(pattern, Importer._PLACEHOLDER_PREFIX +
                            replacement + Importer._PLACEHOLDER_SUFFIX, result)
        return result

    def post_process_comments(self):
        """
        Starts post-processing all issue comments.
        """
        comment_url = self.github_url + '/issues/comments'
        self._post_process_comments(comment_url)

    def _post_process_comments(self, url):
        """
        Paginates through all issue comments and replaces the issue id placeholders with the correct issue ids.
        """
        print("listing comments using " + url)
        response = requests.get(url, auth=(
            self.options.user, self.options.passwd), timeout=Importer._DEFAULT_TIME_OUT)
        if response.status_code != 200:
            raise RuntimeError(
                "Failed to list all comments due to unexpected HTTP status code: {}".format(
                    response.status_code)
            )

        comments = response.json()
        for comment in comments:
            # print "handling comment " + comment['url']
            body = comment['body']
            if Importer._PLACEHOLDER_PREFIX in body:
                newbody = self._replace_github_id_placholder(body)
                self._patch_comment(comment['url'], newbody)
        try:
            next_comments = response.links["next"]
            if next_comments:
                next_url = next_comments['url']
                self._post_process_comments(next_url)
        except KeyError:
            print('no more pages for comments: ')
            for key, value in list(response.links.items()):
                print(key)
                print(value)

    def _replace_github_id_placholder(self, text):
        result = text
        pattern = Importer._PLACEHOLDER_PREFIX + Importer._GITHUB_ISSUE_PREFIX + \
            r'(\d+)' + Importer._PLACEHOLDER_SUFFIX
        result = re.sub(pattern, Importer._GITHUB_ISSUE_PREFIX + r'\1', result)
        pattern = Importer._PLACEHOLDER_PREFIX + \
            r'(\d+)' + Importer._PLACEHOLDER_SUFFIX
        result = re.sub(pattern, r'\1', result)
        return result

    def _patch_comment(self, url, body):
        """
        Patches a single comment body of a Github issue.
        """
        print("patching comment " + url)
        # print "new body:" + body
        patch_data = {'body': body}
        # print patch_data
        response = requests.patch(url, json=patch_data, auth=(
            self.options.user, self.options.passwd), timeout=Importer._DEFAULT_TIME_OUT)
        if response.status_code != 200:
            raise RuntimeError(
                "Failed to patch comment {} due to unexpected HTTP status code: {} ; text: {}".format(
                    url, response.status_code, response.text)
            )
