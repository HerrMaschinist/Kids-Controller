PYTEST ?= /opt/kids_controller/.venv/bin/pytest

.PHONY: test deploy drift verify

test:
	$(PYTEST) tests/ -q

deploy:
	bash scripts/deploy.sh

drift:
	bash scripts/check_drift.sh

verify:
	bash scripts/verify_live.sh
