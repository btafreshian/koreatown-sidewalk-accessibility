.PHONY: install download process maps qa all test clean

PYTHON ?= python

install:
	$(PYTHON) -m pip install -r requirements.txt

download:
	$(PYTHON) -m src.pipeline --step download

process:
	$(PYTHON) -m src.pipeline --step process

maps:
	$(PYTHON) -m src.pipeline --step maps

qa:
	$(PYTHON) -m src.pipeline --step qa

all:
	$(PYTHON) -m src.pipeline

test:
	$(PYTHON) -m pytest

clean:
	$(PYTHON) -c "import shutil, pathlib; [shutil.rmtree(p, ignore_errors=True) for p in [pathlib.Path('data/raw'), pathlib.Path('data/interim'), pathlib.Path('data/processed'), pathlib.Path('outputs/maps'), pathlib.Path('outputs/tables'), pathlib.Path('outputs/html')]]; pathlib.Path('outputs/qgis/koreatown_sidewalk_accessibility.gpkg').unlink(missing_ok=True); [p.mkdir(parents=True, exist_ok=True) for p in [pathlib.Path('data/raw'), pathlib.Path('data/interim'), pathlib.Path('data/processed'), pathlib.Path('outputs/maps'), pathlib.Path('outputs/tables'), pathlib.Path('outputs/html')]]"

