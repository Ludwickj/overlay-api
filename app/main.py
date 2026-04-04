import json
import uuid
from pathlib import Path
from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles

from .models import (
    TextAnnotation,
    LeaderLineAnnotation,
    CreateJobResponse,
    JobStatusResponse,
)
from .storage import make_output_paths, OUTPUT_DIR, TEMP_DIR
from .overlay import apply_annotations_to_pdf, render_pdf_page_to_png

app = FastAPI(title="HPP Deterministic Drawing Overlay API", version="1.4.0")

@app.get("/")
def root():
    return {"status": "API running"}

app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

JOBS = {}


def parse_annotations(raw_text: str):
    raw = json.loads(raw_text)
    parsed = []

    for item in raw:
        kind = item.get("kind")
        if kind == "text":
            parsed.append(TextAnnotation(**item))
        elif kind == "leader_line":
            parsed.append(LeaderLineAnnotation(**item))
        else:
            raise ValueError(f"Unsupported annotation kind: {kind}")

    return parsed


async def process_uploaded_job(job_id: str, input_path: Path, page_number: int, annotations: list):
    try:
        JOBS[job_id] = {"status": "processing"}

        output_pdf, output_png = make_output_paths(job_id)

        apply_annotations_to_pdf(
            input_pdf=input_path,
            output_pdf=output_pdf,
            annotations=annotations,
            page_number_1_based=page_number,
        )

        render_pdf_page_to_png(
            input_pdf=output_pdf,
            output_png=output_png,
            page_number_1_based=page_number,
            dpi=200,
        )

        JOBS[job_id] = {
            "status": "completed",
            "annotatedPdfUrl": f"http://127.0.0.1:8000/outputs/{output_pdf.name}",
            "annotatedPngUrl": f"http://127.0.0.1:8000/outputs/{output_png.name}",
            "message": "Overlay complete",
        }

    except Exception as e:
        JOBS[job_id] = {
            "status": "failed",
            "message": str(e),
        }


@app.post("/upload-job", response_model=CreateJobResponse, status_code=202)
async def create_upload_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    pageNumber: int = Form(1),
    annotations: str = Form(...),
):
    job_id = uuid.uuid4().hex
    JOBS[job_id] = {"status": "queued"}

    input_path = TEMP_DIR / f"{job_id}.pdf"
    content = await file.read()
    input_path.write_bytes(content)

    parsed_annotations = parse_annotations(annotations)

    background_tasks.add_task(process_uploaded_job, job_id, input_path, pageNumber, parsed_annotations)
    return CreateJobResponse(jobId=job_id, status="queued")


@app.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str):
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
