.PHONY: all data features train test clean model check-model

# --- The pipeline ----------------------------------------------------------
# Use the pinned venv when it exists: a bare `python` can resolve to conda,
# whose scikit-learn moves the hgb row. Override with `make PYTHON=...`.
PYTHON ?= $(if $(wildcard .venv/bin/python),.venv/bin/python,python)

all: data features train

data:
	$(PYTHON) -m src.ingest

features:
	$(PYTHON) -m src.features

train:
	$(PYTHON) -m src.train

test:
	$(PYTHON) -m pytest tests/ -q

clean:
	rm -f data/processed/*.parquet reports/metrics.json reports/*.png

# --- The agent model (open weights, local) ----------------------------------
# Builds `bikeshare-coder`: the base model plus a 64k context window, which
# Claude Code needs and Ollama does not give you by default. Pick a larger
# BASE if your machine has the memory (see README.md).
BASE ?= qwen3.5:9b

model:
	ollama pull $(BASE)
	sed "s|^FROM .*|FROM $(BASE)|" model/Modelfile | ollama create bikeshare-coder -f -

check-model:
	bash model/check.sh
