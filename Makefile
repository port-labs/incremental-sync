install:
	@poetry install

format:
	@poetry run ruff format .
	@poetry run ruff check . --fix --select I

lint:
	@poetry run ruff check .
	@poetry run ruff format --check .
	@poetry run mypy .