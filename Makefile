.DEFAULT_GOAL := help

# Some Windows launchers omit OS; native GNU Make still reports a MinGW host.
ifneq ($(filter Windows_NT,$(OS))$(findstring mingw,$(MAKE_HOST)),)
SHELL := pwsh.exe
.SHELLFLAGS := -NoLogo -NoProfile -NonInteractive -Command
PYTHON ?= D:/anaconda/envs/py311/python.exe
PYRUN = & "$(PYTHON)"
else
# Activate the intended Conda environment before invoking make.
PYTHON ?= python
PYRUN = "$(PYTHON)"
endif

HOST ?= 127.0.0.1
PORT ?= 8000
MANAGE := backend/manage.py

.PHONY: help install check migrate run test

help:
	@echo "install  Install Python dependencies"
	@echo "check    Check Django configuration"
	@echo "migrate  Apply Django migrations"
	@echo "run      Start the local development server"
	@echo "test     Verify routes and scaffold boundaries"
	@echo "Override PYTHON with your Conda interpreter path."

install:
	$(PYRUN) -m pip install -r requirements.txt

check:
	$(PYRUN) $(MANAGE) check

migrate:
	$(PYRUN) $(MANAGE) migrate --noinput

run:
	$(PYRUN) $(MANAGE) runserver $(HOST):$(PORT)

test:
	$(PYRUN) $(MANAGE) test tests --noinput
