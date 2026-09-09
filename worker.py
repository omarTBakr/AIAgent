"""Entrypoint for the PDF processing worker: `uv run worker.py`.

Kept at the project root so the working directory lands on sys.path; the worker
itself lives in workers/process_pdf_worker.py.
"""

import asyncio

from workers.process_pdf_worker import run_process_pdf_worker


def main() -> None:
    asyncio.run(run_process_pdf_worker())


if __name__ == "__main__":
    main()
