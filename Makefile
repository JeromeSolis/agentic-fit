# Mode is named in every target so the choice is never implicit.
# --free      = each model picks its own library (free-choice signal)
# --assigned  = sweep each candidate library per model (constrained head-to-head)
CONSTRAINED ?= results/crosslab_reps3_2026-05-25.jsonl

.PHONY: help info tasks smoke models \
        dry-run-free probe-free run-free \
        dry-run-assigned probe-assigned run-assigned \
        summary

help:
	@echo "agentic-fit make targets"
	@echo "  make info                            orientation: what this benchmark measures"
	@echo "  make tasks                           list categories with summaries and candidates"
	@echo "  make smoke                           preflight (key, model ids, Docker, registry)"
	@echo "  make models                          list the pinned cross-lab registry"
	@echo
	@echo "Free-choice (each model picks its own library):"
	@echo "  make dry-run-free                    cost estimate, no spend"
	@echo "  make probe-free                      cheap reps=1 validation (Docker)"
	@echo "  make run-free                        full free run; confirms cost, auto-summarizes"
	@echo
	@echo "Assigned / constrained (sweep each candidate library):"
	@echo "  make dry-run-assigned                cost estimate (~3x free), no spend"
	@echo "  make probe-assigned                  cheap reps=1 validation"
	@echo "  make run-assigned                    full assigned run; confirms cost"
	@echo
	@echo "Analyze a results file:"
	@echo "  make summary FILE=<path>             render summary + default tax"

info:
	uv run agentic-fit info

tasks:
	uv run agentic-fit tasks

smoke:
	uv run agentic-fit smoke

models:
	uv run agentic-fit models

dry-run-free:
	uv run agentic-fit run --free --dry-run

probe-free:
	uv run agentic-fit run --free --probe --sandbox docker --yes

run-free:
	uv run agentic-fit run --free --sandbox docker

dry-run-assigned:
	uv run agentic-fit run --assigned --dry-run

probe-assigned:
	uv run agentic-fit run --assigned --probe --sandbox docker --yes

run-assigned:
	uv run agentic-fit run --assigned --sandbox docker

summary:
	uv run agentic-fit summarize $(FILE) --constrained $(CONSTRAINED)
