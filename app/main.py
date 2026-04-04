import os
import uuid

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from .models import (
    CreateJobRequest,
    CreateJobResponse,
    JobStatusResponse,
)
from .storage import download_file, make_output_paths, OUTPUT_DIR
from .overlay import (
    apply_annotations_to_pdf,
    render_pdf_page_to_png,
)

app = FastAPI(
    title="HPP Deterministic Drawing Overlay API",
    version="2.0.0",
    description="Deterministic overlay service for engineering drawings. No geometry regeneration.",
    servers=[
        {"url": "https://overlay-api-127g.onrender.com"}
    ],


app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

JOBS: dict[str, dict] = {}


def public_base_url() -> str:
    return os.getenv("PUBLIC_BASE_URL", "").rstrip("/")


@app.get("/")
def root():
    return {
        "status": "API running",
        "service": "HPP Deterministic Drawing Overlay API",
        "version": "2.0.0"
    }


@app.get("/build-check")
def build_check():
    return {"build_check": "render-uses-latest-code"}


async def process_overlay_job(job_id: str, request: CreateJobRequest):
    try:
        JOBS[job_id] = {"status": "processing"}

        source = request.source
        suffix = f".{source.fileType.lower()}"
        input_path = await download_file(str(source.fileUrl), suffix=suffix)

        if source.fileType.lower() != "pdf":
            raise ValueError("Only PDF source files are currently supported for deterministic drawing overlay")

        output_pdf, output_png = make_output_paths(job_id)

        apply_annotations_to_pdf(
            input_pdf=input_path,
            output_pdf=output_pdf,
            annotations=request.annotations,
            page_number_1_based=source.pageNumber,
        )

        render_pdf_page_to_png(
            input_pdf=output_pdf,
            output_png=output_png,
            page_number_1_based=source.pageNumber,
            dpi=200,
        )

        base = public_base_url()
        if not base:
            raise ValueError("PUBLIC_BASE_URL environment variable is not configured")

        JOBS[job_id] = {
            "status": "completed",
            "annotatedPdfUrl": f"{base}/outputs/{output_pdf.name}",
            "annotatedPngUrl": f"{base}/outputs/{output_png.name}",
            "message": "Overlay complete",
        }

    except Exception as e:
        JOBS[job_id] = {
            "status": "failed",
            "message": str(e),
        }


@app.post("/overlay-jobs", response_model=CreateJobResponse, status_code=202)
async def create_overlay_job(request: CreateJobRequest, background_tasks: BackgroundTasks):
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status": "queued"}
    background_tasks.add_task(process_overlay_job, job_id, request)
    return CreateJobResponse(jobId=job_id, status="queued")


@app.get("/overlay-jobs/{job_id}", response_model=JobStatusResponse)
async def get_overlay_job_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        jobId=job_id,
        status=job["status"],
        annotatedPdfUrl=job.get("annotatedPdfUrl"),
        annotatedPngUrl=job.get("annotatedPngUrl"),
        message=job.get("message"),
    )
