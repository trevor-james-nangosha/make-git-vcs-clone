import argparse
import collections
import configparser
import hashlib
import os
import re
import sys
import zlib 

arg_parser = argparse.ArgumentParser(description="The stupid content tracker.")
arg_sub_parsers = arg_parser.add_subparsers(title="commands", dest="command")
arg_sub_parsers.required = True

def main(argv = sys.argv[1:]):
    args = arg_parser.parse_args(argv)

    if args.command == "add": cmd_add(args)
    elif args.command == "cat-file": cmd_cat_file(args)
    elif args.command == "checkout": cmd_checkout(args)
    elif args.command == "commit": cmd_commit(args)
    elif args.command == "hash-object": cmd_hash_object(args)
    elif args.command == "init": cmd_init(args)
    elif args.command == "log": cmd_log(args)
    elif args.command == "ls-tree": cmd_ls_tree(args)
    elif args.command == "merge": cmd_merge(args)
    elif args.command == "rebase": cmd_rebase(args)
    elif args.command == "rev-parse": cmd_rev_parse(args)
    elif args.command == "rm": cmd_rm(args)
    elif args.command == "show-ref": cmd_show_ref(args)
    elif args.command == "tag": cmd_tag(args)

class GitRepository(object):
    """A git repository"""
    work_tree = None
    git_dir = None
    conf = None

    def __init__(self, path, force=False):
        self.work_tree = path
        self.git_dir = os.path.join(path, '.git')

        if not (force or os.path.isdir(self.git_dir) ):
            raise Exception(f'not a git repository {path}')

        # read the configuration file in .git.config
        self.conf = configparser.ConfigParser()
        cf = repo_file(self, 'config')

        if cf and os.path.exists(cf):
            self.conf.read([cf])
        elif not force:
            raise Exception('configuration file is missing')

        if not force:
            vers = int(self.conf.get('core', 'repositoryformatversion'))
            if vers != 0:
                raise Exception(f"unsupported repository format version {}")

def repo_path(repo, *path):
    """Compute path under the repo's git_dir"""
    return os.path.join(repo.git_dir, *path)

def repo_file(repo, *path, mkdir=False):
    """same as repo_path, but mkdir *path if absent if mkdir"""
    path = repo_path(repo, *path)
    
    if os.path.exists(path):
        if os.path.isdir(path):
            return path 
        else:
            raise Exception(f"Not a directory: {path}")

        if mkdir:
            os.makedirs(path)
            return path 
        else:
            return None 

def repo_create(path):
    """create a new repository at path."""

    repo = GitRepository(path, True)

    # first, we make sure that the path either does not exist or is 
    # an empty dir
    if os.path.exists(repo.work_tree):
        if not os.path.isdir(repo.work_tree):
            raise Exception(f"{path} is not a directory.")
        if os.listdir(repo.work_tree):
            raise Exception(f"{path} is not empty")

    else:
        os.makedirs(repo.work_tree)
    
    assert(repo_dir(repo, "branches", mkdir=True))
    assert(repo_dir(repo, "objects", mkdir=True))
    assert(repo_dir(repo, "refs", "tags", mkdir=True))
    assert(repo_dir(repo, "refs", "heads", mkdir=True))

    # .git/description
    with open(repo_file(repo, "description"), "w") as f:
        f.write("Unnamed repository: edit this file description")


    # .git/HEAD
    with open(repo_file(repo, "HEAD"), "w") as f:
        f.write("ref: refs/heads/master\n")

    with open(repo_file(repo, "config"), "w") as f:
        config = repo_default_config()
        config.write(f)

    return repo

def repo_default_config():
    ret = configparser.ConfigParser()
    ret.add_section('core')
    ret.set('core', 'repositoryformatversion', '0')
    ret.set('core', 'filemode', 'false')
    ret.set('core', 'bare', 'false')

    return ret

