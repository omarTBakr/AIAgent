from fastapi import APIRouter, File, HTTPException, UploadFile

from exceptions import AIAgentError, ParsingError, StorageError, ValidationError
from exceptions.validation import EmptyFileError, UnsupportedFileTypeError
from utils.logger import get_logger
from utils.workflow import workflow

router = APIRouter()

logger = get_logger(__name__)


@router.post("/process")
async def process(file: UploadFile = File(...)) -> dict:
    """
    Accepts a PDF upload, runs it through the workflow and reports where the
    original and the parsed markdown ended up.
    """
    try:
        if not (file.filename or "").lower().endswith(".pdf"):
            raise UnsupportedFileTypeError("only .pdf files are accepted")

        pdf = await file.read()
        if not pdf:
            raise EmptyFileError("uploaded file is empty")

        result = await workflow(pdf, file.filename)

    except ValidationError as exc:
        # the caller sent something unusable
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ParsingError as exc:
        # a real PDF was sent but could not be read: unprocessable, not a server fault
        logger.warning("could not parse %s: %s", file.filename, exc)
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except StorageError as exc:
        logger.error("storage failed for %s: %s", file.filename, exc)
        raise HTTPException(status_code=502, detail=f"storage error: {exc}") from exc
    except AIAgentError as exc:
        logger.exception("pipeline failed for %s", file.filename)
        raise HTTPException(status_code=500, detail=f"processing failed: {exc}") from exc
    except Exception as exc:
        # anything unplanned is a bug; log it with a traceback
        logger.exception("unexpected failure for %s", file.filename)
        raise HTTPException(status_code=500, detail=f"processing failed: {exc}") from exc

    return {"status": "ok", **result}
