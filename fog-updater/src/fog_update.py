#!/usr/bin/env python3

# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/

from github import Github, GithubException, InputGitAuthor, enable_console_debug_logging
import datetime
import difflib
import io
import os
import requests
import sys

DEFAULT_ORGANIZATION = "mozilla"
DEFAULT_AUTHOR_NAME = "data-updater"
DEFAULT_AUTHOR_EMAIL = "telemetry-alerts@mozilla.com"
BODY_TEMPLATE = f"""This (automated) patch updates the list from metrics_index.py.

For reviewers:

* Canonical source for the index: <{INDEX_URL}>
* Please double-check that the changes here are valid and that the referenced files exist.
    * If the referenced files do not exist, schema deploys will fail
* Delete this branch after merging or closing the PR.

---

The source code of this automation bot lives in <https://github.com/mozilla/probe-scraper/tree/main/fog-updater>.
"""  # noqa

class UnmodifiedException(Exception):
    pass


def ts():
    return str(datetime.datetime.now())


def _commit_repositories_txt(repo, branch, author, new_content):
    contents = repo.get_contents("repositories.txt", ref=branch)

    repo.update_file(
        contents.path,
        "Update repositories.txt with new FOG metrics_txts list",
        new_content,
        contents.sha,
        branch=branch,
        author=author,
    )

    return True


def main(argv, repo, author, debug=False, dry_run=False):
    if len(argv) < 1:
        print(USAGE)
        sys.exit(1)

    release_branch_name = "main"
    short_version = "main"

    print(f"{ts()} Updating repositories.txt")
    try:
        new_content = open("repositories.txt").read()
        new_content += f"ts={ts()}\n"
    except UnmodifiedException as e:
        print(f"{ts()} {e}")
        return
    except Exception as e:
        print(f"{ts()} {e}")
        raise

    if dry_run:
        print(f"{ts()} Dry-run so not continuing.")
        return

    # Create a non unique PR branch name for work on this ac release branch.
    pr_branch_name = f"fog-update/update-metrics-index-{short_version}"

    try:
        pr_branch = repo.get_branch(pr_branch_name)
        if pr_branch:
            print(f"{ts()} The PR branch {pr_branch_name} already exists. Exiting.")
            return
    except GithubException:
        # TODO Only ignore a 404 here, fail on others
        pass

    release_branch = repo.get_branch(release_branch_name)
    print(f"{ts()} Last commit on {release_branch_name} is {release_branch.commit.sha}")

    print(f"{ts()} Creating branch {pr_branch_name} on {release_branch.commit.sha}")
    repo.create_git_ref(
        ref=f"refs/heads/{pr_branch_name}", sha=release_branch.commit.sha
    )
    print(f"{ts()} Created branch {pr_branch_name} on {release_branch.commit.sha}")

    _commit_repositories_txt(repo, pr_branch_name, author, new_content)

    print(f"{ts()} Creating pull request")
    pr = repo.create_pull(
        title=f"Update to latest metrics_index list on {release_branch_name}",
        body=BODY_TEMPLATE,
        head=pr_branch_name,
        base=release_branch_name,
    )
    pr.enable_automerge(merge_method="rebase")
    print(f"{ts()} Pull request at {pr.html_url}")


if __name__ == "__main__":
    debug = os.getenv("DEBUG") is not None
    if debug:
        enable_console_debug_logging()

    github_access_token = os.getenv("GITHUB_TOKEN")
    if not github_access_token:
        print("No GITHUB_TOKEN set. Exiting.")
        sys.exit(1)

    github = Github(github_access_token)
    if github.get_user() is None:
        print("Could not get authenticated user. Exiting.")
        sys.exit(1)

    dry_run = os.getenv("DRY_RUN") == "True"

    organization = os.getenv("GITHUB_REPOSITORY_OWNER") or DEFAULT_ORGANIZATION

    repo = github.get_repo(f"{organization}/test-repo")

    author_name = os.getenv("AUTHOR_NAME") or DEFAULT_AUTHOR_NAME
    author_email = os.getenv("AUTHOR_EMAIL") or DEFAULT_AUTHOR_EMAIL
    author = InputGitAuthor(author_name, author_email)

    print(
        f"{ts()} This is fog-update working on https://github.com/{organization} as {author_email} / {author_name}"  # noqa
    )

    main(sys.argv, repo, author, debug, dry_run)
