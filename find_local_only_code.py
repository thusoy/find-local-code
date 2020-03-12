#!/usr/bin/env python

'''
Looks for code that hasn't pushed to upstream in stash, local-only branches,
branches with unpushed commits, and uncommitted files.
'''

import argparse
import os
import re
import subprocess
import sys
from collections import namedtuple

BRANCH_DETAILS_RE = re.compile(r'^\*?\s+(?P<name>[^ ]+)\s+(?P<head>\w+) (?P<state>.+)$')
BRANCH_STATE_RE = re.compile(r'\[(?P<remote>[\w-]+)\/(?P<remote_branch>[^:\]]+):?\s?(?:ahead (?P<ahead>\d+))?,?\s?(?:behind (?P<behind>\d+))?\]\s.*$')
Branch = namedtuple('Branch', 'name head remote remote_branch ahead behind')

class ProcessFailed(Exception):
    def __init__(self, message, returncode, stderr):
        self.message = message
        self.returncode = returncode
        self.stderr = stderr


def main():
    args = get_args()
    for repo in args.repositories:
        scan_repo(repo)


def scan_repo(repo_path):
    try:
        stashes = check_stashes(repo_path)
    except ProcessFailed as e:
        if e.returncode == 128:
            print('%s is not a git repo' % repo_path)
        else:
            print('Got unknown error when checking stashes in %s' % repo_path)
        return

    if stashes:
        print('%s has %d stashes' % (repo_path, stashes))

    branches = list(get_branches(repo_path))

    local_only_branches = check_local_only_branches(repo_path, branches)
    for branch, commit_count in local_only_branches:
        print('%s has local-only branch %s (%d commits)' % (repo_path, branch, commit_count))

    unpushed_branches = list(check_unpushed_branches(repo_path, branches))
    for branch, ahead, behind in unpushed_branches:
        trailer = ' (and %d behind)' % behind if behind else ''
        print('%s has branch %s which is %s commits ahead%s' % (
            repo_path, branch, ahead, trailer))

    untracked_files = check_untracked_files(repo_path)
    for untracked_file in untracked_files:
        print('%s has untracked file %s' % (repo_path, untracked_file))

    modified_files = check_modified_files(repo_path)
    for modified_file in modified_files:
        print('%s has modified file %s' % (repo_path, modified_file))

    if not (stashes or local_only_branches or unpushed_branches or untracked_files
            or modified_files):
        print('%s is up to date' % repo_path)

def check_stashes(repo_path):
    cmd = [
        'git',
        '-C', repo_path,
        'stash',
        'list',
    ]
    return len(get_command_output_lines(cmd))


def get_branches(repo_path):
    cmd = [
        'git',
        '-C', repo_path,
        'branch',
        '-vv',
    ]
    raw_branches = get_command_output_lines(cmd)
    return parse_git_branch_output(raw_branches)


def parse_git_branch_output(branch_output):
    for branch_details in branch_output:
        match = BRANCH_DETAILS_RE.match(branch_details)
        if not match:
            sys.stderr.write("Branch output didn't match: %s\n" % branch_details)
            continue

        groups = match.groupdict()
        state = groups['state']
        name = groups['name']
        head = groups['head']

        remote_match = BRANCH_STATE_RE.match(state)

        if remote_match:
            remote_groups = remote_match.groupdict(default='0')
            ahead = int(remote_groups.get('ahead'))
            behind = int(remote_groups.get('behind'))
            yield Branch(name, head, remote_match.group('remote'), remote_match.group('remote_branch'), ahead, behind)
        else:
            yield Branch(name, head, None, None, 0, 0)


def check_local_only_branches(repo_path, branches):
    local_only_branches = []
    for branch in branches:
        if not branch.remote:
            # Check that there are commits on this branch that aren't already
            # on master
            cmd = [
                'git',
                '-C', repo_path,
                'log',
                '--oneline',
                '^master',
                branch.name,
            ]
            commit_count = len(get_command_output_lines(cmd))
            if commit_count:
                local_only_branches.append((branch.name, commit_count))

    return local_only_branches


def check_unpushed_branches(repo_path, branches):
    for branch in branches:
        if not branch.remote:
            continue

        if not branch.ahead:
            continue

        yield branch.name, branch.ahead, branch.behind


def check_untracked_files(repo_path):
    cmd = [
        'git',
        '-C', repo_path,
        'ls-files',
        '--others',
        '--directory',
        '--exclude-standard',
    ]
    return get_command_output_lines(cmd)


def check_modified_files(repo_path):
    cmd = [
        'git',
        '-C', repo_path,
        'ls-files',
        '-m'
    ]
    return get_command_output_lines(cmd)


def get_command_output_lines(cmd):
    process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate()
    if process.returncode != 0:
        raise ProcessFailed('Subprocess failed', process.returncode, stderr)

    return stdout.split('\n')[:-1]


def get_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repositories', nargs='+')
    return parser.parse_args()


if __name__ == '__main__':
    main()
