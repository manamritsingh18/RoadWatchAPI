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
    ) -> Dict[str, Any]:
        """
        Save evidence images against a vehicle identified by its number plate.

        - Looks up the vehicle by number_plate; creates it if it doesn't exist.
        - Inserts one row per image URL into the 'evidence' table.

        Args:
            vehicle_number: License plate string (e.g. 'MH12AB1234')
            image_urls:     List of image URL strings
            video_id:       Optional UUID of the related video record

        Returns:
            dict with vehicle_id, evidence_count, saved_urls
        """
        if not image_urls:
            raise ValueError("image_urls must not be empty")

        # Resolve vehicle — reuse existing get_or_create from ReportService
        # vehicle_id here is a BIGINT (int) since vehicles.id is BIGINT
        vehicle_id = ReportService.get_or_create_vehicle(vehicle_number)
        logger.info(
            f"Saving {len(image_urls)} evidence image(s) "
            f"for vehicle '{vehicle_number}' (id={vehicle_id})"
        )

        rows = []
        for url in image_urls:
            row: Dict[str, Any] = {
                "vehicle_id": vehicle_id,
                "image_url": url,
            }
            if video_id:
                row["video_id"] = video_id
            rows.append(row)

        try:
            response = (
                supabase
                .table("evidence")
                .insert(rows)
                .execute()
            )

            if not response.data:
                raise RuntimeError("Evidence insert returned no data")

            saved_urls = [row["image_url"] for row in response.data]
            logger.info(
                f"Saved {len(saved_urls)} evidence row(s) "
                f"for vehicle_id={vehicle_id}"
            )

            return {
                "vehicle_id": vehicle_id,
                "evidence_count": len(saved_urls),
                "saved_urls": saved_urls,
            }

        except Exception as e:
            logger.exception(f"Failed to save evidence: {str(e)}")
            raise RuntimeError(f"Failed to save evidence: {str(e)}")