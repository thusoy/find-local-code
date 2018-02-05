import textwrap

from find_local_only_code import Branch, parse_git_branch_output


def test_get_branches():
    git_output = textwrap.dedent('''\
  branch-that-is-ahead            2cb9177 [origin/ahead: ahead 1] Some commit ahead
  branch-that-is-behind           3d78da4 [origin/behind: behind 2] Some non-fresh commit
* master                          b6d4d57 [origin/master] Yo boi fresh
  local-only                      9a7b693 Only local this one
  out-of-sync                     ac9cb08 [origin/out-of-sync: ahead 1, behind 1] Rebase on the horizon
''').split('\n')[:-1]

    parsed_branches = list(parse_git_branch_output(git_output))

    assert parsed_branches == [
        Branch('branch-that-is-ahead', '2cb9177', 'origin', 'ahead', 1, 0),
        Branch('branch-that-is-behind', '3d78da4', 'origin', 'behind', 0, 2),
        Branch('master', 'b6d4d57', 'origin', 'master', 0, 0),
        Branch('local-only', '9a7b693', None, None, 0, 0),
        Branch('out-of-sync', 'ac9cb08', 'origin', 'out-of-sync', 1, 1),
    ]

