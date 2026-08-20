from typing import List, Optional

from pydantic import BaseModel


class EvidenceCreateRequest(BaseModel):
    image_urls: List[str]
    video_id: Optional[str] = None  # UUID of the video this evidence belongs to


class EvidenceCreateResponse(BaseModel):
    success: bool
    vehicle_id: int           # BIGINT from vehicles table
    vehicle_number: str
    evidence_count: int
    saved_urls: List[str]
