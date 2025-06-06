#!/usr/bin/env python3

# Copyright (c) 2009 Giampaolo Rodola'. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.


"""Shortcuts for various tasks, emulating UNIX "make" on Windows.
This is supposed to be invoked by "make.bat" and not used directly.
This was originally written as a bat file but they suck so much
that they should be deemed illegal!
"""


import argparse
import atexit
import ctypes
import fnmatch
import os
import shutil
import site
import subprocess
import sys

PYTHON = os.getenv('PYTHON', sys.executable)
HERE = os.path.abspath(os.path.dirname(__file__))
ROOT_DIR = os.path.realpath(os.path.join(HERE, "..", ".."))
WINDOWS = os.name == "nt"


sys.path.insert(0, ROOT_DIR)  # so that we can import setup.py

_cmds = {}

GREEN = 2
LIGHTBLUE = 3
YELLOW = 6
RED = 4
DEFAULT_COLOR = 7


# ===================================================================
# utils
# ===================================================================


def safe_print(text, file=sys.stdout):
    """Prints a (unicode) string to the console, encoded depending on
    the stdout/file encoding (eg. cp437 on Windows). This is to avoid
    encoding errors in case of funky path names.
    """
    if not isinstance(text, str):
        return print(text, file=file)
    try:
        file.write(text)
    except UnicodeEncodeError:
        bytes_string = text.encode(file.encoding, 'backslashreplace')
        if hasattr(file, 'buffer'):
            file.buffer.write(bytes_string)
        else:
            text = bytes_string.decode(file.encoding, 'strict')
            file.write(text)
    file.write("\n")


def stderr_handle():
    GetStdHandle = ctypes.windll.Kernel32.GetStdHandle
    STD_ERROR_HANDLE_ID = ctypes.c_ulong(0xFFFFFFF4)
    GetStdHandle.restype = ctypes.c_ulong
    handle = GetStdHandle(STD_ERROR_HANDLE_ID)
    atexit.register(ctypes.windll.Kernel32.CloseHandle, handle)
    return handle


def win_colorprint(s, color=LIGHTBLUE):
    if not WINDOWS:
        return print(s)
    color += 8  # bold
    handle = stderr_handle()
    SetConsoleTextAttribute = ctypes.windll.Kernel32.SetConsoleTextAttribute
    SetConsoleTextAttribute(handle, color)
    try:
        print(s)
    finally:
        SetConsoleTextAttribute(handle, DEFAULT_COLOR)


def sh(cmd, nolog=False):
    assert isinstance(cmd, list), repr(cmd)
    if not nolog:
        safe_print(f"cmd: {cmd}")
    p = subprocess.Popen(cmd, env=os.environ, universal_newlines=True)
    p.communicate()  # print stdout/stderr in real time
    if p.returncode != 0:
        sys.exit(p.returncode)


def rm(pattern, directory=False):
    """Recursively remove a file or dir by pattern."""
    if "*" not in pattern:
        if directory:
            safe_rmtree(pattern)
        else:
            safe_remove(pattern)
        return

    for root, dirs, files in os.walk('.'):
        root = os.path.normpath(root)
        if root.startswith('.git/'):
            continue
        found = fnmatch.filter(dirs if directory else files, pattern)
        for name in found:
            path = os.path.join(root, name)
            if directory:
                safe_print(f"rmdir -f {path}")
                safe_rmtree(path)
            else:
                safe_print(f"rm {path}")
                safe_remove(path)


def safe_remove(path):
    try:
        os.remove(path)
    except FileNotFoundError:
        pass
    except PermissionError as err:
        print(err)
    else:
        safe_print(f"rm {path}")


def safe_rmtree(path):
    def onerror(func, path, err):
        if not issubclass(err[0], FileNotFoundError):
            print(err[1])

    existed = os.path.isdir(path)
    shutil.rmtree(path, onerror=onerror)
    if existed and not os.path.isdir(path):
        safe_print(f"rmdir -f {path}")


def recursive_rm(*patterns):
    """Recursively remove a file or matching a list of patterns."""
    for root, dirs, files in os.walk('.'):
        root = os.path.normpath(root)
        if root.startswith('.git/'):
            continue
        for file in files:
            for pattern in patterns:
                if fnmatch.fnmatch(file, pattern):
                    safe_remove(os.path.join(root, file))
        for dir in dirs:
            for pattern in patterns:
                if fnmatch.fnmatch(dir, pattern):
                    safe_rmtree(os.path.join(root, dir))


# ===================================================================
# commands
# ===================================================================


def build():
    """Build / compile."""
    # Make sure setuptools is installed (needed for 'develop' /
    # edit mode).
    sh([PYTHON, "-c", "import setuptools"])

    # "build_ext -i" copies compiled *.pyd files in ./psutil directory in
    # order to allow "import psutil" when using the interactive interpreter
    # from within psutil root directory.
    cmd = [PYTHON, "setup.py", "build_ext", "-i"]
    if os.cpu_count() or 1 > 1:  # noqa: PLR0133
        cmd += ['--parallel', str(os.cpu_count())]
    # Print coloured warnings in real time.
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    try:
        for line in iter(p.stdout.readline, b''):
            line = line.decode().strip()
            if 'warning' in line:
                win_colorprint(line, YELLOW)
            elif 'error' in line:
                win_colorprint(line, RED)
            else:
                print(line)
        # retcode = p.poll()
        p.communicate()
        if p.returncode:
            win_colorprint("failure", RED)
            sys.exit(p.returncode)
    finally:
        p.terminate()
        p.wait()

    # Make sure it actually worked.
    sh([PYTHON, "-c", "import psutil"])
    win_colorprint("build + import successful", GREEN)


def wheel():
    """Create wheel file."""
    build()
    sh([PYTHON, "setup.py", "bdist_wheel"])


def upload_wheels():
    """Upload wheel files on PyPI."""
    build()
    sh([PYTHON, "-m", "twine", "upload", "dist/*.whl"])


def install_pip():
    """Install pip."""
    sh([PYTHON, os.path.join(HERE, "install_pip.py")])


def install():
    """Install in develop / edit mode."""
    build()
    sh([PYTHON, "setup.py", "develop", "--user"])


def uninstall():
    """Uninstall psutil."""
    # Uninstalling psutil on Windows seems to be tricky.
    # On "import psutil" tests may import a psutil version living in
    # C:\PythonXY\Lib\site-packages which is not what we want, so
    # we try both "pip uninstall psutil" and manually remove stuff
    # from site-packages.
    clean()
    install_pip()
    here = os.getcwd()
    try:
        os.chdir('C:\\')
        while True:
            try:
                import psutil  # noqa: F401
            except ImportError:
                break
            else:
                sh([PYTHON, "-m", "pip", "uninstall", "-y", "psutil"])
    finally:
        os.chdir(here)

    for dir in site.getsitepackages():
        for name in os.listdir(dir):
            if name.startswith('psutil'):
                rm(os.path.join(dir, name))
            elif name == 'easy-install.pth':
                # easy_install can add a line (installation path) into
                # easy-install.pth; that line alters sys.path.
                path = os.path.join(dir, name)
                with open(path) as f:
                    lines = f.readlines()
                    hasit = False
                    for line in lines:
                        if 'psutil' in line:
                            hasit = True
                            break
                if hasit:
                    with open(path, "w") as f:
                        for line in lines:
                            if 'psutil' not in line:
                                f.write(line)
                            else:
                                print(f"removed line {line!r} from {path!r}")


def clean():
    """Deletes dev files."""
    recursive_rm(
        "$testfn*",
        "*.bak",
        "*.core",
        "*.egg-info",
        "*.orig",
        "*.pyc",
        "*.pyd",
        "*.pyo",
        "*.rej",
        "*.so",
        "*.~",
        "*__pycache__",
        ".coverage",
        ".failed-tests.txt",
        "pytest-cache-files*",
    )
    safe_rmtree("build")
    safe_rmtree(".coverage")
    safe_rmtree("dist")
    safe_rmtree("docs/_build")
    safe_rmtree("htmlcov")
    safe_rmtree("tmp")


def install_pydeps_test():
    """Install useful deps."""
    install_pip()
    install_git_hooks()
    sh([PYTHON, "-m", "pip", "install", "--user", "-U", "-e", ".[test]"])


def install_pydeps_dev():
    """Install useful deps."""
    install_pip()
    install_git_hooks()
    sh([PYTHON, "-m", "pip", "install", "--user", "-U", "-e", ".[dev]"])


def test(args=None):
    """Run tests."""
    build()
    args = args or []
    sh(
        [PYTHON, "-m", "pytest", "--ignore=psutil/tests/test_memleaks.py"]
        + args
    )


def test_by_name(arg):
    """Run specific test by name."""
    build()
    sh([PYTHON, "-m", "pytest", arg])


def test_by_regex(arg):
    """Run specific test by name."""
    build()
    sh([PYTHON, "-m", "pytest"] + ["-k", arg])


def test_parallel():
    test(["-n", "auto", "--dist", "loadgroup"])


def coverage():
    """Run coverage tests."""
    # Note: coverage options are controlled by .coveragerc file
    build()
    sh([PYTHON, "-m", "coverage", "run", "-m", "pytest"])
    sh([PYTHON, "-m", "coverage", "report"])
    sh([PYTHON, "-m", "coverage", "html"])
    sh([PYTHON, "-m", "webbrowser", "-t", "htmlcov/index.html"])


def test_process():
    """Run process tests."""
    build()
    sh([PYTHON, "-m", "pytest", "-k", "test_process.py"])


def test_process_all():
    """Run process all tests."""
    build()
    sh([PYTHON, "-m", "pytest", "-k", "test_process_all.py"])


def test_system():
    """Run system tests."""
    build()
    sh([PYTHON, "-m", "pytest", "-k", "test_system.py"])


def test_platform():
    """Run windows only tests."""
    build()
    sh([PYTHON, "-m", "pytest", "-k", "test_windows.py"])


def test_misc():
    """Run misc tests."""
    build()
    sh([PYTHON, "-m", "pytest", "-k", "test_misc.py"])


def test_scripts():
    """Run scripts tests."""
    build()
    sh([PYTHON, "-m", "pytest", "-k", "test_scripts.py"])


def test_unicode():
    """Run unicode tests."""
    build()
    sh([PYTHON, "-m", "pytest", "-k", "test_unicode.py"])


def test_connections():
    """Run connections tests."""
    build()
    sh([PYTHON, "-m", "pytest", "-k", "test_connections.py"])


def test_contracts():
    """Run contracts tests."""
    build()
    sh([PYTHON, "-m", "pytest", "-k", "test_contracts.py"])


def test_testutils():
    """Run test utilities tests."""
    build()
    sh([PYTHON, "-m", "pytest", "-k", "test_testutils.py"])


def test_sudo():
    """Run sudo utilities tests."""
    build()
    sh([PYTHON, "-m", "pytest", "-k", "test_sudo.py"])


def test_last_failed():
    """Re-run tests which failed on last run."""
    build()
    test(["--last-failed"])


def test_memleaks():
    """Run memory leaks tests."""
    build()
    sh([PYTHON, "-m", "pytest", "-k", "test_memleaks.py"])


def install_git_hooks():
    """Install GIT pre-commit hook."""
    if os.path.isdir('.git'):
        src = os.path.join(
            ROOT_DIR, "scripts", "internal", "git_pre_commit.py"
        )
        dst = os.path.realpath(
            os.path.join(ROOT_DIR, ".git", "hooks", "pre-commit")
        )
        with open(src) as s:
            with open(dst, "w") as d:
                d.write(s.read())


def bench_oneshot():
    """Benchmarks for oneshot() ctx manager (see #799)."""
    sh([PYTHON, "scripts\\internal\\bench_oneshot.py"])


def bench_oneshot_2():
    """Same as above but using perf module (supposed to be more precise)."""
    sh([PYTHON, "scripts\\internal\\bench_oneshot_2.py"])


def print_access_denied():
    """Print AD exceptions raised by all Process methods."""
    build()
    sh([PYTHON, "scripts\\internal\\print_access_denied.py"])


def print_api_speed():
    """Benchmark all API calls."""
    build()
    sh([PYTHON, "scripts\\internal\\print_api_speed.py"])


def print_sysinfo():
    """Print system info."""
    build()
    from psutil.tests import print_sysinfo

    print_sysinfo()


def generate_manifest():
    """Generate MANIFEST.in file."""
    script = "scripts\\internal\\generate_manifest.py"
    out = subprocess.check_output([PYTHON, script], text=True)
    with open("MANIFEST.in", "w", newline="\n") as f:
        f.write(out)


def get_python(path):
    if not path:
        return sys.executable
    if os.path.isabs(path):
        return path
    # try to look for a python installation given a shortcut name
    path = path.replace('.', '')
    vers = (
        '310-64',
        '311-64',
        '312-64',
    )
    for v in vers:
        pypath = rf"C:\\python{v}\python.exe"
        if path in pypath and os.path.isfile(pypath):
            return pypath


def parse_args():
    parser = argparse.ArgumentParser()
    # option shared by all commands
    parser.add_argument('-p', '--python', help="use python executable path")
    sp = parser.add_subparsers(dest='command', title='targets')
    sp.add_parser('bench-oneshot', help="benchmarks for oneshot()")
    sp.add_parser('bench-oneshot_2', help="benchmarks for oneshot() (perf)")
    sp.add_parser('build', help="build")
    sp.add_parser('clean', help="deletes dev files")
    sp.add_parser('coverage', help="run coverage tests.")
    sp.add_parser('generate-manifest', help="generate MANIFEST.in file")
    sp.add_parser('help', help="print this help")
    sp.add_parser('install', help="build + install in develop/edit mode")
    sp.add_parser('install-git-hooks', help="install GIT pre-commit hook")
    sp.add_parser('install-pip', help="install pip")
    sp.add_parser('install-pydeps-dev', help="install dev python deps")
    sp.add_parser('install-pydeps-test', help="install python test deps")
    sp.add_parser('print-access-denied', help="print AD exceptions")
    sp.add_parser('print-api-speed', help="benchmark all API calls")
    sp.add_parser('print-sysinfo', help="print system info")
    sp.add_parser('test-parallel', help="run tests in parallel")
    test = sp.add_parser('test', help="[ARG] run tests")
    test_by_name = sp.add_parser('test-by-name', help="<ARG> run test by name")
    test_by_regex = sp.add_parser(
        'test-by-regex', help="<ARG> run test by regex"
    )
    sp.add_parser('test-connections', help="run connections tests")
    sp.add_parser('test-contracts', help="run contracts tests")
    sp.add_parser(
        'test-last-failed', help="re-run tests which failed on last run"
    )
    sp.add_parser('test-memleaks', help="run memory leaks tests")
    sp.add_parser('test-misc', help="run misc tests")
    sp.add_parser('test-scripts', help="run scripts tests")
    sp.add_parser('test-platform', help="run windows only tests")
    sp.add_parser('test-process', help="run process tests")
    sp.add_parser('test-process-all', help="run process all tests")
    sp.add_parser('test-system', help="run system tests")
    sp.add_parser('test-sudo', help="run sudo tests")
    sp.add_parser('test-unicode', help="run unicode tests")
    sp.add_parser('test-testutils', help="run test utils tests")
    sp.add_parser('uninstall', help="uninstall psutil")
    sp.add_parser('upload-wheels', help="upload wheel files on PyPI")
    sp.add_parser('wheel', help="create wheel file")

    for p in (test, test_by_name, test_by_regex):
        p.add_argument('arg', type=str, nargs='?', default="", help="arg")

    args = parser.parse_args()

    if not args.command or args.command == 'help':
        parser.print_help(sys.stderr)
        sys.exit(1)

    return args


def main():
    global PYTHON
    args = parse_args()
    # set python exe
    PYTHON = get_python(args.python)
    if not PYTHON:
        return sys.exit(
            f"can't find any python installation matching {args.python!r}"
        )
    os.putenv('PYTHON', PYTHON)
    win_colorprint("using " + PYTHON)

    fname = args.command.replace('-', '_')
    fun = getattr(sys.modules[__name__], fname)  # err if fun not defined
    if args.command == 'test' and args.arg:
        sh([PYTHON, args.arg])  # test a script
    elif args.command == 'test-by-name':
        test_by_name(args.arg)
    elif args.command == 'test-by-regex':
        test_by_regex(args.arg)
    else:
        fun()


if __name__ == '__main__':
    main()
