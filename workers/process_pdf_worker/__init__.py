"""The PDF processing worker.

Self-contained: the worker module plus the Docker/ directory that runs it as a
standalone process. Importing the package keeps the same names as before, so
`from workers.process_pdf_worker import create_process_pdf_worker` is unchanged.
"""

from workers.process_pdf_worker.process_pdf_worker import (
    create_process_pdf_worker,
    run_process_pdf_worker,
)

__all__ = ["create_process_pdf_worker", "run_process_pdf_worker"]
