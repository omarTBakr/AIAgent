from workflows.workflow_legal_review import LegalReviewWorkflow
from workflows.workflow_process_pdf import ProcessPdfWorkflow

PDF_WORKFLOWS = [ProcessPdfWorkflow]
LEGAL_WORKFLOWS = [LegalReviewWorkflow]

ALL_WORKFLOWS = PDF_WORKFLOWS + LEGAL_WORKFLOWS

__all__ = ["ALL_WORKFLOWS", "LEGAL_WORKFLOWS", "LegalReviewWorkflow", "PDF_WORKFLOWS", "ProcessPdfWorkflow"]
