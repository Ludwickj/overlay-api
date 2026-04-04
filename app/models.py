from typing import List, Literal, Optional, Union
from pydantic import BaseModel, Field, HttpUrl


class Point(BaseModel):
    x: float
    y: float


class SourceDocument(BaseModel):
    fileUrl: HttpUrl
    fileType: Literal["pdf"]
    pageNumber: int = Field(default=1, ge=1)


class TextAnnotation(BaseModel):
    kind: Literal["text"]
    pageNumber: int = Field(ge=1)
    x: float
    y: float
    text: str
    fontSize: float = 10
    fontColor: str = "#0000FF"


class LeaderLineAnnotation(BaseModel):
    kind: Literal["leader_line"]
    pageNumber: int = Field(ge=1)
    points: List[Point]
    strokeColor: str = "#0000FF"
    strokeWidth: float = 1.0


Annotation = Union[TextAnnotation, LeaderLineAnnotation]


class CreateJobRequest(BaseModel):
    source: SourceDocument
    annotations: List[Annotation]
    metadata: Optional[dict] = None


class CreateJobResponse(BaseModel):
    jobId: str
    status: str


class JobStatusResponse(BaseModel):
    jobId: str
    status: str
    annotatedPdfUrl: Optional[str] = None
    annotatedPngUrl: Optional[str] = None
    message: Optional[str] = None
