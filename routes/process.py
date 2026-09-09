from fastapi import APIRouter, File, HTTPException, UploadFile

from utils.workflow import workflow

router = APIRouter()


@router.post("/process")
async def process(file: UploadFile = File(...)) -> dict:
    """
    Accepts a PDF upload, runs it through the workflow and reports where the
    original and the parsed markdown ended up.
    """
    if not (file.filename or "").lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="only .pdf files are accepted")

    pdf = await file.read()
    if not pdf:
        raise HTTPException(status_code=400, detail="uploaded file is empty")

    try:
        result = await workflow(pdf, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"processing failed: {exc}") from exc

    return {"status": "ok", **result}
