import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.database.supabase import supabase
from app.schemas.evidence_frame import EvidenceFrameRecord

logger = logging.getLogger(__name__)


class EvidenceService:

    @staticmethod
    def save_evidence(
        evidence: EvidenceFrameRecord
    ) -> Dict[str, Any]:
        """
        Save one evidence frame reference to PostgreSQL.
        """

        try:
            evidence_data = {
                "report_id": evidence.report_id,
                "storage_url": evidence.storage_url,
                "frame_timestamp": evidence.frame_timestamp,
                "created_at": (
                    evidence.created_at.isoformat()
                    if evidence.created_at
                    else datetime.now(timezone.utc).isoformat()
                )
            }

            response = (
                supabase
                .table("evidence_frames")
                .insert(evidence_data)
                .execute()
            )

            if not response.data:
                raise RuntimeError(
                    "Evidence insert succeeded but returned no data"
                )

            saved_evidence = response.data[0]

            logger.info(
                "Evidence frame saved successfully: %s",
                saved_evidence.get("id")
            )

            return {
                "evidence_id": saved_evidence["id"],
                "report_id": saved_evidence["report_id"],
                "storage_url": saved_evidence["storage_url"],
                "frame_timestamp": saved_evidence["frame_timestamp"]
            }

        except Exception as e:
            logger.exception(
                "Failed to save evidence frame: %s",
                str(e)
            )
            raise RuntimeError(
                f"Failed to save evidence frame: {str(e)}"
            )