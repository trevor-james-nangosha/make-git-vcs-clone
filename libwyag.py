import argparse
import collections
import configparser
import hashlib
import os
import re
import sys
import zlib 

# TODO;
# go to the actual web page and verify the code snippets

arg_parser = argparse.ArgumentParser(description="The stupid content tracker.")
arg_sub_parsers = arg_parser.add_subparsers(title="commands", dest="command")
arg_sub_parsers.required = True

arg_sub_parser = arg_sub_parsers.add_parser("init", help="initialise a new empty git repository")
arg_sub_parser.add_argument('path',
                            metavar="directory",
                            nargs="?",
                            default=".",
                            help="where to create the repository.")

def cmd_init(args):
    repo_create(args.path)

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

def repo_find(path='.', required=True):
    path = os.path.realpath(path)
    if os.path.isdir(os.path.join(path, ".git")):
        return GitRepository(path)

    # if we have not returned, recurse in parent, if w
    parent = os.path.realpath(os.path.join(path, '..'))

    if parent == path:
        # Bottom case
        # os.path.join("/". "..") == "/"
        # if parent == path. then path is not root
        if required:
            raise Exception("No git directory")
        else:
            return None

    # recursive case
    return repo_find(parent, required)


class GitObject(object):
    repo = None

    def __init__(self, repo, data=None ):
        self.repo = repo
        if data != None:
            self.deserealise(self)

    def serealise(self):
        """This function must be implemented by subclasses"""
        # some other trash here.
        raise Exception("Unimplemented.")

    def deserealise(self, data):
        raise Exception("Unimplemented.")

class GitBlob(GitObject):
    fmt = b'blob'
    def serealise(self):
        return self.blob_data

    def deserealise(self, data):
        self.blob_data = data

def object_read(repo, sha):
    """Read object object_id from Git repo. Return a 
    GitObject whose exact type depends on the object"""

    path = repo_file(repo, "objects", sha[0:2], sha[2:1])
    with open(path, "rb") as f:
        raw = zlib.decompress(f.read())

        # read object type
        x = raw.find(b' ')
        fmt = raw[0:x]

        # read and validate the object size
        y = raw.find(b'\x00', x)
        size = int(raw[x:y].decode('ascii'))
        if size != len(raw)-y-1:
            raise Exception(f"malformed object {0}: bad length")

        # Pick constructor
        if fmt == b'commit': c=GitCommit
        elif fmt == b'tree': c=GitTree
        elif fmt == b'tag': c=GitTag
        elif fmt == b'blob': c=GitBlob
        else:
            raise Exception(f"unknown type {0} for object {1}")

        # Call constructor and return object
        return c(repo, raw[y+1:])

def object_find(repo, name, fmt=None, follow=True):
    return name

def object_write(obj, actually_write=True):
    # serialise the object data
    data = obj.serialise()
    # add header
    result = obj.fmt + b' ' + str(len(data)).encode() + b'\x00' + data

    # compute hash
    sha = hashlib.sha1(result).hexdigest()

    if actually_write:
        # compute the path
        path = repo_file(obj.repo, "objects", sha[0:2], sha[2:], mkdir=actually_write)

        with open(path, 'wb') as f:
            # compress anf write
            f.write(zlib.compress(result))

    return sha

arg_sub_parser = arg_sub_parsers.add_parser('cat-file',
                                            help='Provide content or type and size information for repository objects')
arg_sub_parser.add_argument('type',
                            metavar='type',
                            choices=['blob', 'commit', 'tag', 'tree'],
                            help='Specify the type.')                                          

arg_sub_parser.add_argument('object',
                            metavar='object',
                            help='The object to display')


def cmd_cat_file(args):
    repo = repo.find()
    cat_file(repo, args.object, fmt=args.type.encode())

def cat_file(repo, obj, fmt=None):
    obj = object_read(repo, object_find(repo, obj, fmt=fmt))
    sys.stdout.buffer.write(obj.serialise())



arg_sub_parser = arg_sub_parsers.add_parser("hash-object",
                                        help="Compute object ID and optionally creates a blob from a file")

arg_sub_parser.add_argument("-t",
                            metavar="type",
                            dest="type",
                            choices=["blob", "commit", "tag", "tree"],
                            default="blob",
                            help="Specify the type")

arg_sub_parser.add_argument("-w",
                            dest="write",
                            action="store_true",
                            help="Actually write the object into the database")

arg_sub_parser.add_argument("path",
                help="Read object from <file>")

def cmd_hash_object(args):
    if args.write:
        repo = GitRepository(".")
    else:
        repo = None
    
    with open(args.path, "rb") as fd:
        sha = object_hash(fd, args.type.encode(), repo)
        print(sha)

def object_hash(fd, fmt, repo=None):
    data = fd.read()

    # Choose constructor depending on
    # object type found in header.
    if fmt==b'commit': obj=GitCommit(repo, data)
    elif fmt==b'tree': obj=GitTree(repo, data)
    elif fmt==b'tag': obj=GitTag(repo, data)
    elif fmt==b'blob': obj=GitBlob(repo, data)
    else:
        raise Exception("Unknown type %s!" % fmt)
        
    return object_write(obj, repo)


# simple parser for log formats and messages
# kvlm = key value list with message 
def kvlm_message(raw, start=0, dict=None):
    if not dict:
        dict = collections.OrderedDict()
        # you cannot declare the argument as dict=Ordereddict() or all
        # call to the functions will endlessly grow the same dict
        # 
    # we search for the next space and the  next new line
    space = raw.find(b' ', start) 
    new_line = raw.find(b'\n', start)

    # if space appears before the end, we have a keyword

    # base case
    # ============
    # if newline appears first(or there is no space at all, in which case)
    # find returns -1_, we assume a  blank line. a blank line
    # means the remainder of the data is in the message    

    if space < 0 or new_line > space:
        assert(new_line == start)
        dict[b''] = raw[start+1:]
        return dict
    
    # Recursive case
    # ==============
    # we read a key-value pair and recurse for the next.
    key = raw[start:space]

    # find the end of the value. continuation lines begin with a 
    # a space. so we loop until we find a '\n' not followed by a space
    end = start
    while True:
        end = raw.find(b'\n', end+1)
        if raw[end+1] != ord(' '): break 

    # grab the value 
    # also, drop the leading space on continuation lines 
    value = raw[space+1:end].replace(b'\n', b'\n')

    # do not overwrite existing data containers 
    if key in dict:
        if type(dict[key] == list):
            dict[key] = [dict[key], value]
        else:
            dict[key] = [dict[key], value]
    else:
        dict[key] = value

        return kvlm_parse(raw, start=end+1, dict=dict)

def kvlm_serialize(kvlm):
    ret = b''

    # Output fields
    for k in kvlm.keys():
        # Skip the message itself
        if k == b'': continue
        val = kvlm[k]

        # Normalize to a list
        if type(val) != list:
            val = [ val ]
        for v in val:
            ret += k + b' ' + (v.replace(b'\n', b'\n ')) + b'\n'
    
    # Append message
    ret += b'\n' + kvlm[b'']

    return ret

class GitCommit(GitObject):
    fmt = b'commit'

    def deserealise(self, data):
        self.kvlm = kvlm_parse(data)

    def serealise(self):
        return kvlm_serialize(self.kvlm)

arg_sub_parser = arg_sub_parsers.add_parser("log", help='Display history of a given commit')
arg_sub_parser.add_argument("commit",
                            default="HEAD",
                            nargs="?",
                            help="Commit to start at.")

def cmd_log(args):
    repo = repo_find()
    print("digraph wyaglog{")
    log_graphviz(repo, object_find(repo, args.commit), set())
    print('}')

def log_graphviz(repo, sha, seen):
    if sha in seen:
        return
    seen.add(sha)

    commit = object_read(repo, sha)
    assert (commit.fmt==b'commit')

    if not b'parent' in commit.kvlm.keys():
        # Base case: the initial commit.
        return

    parents = commit.kvlm[b'parent']

    if type(parents) != list:
        parents = [ parents ]

    for parent in parents:
        parent = parent.decode("ascii")
        print ("c_{0} -> c_{1};".format(sha, parent))
        log_graphviz(repo, parent, seen)

class GitTreeLeaf(object):
    def __init__(self, mode, path, sha):
        self.mode = mode
        self.path = path
        self.sha = sha 


def tree_parse_one(raw, start=0):
    # Find the space terminator of the mode
    x = raw.find(b' ', start)
    assert(x-start == 5 or x-start==6)

    # Read the mode
    mode = raw[start:x]

    # Find the NULL terminator of the path
    y = raw.find(b'\x00', x)
    # and read the path
    path = raw[x+1:y]

    # Read the SHA and convert to an hex string
    sha = hex(int.from_bytes(raw[y+1:y+21], "big"))[2:] # hex() adds 0x in front,
    # we don't want that.
    return y+21, GitTreeLeaf(mode, path, sha)


def tree_parse(raw):
    position = 0
    max = len(raw)
    ret = list()
    while position < max:
        position, data = tree_parse_one(raw, position)
        ret.append(data)

    return ret


def tree_serialize(obj):
    #@FIXME Add serializer!
    ret = b''

    for i in obj.items:
        ret += i.mode
        ret += b' '
        ret += i.path
        ret += b'\x00'
        sha = int(i.sha, 16)
        # @FIXME Does
        ret += sha.to_bytes(20, byteorder="big")

    return ret


class GitTree(GitObject):
    fmt=b'tree'

    def deserialize(self, data):
        self.items = tree_parse(data)

    def serialize(self):
        return tree_serialize(self)


arg_sub_parser = arg_sub_parsers.add_parser("ls-tree", help="Pretty-print a tree object")
arg_sub_parser.add_argument("object",
                            help="The object to show.")

def cmd_ls_tree(args):
    repo = repo_find()
    obj = object_read(repo, object_find(repo, args.object, fmt = b'tree'))
    
    for item in obj.items:
        print("{0} {1} {2}\t{3}".format("0" * (6 - len(item.mode)) + item.mode.decode("ascii"),
            # Git's ls-tree displays the type
            # of the object pointed to. We can do that too :)
            object_read(repo, item.sha).fmt.decode("ascii"),
            item.sha, item.path.decode("ascii")))


arg_sub_parser = arg_sub_parsers.add_parser("checkout", help="Checkout a commit")
arg_sub_parser.add_argument("commit", help="The commit or tree to checkout.")
arg_sub_parser.add_argument("path", help="The EMPTY directory to checkout on.")    

def cmd_checkout(args):
    repo = repo_find()

    obj = object_read(repo, object_find(repo, args.commit))

    # If the object is a commit, we grab its tree
    if obj.fmt == b'commit':
        obj = object_read(repo, obj.kvlm[b'tree'].decode("ascii"))
    
    # Verify that path is an empty directory
        if os.path.exists(args.path):
            if not os.path.isdir(args.path):
                raise Exception("Not a directory {0}!".format(args.path))
        if os.listdir(args.path):
            raise Exception("Not empty {0}!".format(args.path))
    else:
        os.makedirs(args.path)
    
    tree_checkout(repo, obj, os.path.realpath(args.path).encode())
   

def tree_checkout(repo, tree, path):
    for item in tree.items:
        obj = object_read(repo, item.sha)
        dest = os.path.join(path, item.path)
    
    if obj.fmt == b'tree':
        os.mkdir(dest)
        tree_checkout(repo, obj, dest)
    elif obj.fmt == b'blob':
        with open(dest, 'wb') as f:
            f.write(obj.blobdata)
