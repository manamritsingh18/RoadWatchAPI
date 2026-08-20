import logging
from typing import Any, Dict, List, Optional

from app.database.supabase import supabase
from app.services.report_service import ReportService

logger = logging.getLogger(__name__)


class EvidenceService:

    @staticmethod
    def save_evidence_for_vehicle(
        vehicle_number: str,
        image_urls: List[str],
        video_id: Optional[str] = None,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """
        Save evidence image URLs for a vehicle, optionally tagged with location.

        Args:
            vehicle_number: License plate number
            image_urls:     List of evidence image URLs
            video_id:       Optional linked video ID
            latitude:       Optional GPS latitude for this evidence
            longitude:      Optional GPS longitude for this evidence

        Returns:
            List of inserted evidence row dicts
        """
        if not image_urls:
            raise ValueError("image_urls must not be empty")

        # get_or_create_vehicle returns a plain integer vehicle ID
        vehicle_id = ReportService.get_or_create_vehicle(vehicle_number)
        logger.info(
            f"Saving {len(image_urls)} evidence image(s) "
            f"for vehicle '{vehicle_number}' (id={vehicle_id})"
        )

        rows = [
            {
                "vehicle_id": vehicle_id,
                "video_id": video_id,
                "image_url": url,
                "latitude": latitude,
                "longitude": longitude,
            }
            for url in image_urls
        ]

        try:
            response = (
                supabase
                .table("evidence")
                .insert(rows)
                .execute()
            )

            if not response.data:
                raise RuntimeError("Evidence insert returned no data")

            logger.info(
                f"Saved {len(response.data)} evidence row(s) "
                f"for vehicle_id={vehicle_id}"
            )
            return response.data

        except Exception as e:
            logger.exception(f"Failed to save evidence: {str(e)}")
            raise RuntimeError(f"Failed to save evidence: {str(e)}")