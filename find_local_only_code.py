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
BRANCH_STATE_RE = re.compile(r'^\[(?P<remote>[\w-]+)\/(?P<remote_branch>[^\]]+)\]\s.*$')
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
# TODO: Branches with conflicts


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
    for branch_details in raw_branches:
        match = BRANCH_DETAILS_RE.match(branch_details)
        if not match:
            sys.stderr.write("Branch output didn't match: %s\n" % branch_details)
            continue

        state = match.group('state')
        remote_match = BRANCH_STATE_RE.match(state)
        name = match.group('name')
        head = match.group('head')

        if remote_match:
            yield Branch(name, head, remote_match.group('remote'), remote_match.group('remote_branch'))
        else:
            yield Branch(name, head, None, None)


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

        print(branch)
        remote_commit = get_remote_head(repo_path, branch.remote, branch.remote_branch)
        if remote_commit == branch.head:
            # Local and remote head are equal
            continue

        ahead, behind = get_ahead_status(repo_path, branch.name, branch.remote, branch.remote_branch)
        yield branch.name, ahead, behind


def get_remote_head(repo_path, remote, branch):
    spec_path = os.path.join(repo_path, '.git', 'refs', remote, branch)
    with open(spec_path) as fh:
        return fh.read().strip()


def get_ahead_status(repo_path, local_branch, remote, remote_branch):
    '''Get two numbers, the amount of commits the local branch is ahead of the remote, and how
    many branches behind it is.
    '''
    cmd = [
        'git',
        '-C', repo_path,
        'rev-list',
        '--left-right',
        '--count',
        '%s/%s...%s' % (remote, remote_branch, local_branch),
    ]
    left, right = [int(s) for s in subprocess.check_output(cmd).split()]
    return left, right


def get_command_output_lines(cmd):
    return subprocess.check_output(cmd).split('\n')[:-1]


def get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('repositories', nargs='+')
    return parser.parse_args()


if __name__ == '__main__':
    main()
