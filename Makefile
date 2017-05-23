PYTHON ?= python
PHP ?= php

all:
	$(PYTHON) -mpooledbismuth -v

.PHONY: webui
webui:
	php -t webui -S 0.0.0.0:8031

clean:
	find . -name '*.pyc'  | xargs -n 1 rm
	rm -rf tests/data data/*

.PHONY: test
test:
	rm -rf tests/data
	mkdir -p tests/data/audit tests/data/done
	PYTHONPATH=. pytest -t tests -i --color