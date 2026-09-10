"""Lets the package be run directly:

python -m workers.legal_advice_worker
"""

import asyncio

from workers.legal_advice_worker.legal_advice_worker import run_legal_advice_worker

if __name__ == "__main__":
    asyncio.run(run_legal_advice_worker())
