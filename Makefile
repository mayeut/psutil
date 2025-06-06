# Shortcuts for various tasks (UNIX only).
# To use a specific Python version run: "make install PYTHON=python3.3"
# You can set the variables below from the command line.

# Configurable
PYTHON = python3
ARGS =

# In not in a virtualenv, add --user options for install commands.
SETUP_INSTALL_ARGS = `$(PYTHON) -c \
	"import sys; print('' if hasattr(sys, 'real_prefix') or hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix else '--user')"`
PIP_INSTALL_ARGS = --trusted-host files.pythonhosted.org --trusted-host pypi.org --upgrade
PYTHON_ENV_VARS = PYTHONWARNINGS=always PYTHONUNBUFFERED=1 PSUTIL_DEBUG=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
SUDO = $(if $(filter $(OS),Windows_NT),,sudo -E)
DPRINT = ~/.dprint/bin/dprint

# if make is invoked with no arg, default to `make help`
.DEFAULT_GOAL := help

# install git hook
_ := $(shell mkdir -p .git/hooks/ && ln -sf ../../scripts/internal/git_pre_commit.py .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit)

# ===================================================================
# Install
# ===================================================================

clean:  ## Remove all build files.
	@rm -rfv `find . \
		-type d -name __pycache__ \
		-o -type f -name \*.bak \
		-o -type f -name \*.orig \
		-o -type f -name \*.pyc \
		-o -type f -name \*.pyd \
		-o -type f -name \*.pyo \
		-o -type f -name \*.rej \
		-o -type f -name \*.so \
		-o -type f -name \*.~ \
		-o -type f -name \*\$testfn`
	@rm -rfv \
		*.core \
		*.egg-info \
		*\@psutil-* \
		.coverage \
		.failed-tests.txt \
		.pytest_cache \
		.ruff_cache/ \
		build/ \
		dist/ \
		docs/_build/ \
		htmlcov/ \
		pytest-cache-files* \
		wheelhouse

.PHONY: build
build:  ## Compile (in parallel) without installing.
	@# "build_ext -i" copies compiled *.so files in ./psutil directory in order
	@# to allow "import psutil" when using the interactive interpreter from
	@# within  this directory.
	$(PYTHON_ENV_VARS) $(PYTHON) setup.py build_ext -i --parallel 4
	$(PYTHON_ENV_VARS) $(PYTHON) -c "import psutil"  # make sure it actually worked

install:  ## Install this package as current user in "edit" mode.
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) setup.py develop $(SETUP_INSTALL_ARGS)

uninstall:  ## Uninstall this package via pip.
	cd ..; $(PYTHON_ENV_VARS) $(PYTHON) -m pip uninstall -y -v psutil || true
	$(PYTHON_ENV_VARS) $(PYTHON) scripts/internal/purge_installation.py

install-pip:  ## Install pip (no-op if already installed).
	$(PYTHON) scripts/internal/install_pip.py

install-sysdeps:
	./scripts/internal/install-sysdeps.sh

install-pydeps-test:  ## Install python deps necessary to run unit tests.
	${MAKE} install-pip
	$(PYTHON) -m pip install $(PIP_INSTALL_ARGS) -e .[test]

install-pydeps-dev:  ## Install python deps meant for local development.
	${MAKE} install-git-hooks
	${MAKE} install-pip
	$(PYTHON) -m pip install $(PIP_INSTALL_ARGS) -e .[test,dev]

install-git-hooks:  ## Install GIT pre-commit hook.
	ln -sf ../../scripts/internal/git_pre_commit.py .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit

# ===================================================================
# Tests
# ===================================================================

test:  ## Run all tests. To run a specific test do "make test ARGS=psutil.tests.test_system.TestDiskAPIs"
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest --ignore=psutil/tests/test_memleaks.py --ignore=psutil/tests/test_sudo.py $(ARGS)

test-parallel:  ## Run all tests in parallel.
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest --ignore=psutil/tests/test_memleaks.py -p xdist -n auto --dist loadgroup $(ARGS)

test-process:  ## Run process-related API tests.
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) psutil/tests/test_process.py

test-process-all:  ## Run tests which iterate over all process PIDs.
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) psutil/tests/test_process_all.py

test-system:  ## Run system-related API tests.
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) psutil/tests/test_system.py

test-misc:  ## Run miscellaneous tests.
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) psutil/tests/test_misc.py

test-scripts:  ## Run scripts tests.
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) psutil/tests/test_scripts.py

test-testutils:  ## Run test utils tests.
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) psutil/tests/test_testutils.py

test-unicode:  ## Test APIs dealing with strings.
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) psutil/tests/test_unicode.py

test-contracts:  ## APIs sanity tests.
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) psutil/tests/test_contracts.py

test-connections:  ## Test psutil.net_connections() and Process.net_connections().
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) psutil/tests/test_connections.py

test-posix:  ## POSIX specific tests.
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) psutil/tests/test_posix.py

test-platform:  ## Run specific platform tests only.
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) psutil/tests/test_`$(PYTHON) -c 'import psutil; print([x.lower() for x in ("LINUX", "BSD", "OSX", "SUNOS", "WINDOWS", "AIX") if getattr(psutil, x)][0])'`.py

test-memleaks:  ## Memory leak tests.
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest $(ARGS) psutil/tests/test_memleaks.py

test-last-failed:  ## Re-run tests which failed on last run
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) -m pytest --last-failed $(ARGS)

test-coverage:  ## Run test coverage.
	${MAKE} build
	# Note: coverage options are controlled by .coveragerc file
	rm -rf .coverage htmlcov
	$(PYTHON_ENV_VARS) $(PYTHON) -m coverage run -m pytest --ignore=psutil/tests/test_memleaks.py $(ARGS)
	$(PYTHON) -m coverage report
	@echo "writing results to htmlcov/index.html"
	$(PYTHON) -m coverage html
	$(PYTHON) -m webbrowser -t htmlcov/index.html

test-sudo:  ## Run tests requiring root privileges.
	# Use unittest runner because pytest may not be installed as root.
	$(SUDO) $(PYTHON_ENV_VARS) $(PYTHON) -m unittest -v psutil.tests.test_sudo

test-ci:  ## Run tests on GitHub CI.
	${MAKE} install-sysdeps
	PIP_BREAK_SYSTEM_PACKAGES=1 ${MAKE} install-pydeps-test
	${MAKE} print-sysinfo
	$(PYTHON) -m pip list
	${MAKE} test
	${MAKE} test-memleaks
	${MAKE} test-sudo

lint-ci:  ## Run all linters on GitHub CI.
	python3 -m pip install -U black ruff rstcheck toml-sort sphinx
	curl -fsSL https://dprint.dev/install.sh | sh
	${MAKE} lint-all

# ===================================================================
# Linters
# ===================================================================

ruff:  ## Run ruff linter.
	@git ls-files '*.py' | xargs $(PYTHON) -m ruff check --output-format=concise

black:  ## Run black formatter.
	@git ls-files '*.py' | xargs $(PYTHON) -m black --check --safe

dprint:
	@$(DPRINT) check --list-different

lint-c:  ## Run C linter.
	@git ls-files '*.c' '*.h' | xargs $(PYTHON) scripts/internal/clinter.py

lint-rst:  ## Run linter for .rst files.
	@git ls-files '*.rst' | xargs rstcheck --config=pyproject.toml

lint-toml:  ## Run linter for pyproject.toml.
	@git ls-files '*.toml' | xargs toml-sort --check

lint-all:  ## Run all linters
	${MAKE} black
	${MAKE} ruff
	${MAKE} dprint
	${MAKE} lint-c
	${MAKE} lint-rst
	${MAKE} lint-toml

# --- not mandatory linters (just run from time to time)

pylint:  ## Python pylint
	@git ls-files '*.py' | xargs $(PYTHON) -m pylint --rcfile=pyproject.toml --jobs=0 $(ARGS)

vulture:  ## Find unused code
	@git ls-files '*.py' | xargs $(PYTHON) -m vulture $(ARGS)

# ===================================================================
# Fixers
# ===================================================================

fix-black:
	@git ls-files '*.py' | xargs $(PYTHON) -m black

fix-ruff:
	@git ls-files '*.py' | xargs $(PYTHON) -m ruff check --fix --output-format=concise $(ARGS)

fix-toml:  ## Fix pyproject.toml
	@git ls-files '*.toml' | xargs toml-sort

fix-dprint:
	@$(DPRINT) fmt

fix-all:  ## Run all code fixers.
	${MAKE} fix-ruff
	${MAKE} fix-black
	${MAKE} fix-toml
	${MAKE} fix-dprint

# ===================================================================
# Distribution
# ===================================================================

sdist:  ## Create tar.gz source distribution.
	${MAKE} generate-manifest
	$(PYTHON_ENV_VARS) $(PYTHON) setup.py sdist

download-wheels:  ## Download latest wheels hosted on github.
	$(PYTHON_ENV_VARS) $(PYTHON) scripts/internal/download_wheels.py --tokenfile=~/.github.token
	${MAKE} print-dist

create-wheels:  ## Create .whl files
	$(PYTHON_ENV_VARS) $(PYTHON) setup.py bdist_wheel
	${MAKE} check-wheels

check-sdist:  ## Check sanity of source distribution.
	$(PYTHON_ENV_VARS) $(PYTHON) -m virtualenv --clear --no-wheel --quiet build/venv
	$(PYTHON_ENV_VARS) build/venv/bin/python -m pip install -v --isolated --quiet dist/*.tar.gz
	$(PYTHON_ENV_VARS) build/venv/bin/python -c "import os; os.chdir('build/venv'); import psutil"
	$(PYTHON) -m twine check --strict dist/*.tar.gz

check-wheels:  ## Check sanity of wheels.
	$(PYTHON) -m abi3audit --verbose --strict dist/*-abi3-*.whl
	$(PYTHON) -m twine check --strict dist/*.whl

pre-release:  ## Check if we're ready to produce a new release.
	${MAKE} clean
	${MAKE} sdist
	${MAKE} check-sdist
	${MAKE} install
	@$(PYTHON) -c \
		"import requests, sys; \
		from packaging.version import parse; \
		from psutil import __version__; \
		res = requests.get('https://pypi.org/pypi/psutil/json', timeout=5); \
		versions = sorted(res.json()['releases'], key=parse, reverse=True); \
		sys.exit('version %r already exists on PYPI' % __version__) if __version__ in versions else 0"
	@$(PYTHON) -c \
		"from psutil import __version__ as ver; \
		doc = open('docs/index.rst').read(); \
		history = open('HISTORY.rst').read(); \
		assert ver in doc, '%r not found in docs/index.rst' % ver; \
		assert ver in history, '%r not found in HISTORY.rst' % ver; \
		assert 'XXXX' not in history, 'XXXX found in HISTORY.rst';"
	${MAKE} download-wheels
	${MAKE} check-wheels
	${MAKE} print-hashes
	${MAKE} print-dist

release:  ## Upload a new release.
	${MAKE} check-sdist
	${MAKE} check-wheels
	$(PYTHON) -m twine upload dist/*.tar.gz
	$(PYTHON) -m twine upload dist/*.whl
	${MAKE} git-tag-release

generate-manifest:  ## Generates MANIFEST.in file.
	$(PYTHON) scripts/internal/generate_manifest.py > MANIFEST.in

print-dist:  ## Print downloaded wheels / tar.gs
	$(PYTHON) scripts/internal/print_dist.py

git-tag-release:  ## Git-tag a new release.
	git tag -a release-`python3 -c "import setup; print(setup.get_version())"` -m `git rev-list HEAD --count`:`git rev-parse --short HEAD`
	git push --follow-tags

# ===================================================================
# Printers
# ===================================================================

print-announce:  ## Print announce of new release.
	@$(PYTHON) scripts/internal/print_announce.py

print-timeline:  ## Print releases' timeline.
	@$(PYTHON) scripts/internal/print_timeline.py

print-access-denied: ## Print AD exceptions
	${MAKE} build
	@$(PYTHON_ENV_VARS) $(PYTHON) scripts/internal/print_access_denied.py

print-api-speed:  ## Benchmark all API calls
	${MAKE} build
	@$(PYTHON_ENV_VARS) $(PYTHON) scripts/internal/print_api_speed.py $(ARGS)

print-downloads:  ## Print PYPI download statistics
	$(PYTHON) scripts/internal/print_downloads.py

print-hashes:  ## Prints hashes of files in dist/ directory
	$(PYTHON) scripts/internal/print_hashes.py dist/

print-sysinfo:  ## Prints system info
	$(PYTHON) -c "from psutil.tests import print_sysinfo; print_sysinfo()"

# ===================================================================
# Misc
# ===================================================================

grep-todos:  ## Look for TODOs in the source files.
	git grep -EIn "TODO|FIXME|XXX"

bench-oneshot:  ## Benchmarks for oneshot() ctx manager (see #799).
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) scripts/internal/bench_oneshot.py

bench-oneshot-2:  ## Same as above but using perf module (supposed to be more precise)
	${MAKE} build
	$(PYTHON_ENV_VARS) $(PYTHON) scripts/internal/bench_oneshot_2.py

check-broken-links:  ## Look for broken links in source files.
	git ls-files | xargs $(PYTHON) -Wa scripts/internal/check_broken_links.py

check-manifest:  ## Inspect MANIFEST.in file.
	$(PYTHON) -m check_manifest -v $(ARGS)

help: ## Display callable targets.
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'
