"""Write the environment, Docker and Makefile definitions.

Kept as a script so the pinned versions have one source of truth: the runtime
pins here must match ``pyproject.toml`` and the version pair under which the
audited campaign reproduces bit-exactly (Python 3.11.9 / NumPy 1.26.4).
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

RUNTIME = """# Runtime dependencies. Python 3.11.9.
#
# This exact pair -- Python 3.11.9 with NumPy 1.26.4 -- is the combination under
# which the campaign reproduces bit-exactly. Other versions may reproduce; this
# pair is verified.
numpy==1.26.4
PyYAML==6.0.1
"""

DEV = """-r requirements.txt

# Testing and linting
pytest==8.2.2
pytest-cov==5.0.0
ruff==0.5.5

# Figures and tables
matplotlib==3.8.4
pandas==2.2.2
"""

CONDA = """name: cdos
channels:
  - conda-forge
dependencies:
  - python=3.11.9
  - numpy=1.26.4
  - pyyaml=6.0.1
  - matplotlib=3.8.4
  - pandas=2.2.2
  - pytest=8.2.2
  - pip
  - pip:
      - pytest-cov==5.0.0
      - ruff==0.5.5
"""

DOCKERFILE = """# Reproduction environment for CivicDividendOS.
#
# Contains the simulation, the test suite, the figure and table pipeline, and a
# LaTeX installation sufficient to build the manuscript. Built and exercised;
# see docs/reproducibility.md for what was verified and what was not.
FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \\
    PYTHONUNBUFFERED=1 \\
    PYTHONHASHSEED=0 \\
    PIP_NO_CACHE_DIR=1

# LaTeX is a large layer. Build with --build-arg WITH_LATEX=0 to skip it when
# only the simulation and tests are needed.
ARG WITH_LATEX=1

RUN apt-get update && apt-get install -y --no-install-recommends \\
      make git ca-certificates \\
 && if [ "$WITH_LATEX" = "1" ]; then apt-get install -y --no-install-recommends \\
      texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \\
      texlive-science texlive-pictures latexmk ; fi \\
 && rm -rf /var/lib/apt/lists/*

WORKDIR /work

COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip==24.0 && pip install -r requirements-dev.txt

COPY . .
RUN pip install -e . --no-deps

# Fail the build if the environment cannot reproduce the audited baseline.
RUN python -m pytest tests/unit tests/numerical -q

CMD ["make", "reproduce"]
"""

MAKEFILE = """# CivicDividendOS reproduction pipeline.
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

.PHONY: help install test test-fast smoke reproduce experiments ablations \\
        main tables figures paper clean distclean lint audit verify

help:
\t@grep -E '^#   ' $(MAKEFILE_LIST) | sed 's/^#   //'

install:
\t$(PYTHON) -m pip install -r requirements-dev.txt
\t$(PYTHON) -m pip install -e . --no-deps

lint:
\t$(PYTHON) -m ruff check src tests scripts

test:
\t$(PYTEST) tests

test-fast:
\t$(PYTEST) tests -m "not slow"

smoke:
\t$(PYTHON) scripts/run_campaign.py --seeds 2 --arms B0 B1 B6 B6c \\
\t\t--out results/raw/smoke.json --experiment-id smoke

main:
\t$(PYTHON) scripts/run_campaign.py --seeds $(SEEDS) \\
\t\t--out results/raw/main.json --experiment-id main

experiments:
\t$(PYTHON) scripts/run_all_experiments.py --pattern 'E*'

ablations:
\t$(PYTHON) scripts/run_all_experiments.py --pattern 'A*'

reproduce: main experiments ablations tables figures
\t@echo "reproduction complete; see results/manifests for provenance"

tables:
\t$(PYTHON) scripts/make_tables.py

figures:
\t$(PYTHON) scripts/make_figures.py

verify:
\t$(PYTHON) scripts/verify_generated.py

paper: tables figures
\tlatexmk -pdf -interaction=nonstopmode -halt-on-error $(PAPER).tex

audit:
\tcd audit && $(PYTHON) run_all.py --quick

clean:
\trm -f *.aux *.log *.out *.toc *.fls *.fdb_latexmk *.bbl *.blg
\trm -rf .pytest_cache .ruff_cache
\tfind . -name '__pycache__' -type d -prune -exec rm -rf {} +

distclean: clean
\trm -rf results/raw/*.json results/processed/*.json figures/*.pdf \\
\t\ttables/*.tex paper/generated/*.tex
"""


def main() -> None:
    (ROOT / "requirements.txt").write_text(RUNTIME, encoding="utf-8", newline="\n")
    (ROOT / "requirements-dev.txt").write_text(DEV, encoding="utf-8", newline="\n")
    (ROOT / "environment.yml").write_text(CONDA, encoding="utf-8", newline="\n")
    (ROOT / "Dockerfile").write_text(DOCKERFILE, encoding="utf-8", newline="\n")
    (ROOT / "Makefile").write_text(MAKEFILE, encoding="utf-8", newline="\n")
    print("wrote requirements.txt, requirements-dev.txt, environment.yml, "
          "Dockerfile, Makefile")


if __name__ == "__main__":
    main()
