PYTHON := /opt/anaconda3/bin/python

.PHONY: all build check preview clean

all: build check

build:
	$(PYTHON) scripts/build_profile.py

check:
	$(PYTHON) scripts/verify_build.py

preview: build
	$(PYTHON) scripts/verify_build.py --render-only

clean:
	rm -f assets/*.svg preview-dark.png preview-light.png
