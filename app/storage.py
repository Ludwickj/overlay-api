import uuid
from pathlib import Path
import httpx

BASE_DIR = Path(__file__).resolve().parent.parent
TEMP_DIR = BASE_DIR / "temp"
OUTPUT_DIR = BASE_DIR / "outputs"

TEMP_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


async def download_file(url: str, suffix: str) -> Path:
    file_id = uuid.uuid4().hex
    path = TEMP_DIR / f"{file_id}{suffix}"

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url)
        response.raise_for_status()
        path.write_bytes(response.content)

    return path


def make_output_paths(job_id: str) -> tuple[Path, Path]:
    pdf_path = OUTPUT_DIR / f"{job_id}.pdf"
    png_path = OUTPUT_DIR / f"{job_id}.png"
    return pdf_path, png_path
