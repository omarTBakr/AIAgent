"""The legal review worker.

Self-contained: the worker module plus the Docker/ directory that runs it as a
standalone process.
"""

from workers.legal_advice_worker.legal_advice_worker import (
    create_legal_advice_worker,
    run_legal_advice_worker,
)

__all__ = ["create_legal_advice_worker", "run_legal_advice_worker"]
