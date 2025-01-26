ACTIVATE := . .venv/bin/activate

define install_poetry
	if ! command -v poetry &> /dev/null; then \
    	pip install --upgrade pip; \
		pip install 'poetry>=1.0.0,<2.0.0'; \
	else \
    	echo "Poetry is already installed."; \
	fi
endef

define deactivate_virtualenv
    if [ -n "$$VIRTUAL_ENV" ]; then \
        unset VIRTUAL_ENV; \
        unset PYTHONHOME; \
        unset -f pydoc >/dev/null 2>&1; \
        OLD_PATH="$$PATH"; \
        PATH=$$(echo -n "$$PATH" | awk -v RS=: -v ORS=: '/\/virtualenv\/bin$$/ {next} {print}'); \
        export PATH; \
        hash -r; \
        echo "Deactivated the virtual environment."; \
    fi
endef
.SILENT: install

install:
	$(call deactivate_virtualenv) && \
	$(call install_poetry) && \
	poetry install --with dev

format:
	@poetry run ruff format .
	@poetry run ruff check . --fix --select I

lint:
	@poetry run ruff check .
	@poetry run ruff format --check .
	@poetry run mypy .

run:
	@poetry run python -m src.main