# ============================================================
# sovereignagents — zeo Makefile
# ============================================================

GREEN  := $(shell tput -Txterm setaf 2 2>/dev/null || echo "")
YELLOW := $(shell tput -Txterm setaf 3 2>/dev/null || echo "")
WHITE  := $(shell tput -Txterm setaf 7 2>/dev/null || echo "")
BLUE   := $(shell tput -Txterm setaf 4 2>/dev/null || echo "")
RED    := $(shell tput -Txterm setaf 1 2>/dev/null || echo "")
RESET  := $(shell tput -Txterm sgr0 2>/dev/null || echo "")

SHELL := /bin/bash

VENV_NAME := .venv
REPO_ROOT := $(shell pwd)
PYTHON := $(REPO_ROOT)/$(VENV_NAME)/bin/python
UV := $(shell command -v uv 2>/dev/null || echo "uv")

SRC := src/zero_employee
TESTS := tests

.DEFAULT_GOAL := help

help: ## Show this help menu
	@echo ""
	@echo "${YELLOW}zero-employee — Development & Governance Guide${RESET}"
	@echo ""
	@echo "${YELLOW}Setup:${RESET}"
	@echo "  ${GREEN}make setup${RESET}             - Full dev setup (venv + editable install + dev deps)"
	@echo "  ${GREEN}make check-env${RESET}         - Verify virtual environment & imports"
	@echo ""
	@echo "${YELLOW}THE GATE (run before every commit):${RESET}"
	@echo "  ${GREEN}make verify${RESET}            - Fast doctrine gate (format-check + lint + tests)"
	@echo "  ${GREEN}make verify-full${RESET}       - Clean caches + reinstall + full verify"
	@echo ""
	@echo "${YELLOW}Individual Checks:${RESET}"
	@echo "  ${GREEN}make format${RESET}            - Auto-fix code formatting (ruff)"
	@echo "  ${GREEN}make format-check${RESET}      - Check formatting only"
	@echo "  ${GREEN}make lint${RESET}              - Run ruff linting checks"
	@echo "  ${GREEN}make typecheck${RESET}         - Run mypy type checking"
	@echo "  ${GREEN}make test${RESET}              - Run pytest suite via uv"
	@echo "  ${GREEN}make dogfood${RESET}           - Run zeo on sovereignagents corpus"
	@echo ""
	@echo "${YELLOW}Tool Installation:${RESET}"
	@echo "  ${GREEN}make install-tool${RESET}      - Install zeo globally via uv tool"
	@echo ""
	@echo "${YELLOW}Clean:${RESET}"
	@echo "  ${GREEN}make clean-caches${RESET}      - Remove test/lint caches and pyc files"
	@echo "  ${GREEN}make clean${RESET}             - Remove build artifacts and caches"
	@echo "  ${GREEN}make clean-all${RESET}         - Remove build artifacts and .venv"
	@echo ""
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_.-]+:.*## / {printf "  ${YELLOW}%-20s${GREEN}%s${RESET}\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""

.PHONY: env
env: ## Create virtual environment using uv
	@echo "${BLUE}Creating virtual environment with uv...${RESET}"
	# --clear: never prompt when .venv already exists. An interactive "replace it?"
	# confirmation during `make verify-full` leaves leftover keystrokes (e.g. typing
	# "yes" when only "y" is consumed) in the shell buffer as a bogus next command.
	@$(UV) venv --clear $(VENV_NAME)
	@echo "${GREEN}✓ Virtual environment created in $(VENV_NAME)${RESET}"

.PHONY: install
install: ## Install zeo in editable mode
	@echo "${BLUE}Installing zero-employee in editable mode...${RESET}"
	@if [ ! -d "$(VENV_NAME)" ]; then $(MAKE) --no-print-directory env; fi
	@$(UV) pip install -e ".[dev]" --python $(PYTHON) 2>/dev/null || $(UV) pip install -e . --python $(PYTHON)
	@echo "${GREEN}✓ zeo installed${RESET}"

.PHONY: setup
setup: ## Create environment and install all dependencies
	@echo "${BLUE}Setting up zeo development environment...${RESET}"
	@$(MAKE) --no-print-directory env
	@$(MAKE) --no-print-directory install
	@$(MAKE) --no-print-directory check-env

.PHONY: check-env
check-env: ## Verify virtual environment is active and zero_employee is importable
	@echo "${BLUE}Checking environment...${RESET}"
	@if [ ! -f "$(PYTHON)" ]; then echo "${RED}Virtual environment not found at $(PYTHON). Run 'make setup'.${RESET}"; exit 1; fi
	@$(PYTHON) --version
	@$(PYTHON) -c "import zero_employee; print(f'OK: zero_employee at {zero_employee.__file__}')" || (echo "${RED}Import failed — run 'make setup'${RESET}" && exit 1)
	@echo "${GREEN}✓ Environment check passed${RESET}"

.PHONY: verify
verify: ## The doctrine gate: format-check + lint + tests
	@echo "${BLUE}Running zeo doctrine gate...${RESET}"
	@echo ""
	@echo "${BLUE}[1/3] format-check${RESET}"
	@$(MAKE) --no-print-directory format-check
	@echo ""
	@echo "${BLUE}[2/3] lint${RESET}"
	@$(MAKE) --no-print-directory lint
	@echo ""
	@echo "${BLUE}[3/3] test${RESET}"
	@$(MAKE) --no-print-directory test
	@echo ""
	@echo "${GREEN}=== make verify GREEN ===${RESET}"

.PHONY: verify-full
verify-full: ## Full gate: clean caches + fresh install + verify
	@echo "${BLUE}Running FULL verification (fresh install)...${RESET}"
	@$(MAKE) --no-print-directory clean-caches
	@$(MAKE) --no-print-directory setup
	@$(MAKE) --no-print-directory verify
	@echo ""
	@echo "${GREEN}=== make verify-full GREEN ===${RESET}"

.PHONY: format
format: ## Format code with ruff
	@echo "${BLUE}Formatting code with ruff...${RESET}"
	@if $(UV) run ruff --version >/dev/null 2>&1; then $(UV) run ruff format $(SRC) $(TESTS); $(UV) run ruff check --fix $(SRC) $(TESTS); else echo "${YELLOW}ruff not found, skipping format${RESET}"; fi

.PHONY: format-check
format-check: ## Check formatting only
	@echo "${BLUE}Checking formatting with ruff...${RESET}"
	@if $(UV) run ruff --version >/dev/null 2>&1; then $(UV) run ruff format --check $(SRC) $(TESTS); else echo "${YELLOW}ruff not found, skipping format-check${RESET}"; fi

.PHONY: lint
lint: ## Run ruff linter
	@echo "${BLUE}Running ruff linter...${RESET}"
	@if $(UV) run ruff --version >/dev/null 2>&1; then $(UV) run ruff check $(SRC) $(TESTS); else echo "${YELLOW}ruff not found, skipping lint${RESET}"; fi

.PHONY: typecheck
typecheck: ## Run mypy strict type checking
	@echo "${BLUE}Running mypy...${RESET}"
	@if $(UV) run mypy --version >/dev/null 2>&1; then $(UV) run mypy $(SRC); else echo "${YELLOW}mypy not found, skipping typecheck${RESET}"; fi

.PHONY: test
test: ## Run test suite via uv pytest
	@echo "${BLUE}Running pytest suite via uv...${RESET}"
	@$(UV) run pytest -q

.PHONY: dogfood
dogfood: ## Run zeo against sovereignagents sows repo
	@echo "${BLUE}Dogfooding zeo...${RESET}"
	@if [ -d "../sovereignagents-sows" ]; then $(UV) run zeo ../sovereignagents-sows; elif [ -d "../org" ]; then $(UV) run zeo ../org; else echo "${YELLOW}No target corpus found at ../sovereignagents-sows or ../org${RESET}"; fi

.PHONY: install-tool
install-tool: ## Install zeo CLI globally via uv tool
	@echo "${BLUE}Installing zero-employee as global uv tool...${RESET}"
	@$(UV) tool install --force .
	@echo "${GREEN}✓ zeo installed as global uv tool${RESET}"

.PHONY: clean-caches
clean-caches: ## Clear test, lint, and Python bytecode caches
	@echo "${BLUE}Clearing caches...${RESET}"
	@rm -rf .coverage .mypy_cache .pytest_cache .ruff_cache
	@find . -type d -name "__pycache__" -not -path "./$(VENV_NAME)/*" -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -not -path "./$(VENV_NAME)/*" -delete 2>/dev/null || true
	@echo "${GREEN}✓ Caches cleared${RESET}"

.PHONY: clean
clean: clean-caches ## Remove build artifacts and caches
	@echo "${BLUE}Cleaning build artifacts...${RESET}"
	@rm -rf build/ dist/ *.egg-info src/*.egg-info
	@echo "${GREEN}✓ Clean complete${RESET}"

.PHONY: clean-all
clean-all: clean ## Remove build artifacts and virtual environment
	@echo "${BLUE}Removing virtual environment...${RESET}"
	@rm -rf $(VENV_NAME)
	@echo "${GREEN}✓ Clean all complete${RESET}"
