import os
import subprocess
import re
import sys
import fnmatch

from collections import defaultdict

here = os.path.split(__file__)[0]

repo_root = os.path.abspath(os.path.join(here, "..", ".."))

def git(command, *args):
    args = list(args)

    proc_kwargs = {"cwd": repo_root}

    command_line = ["git", command] + args

    try:
        return subprocess.check_output(command_line, **proc_kwargs)
    except subprocess.CalledProcessError as e:
        raise


def iter_files():
    for item in git("ls-tree", "-r", "--name-only", "HEAD").split("\n"):
        yield item


def check_path_length(path):
    if len(path) + 1 > 150:
        return [("PATH LENGTH", "/%s longer than maximum path length (%d > 150)" % (path, len(path) + 1), None)]
    return []

def set_type(error_type, errors):
    return [(error_type,) + error for error in errors]

def parse_whitelist_file(filename):
    data = defaultdict(lambda:defaultdict(set))

    with open(filename) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [item.strip() for item in line.split(":")]
            if len(parts) == 2:
                parts.append(None)
            else:
                parts[-1] = int(parts[-1])

            error_type, file_match, line_number = parts
            data[file_match][error_type].add(line_number)

    def inner(path, errors):
        test_path = "webaudio/the-audio-api/the-gainnode-interface/gain-expected.wav"
        rv = []
        # if path == test_path:
        #     import pdb
        #     pdb.set_trace()

        whitelisted = [False for item in xrange(len(errors))]

        for file_match, whitelist_errors in data.iteritems():
            if fnmatch.fnmatch(path, file_match):
                for i, (error_type, msg, line) in enumerate(errors):
                    if error_type in whitelist_errors:
                        allowed_lines = whitelist_errors[error_type]
                        if None in allowed_lines or line in allowed_lines:
                            whitelisted[i] = True

        return [item for i, item in enumerate(errors) if not whitelisted[i]]
    return inner

_whitelist_fn = None
def whitelist_errors(path, errors):
    global _whitelist_fn

    if _whitelist_fn is None:
        _whitelist_fn = parse_whitelist_file("lint.whitelist")
    return _whitelist_fn(path, errors)

trailing_whitespace_regexp = re.compile("\s$")
tabs_regexp = re.compile("^\t")
cr_regexp = re.compile("\r$")
def check_whitespace(path, f):
    errors = []
    for i, line in enumerate(f):
        for regexp, error in [(trailing_whitespace_regexp, "TRAILING WHITESPACE"),
                              (tabs_regexp, "INDENT TABS"),
                              (cr_regexp, "CR AT EOL")]:
            if regexp.match(line):
                errors.append((error, "%s line %i" % (path, i+1), i+1))

    return errors

def output_errors(errors):
    for error_type, error, line_number in errors:
        print "%s: %s" % (error_type, error)

def output_error_count(error_count):
    by_type = " ".join("%s: %d" % item for item in error_count.iteritems())
    count = sum(error_count.values())
    print "There were %d errors (%s)" % (count, by_type)

def main():
    error_count = defaultdict(int)

    def run_lint(path, fn, *args):
        errors = whitelist_errors(path, fn(path, *args))
        output_errors(errors)
        for error_type, error, line in errors:
            error_count[error_type] += 1

    for path in iter_files():
        abs_path = os.path.join(repo_root, path)
        for path_fn in path_lints:
            run_lint(path, path_fn)

        if not os.path.isdir(abs_path):
            with open(abs_path) as f:
                for file_fn in file_lints:
                    run_lint(path, file_fn, f)

    output_error_count(error_count)
    return error_count

path_lints = [check_path_length]
file_lints = [check_whitespace]

if __name__ == "__main__":
    error_count = main()
    if error_count > 0:
        sys.exit(1)
