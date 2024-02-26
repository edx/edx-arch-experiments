.PHONY: clean compile_translations coverage diff_cover docs dummy_translations \
        extract_translations fake_translations help pii_check pull_translations push_translations \
        quality requirements selfcheck test test-all upgrade validate upgrade_package

.DEFAULT_GOAL := help

# For opening files in a browser. Use like: $(BROWSER)relative/path/to/file.html
BROWSER := python -m webbrowser file://$(CURDIR)/

help: ## display this help message
	@echo "Please use \`make <target>' where <target> is one of"
	@awk -F ':.*?## ' '/^[a-zA-Z]/ && NF==2 {printf "\033[36m  %-25s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST) | sort

clean: ## remove generated byte code, coverage reports, and build artifacts
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	coverage erase
	rm -fr build/
	rm -fr dist/
	rm -fr *.egg-info

coverage: clean ## generate and view HTML coverage report
	pytest --cov-report html
	$(BROWSER)htmlcov/index.html

docs: ## generate Sphinx HTML documentation, including API docs
	tox -e docs
	$(BROWSER)docs/_build/html/index.html

# Define CMD_PIP_COMPILE_OPTS=-v to get more information during make upgrade.
CMD_PIP_COMPILE ?= pip-compile --rebuild --upgrade --allow-unsafe $(CMD_PIP_COMPILE_OPTS)

upgrade: export CUSTOM_COMPILE_COMMAND=make upgrade
upgrade: ## update the requirements/*.txt files with the latest packages satisfying requirements/*.in
	pip install -qr requirements/pip-tools.txt
	# Make sure to compile files after any other files they include!
	$(CMD_PIP_COMPILE) --rebuild -o requirements/pip.txt requirements/pip.in
	$(CMD_PIP_COMPILE) -o requirements/pip-tools.txt requirements/pip-tools.in
	pip install -qr requirements/pip.txt
	pip install -qr requirements/pip-tools.txt
	$(CMD_PIP_COMPILE) -o requirements/base.txt requirements/base.in
	$(CMD_PIP_COMPILE) -o requirements/test.txt requirements/test.in
	$(CMD_PIP_COMPILE) -o requirements/doc.txt requirements/doc.in
	$(CMD_PIP_COMPILE) -o requirements/scripts.txt requirements/scripts.in
	$(CMD_PIP_COMPILE) -o requirements/quality.txt requirements/quality.in
	$(CMD_PIP_COMPILE) -o requirements/ci.txt requirements/ci.in
	$(CMD_PIP_COMPILE) -o requirements/dev.txt requirements/dev.in
	# Let tox control the Django version for tests
	sed '/^[dD]jango==/d' requirements/test.txt > requirements/test.tmp
	mv requirements/test.tmp requirements/test.txt


upgrade_package: ## update the requirements/*.txt file with the latest version of $package
	@test -n "$(package)" || { echo "\nUsage: make upgrade_package package=...\n"; exit 1; }
	CMD_PIP_COMPILE="pip-compile --rebuild --upgrade-package $(package)" make upgrade

quality: ## check coding style with pycodestyle and pylint
	tox -e quality

pii_check: ## check for PII annotations on all Django models
	tox -e pii_check

requirements: ## install development environment requirements
	pip install -qr requirements/pip-tools.txt
	pip-sync requirements/dev.txt requirements/private.*

test: clean ## run tests in the current virtualenv
	pytest

diff_cover: test ## find diff lines that need test coverage
	diff-cover coverage.xml

test-all: quality pii_check ## run tests on every supported Python/Django combination
	tox

validate: quality pii_check test ## run tests and quality checks

selfcheck: ## check that the Makefile is well-formed
	@echo "The Makefile is well-formed."

## Localization targets

extract_translations: ## extract strings to be translated, outputting .mo files
	rm -rf docs/_build
	cd edx_arch_experiments && ../manage.py makemessages -l en -v1 -d django
	cd edx_arch_experiments && ../manage.py makemessages -l en -v1 -d djangojs

compile_translations: ## compile translation files, outputting .po files for each supported language
	cd edx_arch_experiments && ../manage.py compilemessages

detect_changed_source_translations:
	cd edx_arch_experiments && i18n_tool changed

pull_translations: ## pull translations from Transifex
	tx pull -t -a -f --mode reviewed

push_translations: ## push source translation files (.po) from Transifex
	tx push -s

dummy_translations: ## generate dummy translation (.po) files
	cd edx_arch_experiments && i18n_tool dummy

build_dummy_translations: extract_translations dummy_translations compile_translations ## generate and compile dummy translation files

validate_translations: build_dummy_translations detect_changed_source_translations ## validate translations

## Docker in this repo is only supported for running tests locally
## as an alternative to virtualenv natively - johnnagro 2023-09-06
test-shell: ## Run a shell, as root, on the specified service container
	docker-compose run -u 0 test-shell env TERM=$(TERM) /bin/bash
