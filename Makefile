# CivicDividendOS reproduction pipeline.
#
#   make install     install the pinned environment
#   make test        the whole test suite
#   make smoke       a two-seed campaign, about a minute
#   make reproduce   the full experiment matrix (hours)
#   make tables      regenerate every LaTeX table from results
#   make figures     regenerate every figure from results
#   make paper       compile the manuscript
#   make clean       remove generated artefacts, keep results
#
# Nothing in the paper's results tables is typed by hand: `make tables`
# regenerates all of them from results/, and CI fails if they drift.

PYTHON  ?= python
PYTEST  ?= $(PYTHON) -m pytest
SEEDS   ?= 50
PAPER   ?= CivicDividendOS_v2

.PHONY: help install test test-fast smoke reproduce experiments ablations \
        main tables figures paper clean distclean lint audit verify

help:
	@grep -E '^#   ' $(MAKEFILE_LIST) | sed 's/^#   //'

install:
	$(PYTHON) -m pip install -r requirements-dev.txt
	$(PYTHON) -m pip install -e . --no-deps

lint:
	$(PYTHON) -m ruff check src tests scripts

test:
	$(PYTEST) tests

test-fast:
	$(PYTEST) tests -m "not slow"

smoke:
	$(PYTHON) scripts/run_campaign.py --seeds 2 --arms B0 B1 B6 B6c \
		--out results/raw/smoke.json --experiment-id smoke

main:
	$(PYTHON) scripts/run_campaign.py --seeds $(SEEDS) \
		--out results/raw/main.json --experiment-id main

experiments:
	$(PYTHON) scripts/run_all_experiments.py --pattern 'E*'

ablations:
	$(PYTHON) scripts/run_all_experiments.py --pattern 'A*'

reproduce: main experiments ablations tables figures
	@echo "reproduction complete; see results/manifests for provenance"

tables:
	$(PYTHON) scripts/make_tables.py

figures:
	$(PYTHON) scripts/make_figures.py

verify:
	$(PYTHON) scripts/verify_generated.py

paper: tables figures
	latexmk -pdf -interaction=nonstopmode -halt-on-error $(PAPER).tex

audit:
	cd audit && $(PYTHON) run_all.py --quick

clean:
	rm -f *.aux *.log *.out *.toc *.fls *.fdb_latexmk *.bbl *.blg
	rm -rf .pytest_cache .ruff_cache
	find . -name '__pycache__' -type d -prune -exec rm -rf {} +

distclean: clean
	rm -rf results/raw/*.json results/processed/*.json figures/*.pdf \
		tables/*.tex paper/generated/*.tex
