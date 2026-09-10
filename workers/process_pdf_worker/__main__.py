"""Lets the package be run directly:

python -m workers.process_pdf_worker
"""

import asyncio

from workers.process_pdf_worker.process_pdf_worker import run_process_pdf_worker

if __name__ == "__main__":
    asyncio.run(run_process_pdf_worker())
