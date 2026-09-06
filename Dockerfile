# Reproduction environment for CivicDividendOS.
#
# Contains the simulation, the test suite, the figure and table pipeline, and a
# LaTeX installation sufficient to build the manuscript. Built and exercised;
# see docs/reproducibility.md for what was verified and what was not.
FROM python:3.11.9-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONHASHSEED=0 \
    PIP_NO_CACHE_DIR=1

# LaTeX is a large layer. Build with --build-arg WITH_LATEX=0 to skip it when
# only the simulation and tests are needed.
ARG WITH_LATEX=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      make git ca-certificates \
 && if [ "$WITH_LATEX" = "1" ]; then apt-get install -y --no-install-recommends \
      texlive-latex-recommended texlive-latex-extra texlive-fonts-recommended \
      texlive-science texlive-pictures latexmk ; fi \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /work

COPY requirements.txt requirements-dev.txt ./
RUN pip install --upgrade pip==24.0 && pip install -r requirements-dev.txt

COPY . .
RUN pip install -e . --no-deps

# Fail the build if the environment cannot reproduce the audited baseline.
RUN python -m pytest tests/unit tests/numerical -q

CMD ["make", "reproduce"]
