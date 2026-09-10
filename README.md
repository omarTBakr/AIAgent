# AIAgent

A small FastAPI service that turns PDFs into Markdown and keeps both in
S3-compatible object storage.

Upload a PDF to one endpoint and the service stores the original, parses it with
[pymupdf4llm](https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/), stores the
resulting Markdown, and pulls that Markdown back onto local disk for inspection.

## How it works

`POST /process` stores the upload, then hands the work to Temporal:

1. The route writes the PDF into `TEMP_PDF_FOLDER` and uploads it to
   `S3_PDF_BUCKET`, then starts `ProcessPdfWorkflow` with just the two keys
2. `download_pdf` pulls the PDF onto whichever worker picked up the task
3. `parse_pdf` converts it to Markdown with pymupdf4llm
4. `upload_md` writes the Markdown to `S3_PARSED_MDS`
5. `download_md` pulls it back into `TEMP_MD_FOLDER`

The document itself never travels through the workflow history: the route
uploads it first and the workflow passes only keys, which is also why the
worker does not need to share a filesystem with the API.

Each run gets a short random id, so `report.pdf` uploaded twice becomes
`report-a1b2c3d4.pdf` and `report-9f8e7d6c.pdf` rather than overwriting itself.
Both the PDF and its Markdown share the same run id, and the workflow id is
derived from the PDF key so a retried upload deduplicates.

Retry behaviour comes from named policies in `enums/RetryPolicy.py` rather than
being spelled out at each call site: `StorageRetryPolicy()` retries three times
with a one-second initial backoff, `ParsingRetryPolicy()` twice with a
five-second one, and `StrictRetryPolicy()` does not retry at all. Storage steps
time out after a minute, parsing after ten.

## Layout

```
main.py                      FastAPI app, /health, uvicorn entrypoint
worker.py                    worker entrypoint (uv run worker.py)
workers/process_pdf_worker.py  the PDF pipeline worker
utils/create_worker.py       create_worker() factory
routes/process.py            POST /process  (multipart upload)
workflows/                   workflow_process_pdf.py - ProcessPdfWorkflow
activities/                  one Temporal activity per file
schemas/                     one dataclass schema file per activity/workflow
enums/RetryPolicy/           one retry policy per file
utils/utility.py             get_s3_client, upload_s3_file, download_s3_file,
                             build_run_artifacts
utils/temporal_client.py     get_temporal_client
utils/config.py              pydantic-settings Settings, loaded from .env
utils/logger.py              setup_logging, get_logger
parsers/pymupdf_parser.py    parse_pdf, parse_pdf_to_file
exceptions/                  the project's exception hierarchy
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
| `TEMPORAL_HOST` | `host:port` of the Temporal frontend (default `localhost:7233`) |
| `TEMPORAL_NAMESPACE` | Temporal namespace (default `default`) |
| `TEMPORAL_TASK_QUEUE` | Task queue for the workflow and activities (default `process_pdf_queue`) |
| `LOG_LEVEL` | Root log level (default `INFO`) |
| `RUN_WORKER_IN_API` | Run the worker inside the API process (default `false`) |

Both buckets must already exist; the service does not create them.

## Running

With `RUN_WORKER_IN_API=true` the API hosts the worker, so local development
needs two processes:

```bash
temporal server start-dev     # 1. Temporal
uv run main.py                # 2. API, with the worker inside it
```

In production leave `RUN_WORKER_IN_API` off and run the worker separately, so a
slow parse cannot starve request handling and in-flight work survives an API
restart:

```bash
temporal server start-dev     # 1. Temporal
uv run worker.py              # 2. Worker
uv run main.py                # 3. API
```

Startup fails loudly if `RUN_WORKER_IN_API` is set and Temporal cannot be
reached: an API that was asked to host a worker but has none would accept
uploads that nothing ever picks up.

The API comes up on `http://127.0.0.1:8000`, with interactive docs at
`http://127.0.0.1:8000/docs`, and the Temporal web UI on
`http://127.0.0.1:8233`.

`POST /process` returns 503 if Temporal is unreachable. If the server is up but
no worker is polling `TEMPORAL_TASK_QUEUE`, the upload is still accepted with a
202 and the task simply stays `processing` until a worker appears.

## API

### `GET /health`

```json
{ "status": "ok" }
```

### `POST /process`

Accepts `multipart/form-data` with a single field named `file` containing a
`.pdf`. Stores the PDF, starts the workflow and returns **202 straight away** —
it does not wait for the pipeline to finish.

```bash
curl -F "file=@report.pdf" http://127.0.0.1:8000/process
```

```json
{
  "status": "processing",
  "task_id": "a1b2c3d4",
  "workflow_id": "process-pdf-a1b2c3d4",
  "pdf_bucket": "temporalpdfs",
  "pdf_key": "report-a1b2c3d4.pdf",
  "md_key": "report-a1b2c3d4.md"
}
```

Add `?wait=true` to hold the request open until the pipeline finishes and get
the full result in one call (HTTP 200). Convenient for small documents; a large
PDF will outlast most proxy timeouts.

### `GET /process/{task_id}`

Reports where a task got to. Temporal holds the state, so nothing is stored
here.

```json
{ "status": "processing", "task_id": "a1b2c3d4", "workflow_id": "process-pdf-a1b2c3d4" }
```

Once finished:

```json
{
  "status": "completed",
  "task_id": "a1b2c3d4",
  "workflow_id": "process-pdf-a1b2c3d4",
  "pdf_bucket": "temporalpdfs",
  "pdf_key": "report-a1b2c3d4.pdf",
  "md_bucket": "parsedmds",
  "md_key": "report-a1b2c3d4.md",
  "local_pdf": "/path/to/AIAgent/assets/TEMP_PDF/report-a1b2c3d4.pdf",
  "local_md": "/path/to/AIAgent/assets/TEMP_MD/report-a1b2c3d4.md",
  "markdown_characters": 1843
}
```

A task that ended badly reports the terminal state's name: `failed`,
`terminated`, `timed_out` or `canceled`. An unknown id is a 404.

Because the work is durable, a dropped connection costs you the response but
never the run: the `task_id` fetches it afterwards.

### Errors

| Status | Cause |
| --- | --- |
| `400` | The upload is not a `.pdf`, or the file is empty (`ValidationError`) |
| `404` | No task with that id |
| `422` | No form field named `file` was sent, or the PDF could not be parsed (`ParsingError`) |
| `502` | The object store could not be reached or refused the request (`StorageError`) |
| `503` | Temporal is unreachable (`TemporalConnectionError`) |
| `500` | The workflow failed, or anything else |

The workflow returns a `ProcessPdfResult` (`schemas/process_pdf_result.py`),
which both endpoints pass straight through. `workflow_id` is what you look up
in the Temporal UI.

### Task ids

Every upload gets a `task_id`, generated once in `build_run_artifacts`. It is
the thread that ties one run together: it names the workflow
(`process-pdf-<task_id>`), appears in both object keys, is carried in every
activity's input, and prefixes every log line the run produces.

That is what makes concurrent runs readable. Two uploads at the same time
interleave in the log, but each stays separable:

```
[task f54f498f] parsing pdf ...
[task e296b2ea] parsing pdf ...
[task f54f498f] uploaded markdown parsedmds/...
[task e296b2ea] uploaded markdown parsedmds/...
```

Grepping one task id gives you that run and nothing else.

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
tests/test_workflow_process_pdf.py
                         ProcessPdfWorkflow against a real in-process Temporal
                         server, with the activities hitting the S3 fake
tests/test_temporal_client.py
                         connection caching, timeouts and failure translation
tests/test_enums.py      the retry policies and their relative tuning
tests/test_create_worker.py
                         worker wiring: task queue, client, registrations
tests/test_lifespan.py   the in-API worker starting, stopping and failing
tests/test_routes.py     /health and /process, including the 400/422/500 paths
tests/test_activities.py the five activities via Temporal's ActivityEnvironment
tests/test_schemas.py    schemas survive Temporal's data converter round trip
tests/test_logging.py    every activity logs through activity.logger
tests/test_exceptions.py the hierarchy, and that the code raises the right types
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

## Exceptions

Everything the project raises on purpose descends from `AIAgentError`, so
`except AIAgentError` catches deliberate failures while letting real bugs
escape uncaught.

```
AIAgentError
+-- ConfigurationError      MissingSettingError, InvalidSettingError
+-- ValidationError         UnsupportedFileTypeError, EmptyFileError
+-- StorageError            StorageConnectionError, UploadError, DownloadError,
|                           ObjectNotFoundError, LocalFileNotFoundError
+-- ParsingError            PdfNotFoundError, InvalidPdfError
+-- WorkflowError           ActivityFailedError
```

Each domain lives in its own module (`exceptions/storage.py` and so on) and is
re-exported from the package, so `from exceptions import UploadError` works.

Two of them deliberately inherit from a builtin as well —
`LocalFileNotFoundError` and `PdfNotFoundError` are both `FileNotFoundError` —
so code that only cares that a file is missing keeps working without knowing
about this hierarchy.

boto3 and pymupdf errors are translated at the boundary in `utils/utility.py`
and `parsers/pymupdf_parser.py`, always with `raise ... from exc` so the
original error stays attached as `__cause__`. `routes/process.py` maps the
domains onto HTTP status codes (see the table above).

## Temporal activities

The five pipeline steps exist as Temporal activities, one per file. Each is a
thin wrapper: it takes a dataclass from `schemas/`, performs one side effect,
and returns a dataclass. The real work stays in `utils/` and `parsers/` so it
stays testable without a Temporal server.

| Activity | Schema | Does |
| --- | --- | --- |
| `activities/upload_pdf.py` | `schemas/upload_pdf.py` | Local PDF into `S3_PDF_BUCKET` |
| `activities/download_pdf.py` | `schemas/download_pdf.py` | `S3_PDF_BUCKET` into `TEMP_PDF_FOLDER` |
| `activities/parse_pdf.py` | `schemas/parse_pdf.py` | PDF into Markdown |
| `activities/upload_md.py` | `schemas/upload_md.py` | Markdown into `S3_PARSED_MDS` |
| `activities/download_md.py` | `schemas/download_md.py` | `S3_PARSED_MDS` into `TEMP_MD_FOLDER` |

`activities.ALL_ACTIVITIES` is the list to hand a `Worker(activities=...)`.

The schema folder is called `schemas/` rather than `dataclasses/` on purpose: a
top-level package named `dataclasses` shadows the standard library module and
breaks pydantic, temporalio and fastapi on import.

### Logging

Every activity logs through `activity.logger`, so records carry Temporal
context (`activity_id`, `activity_type`, `attempt`, `workflow_id`) once a
worker is running:

```
INFO  temporalio.activity: uploading pdf /tmp/report.pdf -> temporalpdfs/report-a1b2c3d4.pdf
      ({'activity_id': '5', 'attempt': 1, 'workflow_id': '...', ...})
```

Each activity logs before the step, after it succeeds, and logs the exception
before re-raising on failure. Call `utils.logger.setup_logging()` from an
entrypoint to configure the root logger from `LOG_LEVEL`.

### The workflow

`workflows/workflow_process_pdf.py` defines `ProcessPdfWorkflow`, which chains
`download_pdf`, `parse_pdf`, `upload_md` and `download_md`. Activity modules are
imported under `workflow.unsafe.imports_passed_through()` so the workflow
sandbox does not re-execute them.

`upload_pdf` is registered on the worker but is not part of this workflow: the
API uploads the document itself, before the workflow starts. It is there for
flows that begin from a file already on a worker.

`workers/process_pdf_worker.py` is the worker for this pipeline. It registers
`ALL_WORKFLOWS` and `ALL_ACTIVITIES` and polls `TEMPORAL_TASK_QUEUE`, which
defaults to `process_pdf_queue`.

It is built by `utils/create_worker.py`, a small factory that connects a client
and applies the configured task queue when none is passed:

```python
worker = await create_worker(workflows=ALL_WORKFLOWS, activities=ALL_ACTIVITIES)
await worker.run()
```

`create_worker` returns the worker rather than running it, so a caller can pick
between `await worker.run()` and `async with worker:` (which is what the tests
use). Both the task queue and the client can be overridden, which is how the
tests point a worker at a throwaway queue.

`worker.py` at the project root is only an entrypoint; it exists so that
`uv run worker.py` puts the project directory on `sys.path`. Running the module
directly also works: `uv run python -m workers.process_pdf_worker`.

Retry policies live under `enums/RetryPolicy/`, one per file:

```
enums/RetryPolicy/StorageRetryPolicy.py   3 attempts, 1s backoff, 30s cap
enums/RetryPolicy/ParsingRetryPolicy.py   2 attempts, 5s backoff, 1m cap
enums/RetryPolicy/StrictRetryPolicy.py    1 attempt, no retry
enums/RetryPolicy/RetryProfile.py         the enum + get_retry_policy()
```

They are re-exported from both packages, so either import works:

```python
from enums import StorageRetryPolicy
from enums.RetryPolicy.StorageRetryPolicy import StorageRetryPolicy
```


```python
from enums.RetryPolicy import StorageRetryPolicy, ParsingRetryPolicy, StrictRetryPolicy

execute_activity(..., retry_policy=StorageRetryPolicy())
```

Each returns a fresh `temporalio.common.RetryPolicy`, so a caller that mutates
one cannot affect anybody else's. `RetryProfile` is the matching enum for
picking a policy by name (`get_retry_policy("storage")`), which is what keeps
the tuning selectable from configuration.

One limit worth knowing: `parse_pdf` returns the Markdown through the workflow,
so a very large document can bump into Temporal's payload size limit. If that
happens, have the activity write to the bucket and pass the key instead.

The server samples are a separate upstream repository and are not tracked here.
To fetch them:

```bash
git clone https://github.com/temporalio/samples-server.git setup/samples-server
```

## License

Not yet specified.
