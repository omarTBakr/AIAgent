# AIAgent

A small FastAPI service that turns PDFs into Markdown and keeps both in
S3-compatible object storage.

Upload a PDF to one endpoint and the service stores the original, parses it with
[pymupdf4llm](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/), stores the
resulting Markdown, and pulls that Markdown back onto local disk for inspection.

## How it works

`POST /process` hands the uploaded bytes to `workflow()`, which runs five steps:

1. Write the PDF into `TEMP_PDF_FOLDER`
2. Upload the PDF to the `S3_PDF_BUCKET` bucket
3. Parse it into Markdown with pymupdf4llm
4. Upload the Markdown to the `S3_PARSED_MDS` bucket
5. Download that Markdown back into `TEMP_MD_FOLDER`

Each run gets a short random id, so `report.pdf` uploaded twice becomes
`report-a1b2c3d4.pdf` and `report-9f8e7d6c.pdf` rather than overwriting itself.
Both the PDF and its Markdown share the same run id.

All blocking work (boto3 calls, PDF parsing) runs through `asyncio.to_thread`
so it never stalls the event loop.

## Layout

```
main.py                      FastAPI app, /health, uvicorn entrypoint
routes/process.py            POST /process  (multipart upload)
utils/workflow.py            workflow() - the five steps above
utils/utility.py             get_s3_client, upload_s3_file, download_s3_file,
                             build_run_artifacts
utils/config.py              pydantic-settings Settings, loaded from .env
parsers/pymupdf_parser.py    parse_pdf, parse_pdf_to_file
tests/                       pytest suite (offline, no credentials needed)
assets/                      local scratch space (gitignored)
setup/                       Temporal server samples (see below)
```

## Requirements

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- An S3-compatible bucket pair (this project is developed against
  [IDrive e2](https://www.idrive.com/e2/), but plain AWS S3 works too)

## Setup

```bash
git clone https://github.com/omarTBakr/AIAgent.git
cd AIAgent
uv sync
```

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env
```

`.env` is gitignored — keep your real keys out of version control.

### Environment variables

| Variable | Description |
| --- | --- |
| `AWS_ACCESS_KEY_ID` | Access key for the object store |
| `AWS_SECRET_ACCESS_KEY` | Secret key for the object store |
| `AWS_REGION` | Region code, e.g. `us-west-4` |
| `AWS_ENDPOINT_URL` | S3 endpoint, e.g. `https://s3.us-west-4.idrivee2.com` |
| `S3_PDF_BUCKET` | Bucket the uploaded PDFs land in |
| `S3_PARSED_MDS` | Bucket the parsed Markdown lands in |
| `TEMP_PD_DIR` | Local scratch root, relative to the project root |
| `TEMP_PDF_FOLDER` | Sub-folder of `TEMP_PD_DIR` holding PDFs |
| `TEMP_MD_FOLDER` | Sub-folder of `TEMP_PD_DIR` holding Markdown |
| `API_HOST` | Host uvicorn binds to (default `0.0.0.0`) |
| `API_PORT` | Port uvicorn listens on (default `8000`) |

Both buckets must already exist; the service does not create them.

## Running

```bash
uv run main.py
```

The API comes up on `http://127.0.0.1:8000`, with interactive docs at
`http://127.0.0.1:8000/docs`.

## API

### `GET /health`

```json
{ "status": "ok" }
```

### `POST /process`

Accepts `multipart/form-data` with a single field named `file` containing a
`.pdf`.

```bash
curl -F "file=@report.pdf" http://127.0.0.1:8000/process
```

```json
{
  "status": "ok",
  "pdf_key": "report-a1b2c3d4.pdf",
  "md_key": "report-a1b2c3d4.md",
  "local_pdf": "/path/to/AIAgent/assets/TEMP_PDF/report-a1b2c3d4.pdf",
  "local_md": "/path/to/AIAgent/assets/TEMP_MD/report-a1b2c3d4.md"
}
```

Errors:

| Status | Cause |
| --- | --- |
| `400` | The upload is not a `.pdf`, or the file is empty |
| `422` | No form field named `file` was sent |
| `500` | A storage or parsing step failed |

The response takes a few seconds — two uploads, a parse and a download happen
before it returns.

## Tests

```bash
uv run pytest
```

The suite runs entirely offline — S3 is replaced with an in-memory fake and the
scratch directories are redirected into a temp dir, so no credentials, no `.env`
and no buckets are needed.

```
tests/conftest.py        fixtures: fake settings, FakeS3Client, a sample PDF
tests/test_config.py     env loading, whitespace stripping, scratch paths
tests/test_utility.py    run-id generation, S3 upload/download helpers
tests/test_parser.py     pymupdf4llm parsing from bytes and from a path
tests/test_workflow.py   the five-step pipeline end to end
tests/test_routes.py     /health and /process, including the 400/422/500 paths
```

## Code quality

Formatting and linting are enforced by [black](https://black.readthedocs.io/)
and [ruff](https://docs.astral.sh/ruff/), both configured to a line length of
**130** in `pyproject.toml`.

Install the git hook once, and black, ruff and pytest then run automatically
before every commit:

```bash
uv run pre-commit install
```

To run the checks by hand:

```bash
uv run black .
uv run ruff check --fix .
uv run pytest
```

The same three checks run in GitHub Actions on every push and pull request
(`.github/workflows/lint.yml`).

## Temporal (not wired up yet)

`temporalio` is declared as a dependency and `setup/` is where the Temporal
server samples live, but the pipeline currently runs as a plain async function.
The five steps in `workflow()` are already isolated enough to become Temporal
activities when that work starts.

The server samples are a separate upstream repository and are not tracked here.
To fetch them:

```bash
git clone https://github.com/temporalio/samples-server.git setup/samples-server
```

## License

Not yet specified.
