#!/usr/bin/env python

# Looks for code that hasn't pushed to upstream in stash, local-only branches,
# branches with unpushed commits, and uncommitted files. write in python to
# easily enable cli parsing to only scan for/ignore subsets of these

import argparse
import subprocess
import re
import sys
import os
from collections import namedtuple

BRANCH_DETAILS_RE = re.compile(r'^\*?\s+(?P<name>[^ ]+)\s+(?P<head>\w+) (?P<state>.+)$')
BRANCH_STATE_RE = re.compile(r'\[(?P<remote>[\w-]+)\/(?P<remote_branch>[^:\]]+):?\s?(?:ahead (?P<ahead>\d+))?,?\s?(?:behind (?P<behind>\d+))?\]\s.*$')
Branch = namedtuple('Branch', 'name head remote remote_branch ahead behind')

def main():
    args = get_args()
    for repo in args.repositories:
        scan_repo(repo)


def scan_repo(repo_path):
    stashes = check_stashes(repo_path)
    if stashes:
        print('%s has %d stashes' % (repo_path, stashes))

    branches = list(get_branches(repo_path))

    local_only_branches = check_local_only_branches(branches)
    for branch in local_only_branches:
        print('%s has local-only branch %s' % (repo_path, branch))

    unpushed_branches = check_unpushed_branches(repo_path, branches)
    for branch, ahead, behind in unpushed_branches:
        trailer = ' (and %d behind)' % behind if behind else ''
        print('%s has branch %s which is %s commits ahead%s' % (
            repo_path, branch, ahead, trailer))


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


def check_local_only_branches(branches):
    local_only_branches = []
    for branch in branches:
        if not branch.remote:
            local_only_branches.append(branch.name)

    return local_only_branches


def check_unpushed_branches(repo_path, branches):
    for branch in branches:
        if not branch.remote:
            continue

        if not branch.ahead:
            continue

        yield branch.name, branch.ahead, branch.behind


def get_command_output_lines(cmd):
    return subprocess.check_output(cmd).split('\n')[:-1]


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('repositories', nargs='+')
    return parser.parse_args()


if __name__ == '__main__':
    main()
