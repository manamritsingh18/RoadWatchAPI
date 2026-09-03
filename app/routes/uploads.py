import logging

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    status,
    Depends,
)
from pydantic import BaseModel

from app.services.storage_service import StorageService
from app.services.video_service import VideoService
from app.utils.auth import get_current_user


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/videos",
    tags=["Videos"],
)


ALLOWED_VIDEO_TYPES = {
    "video/mp4",
    "video/mpeg",
    "video/quicktime",
    "video/x-msvideo",
    "video/webm",
}


# ==============================================================
# Request models
# ==============================================================

class VideoInitRequest(BaseModel):
    filename: str
    content_type: str
    vehicle_type: str | None = None


class VideoCompleteRequest(BaseModel):
    video_id: str
    storage_path: str
    blob_url: str


class VideoRegisterRequest(BaseModel):
    filename: str
    original_name: str
    blob_url: str
    vehicle_type: str | None = None


# ==============================================================
# POST /videos/upload/init
# Generate signed upload URL + pre-create DB record
# ==============================================================

@router.post("/upload/init", status_code=status.HTTP_201_CREATED)
async def init_video_upload(
    body: VideoInitRequest,
    current_user=Depends(get_current_user),
):
    """
    Step 1 of large-file upload flow.

    Generates a Supabase signed upload URL and pre-creates a videos
    row with status = 'unprocessed'.

    The AI worker will later pick up this video using direct
    PostgreSQL polling.
    """

    user_id = (
        current_user.get("id")
        if isinstance(current_user, dict)
        else getattr(current_user, "id", None)
    )

    try:
        signed = StorageService.create_signed_upload_url(body.filename)

        record = VideoService.create_pending_video_record(
            filename=body.filename,
            original_name=body.filename,
            storage_path=signed["storage_path"],
            user_id=user_id,
            vehicle_type=body.vehicle_type,
        )

        return {
            "success": True,
            "data": {
                "video_id": record["id"],
                "storage_path": signed["storage_path"],
                "upload_url": signed["upload_url"],
                "vehicle_type": record.get("vehicle_type"),
                "status": record["status"],
            },
        }

    except Exception as e:
        logger.exception(
            f"Failed to init video upload: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Failed to init video upload",
                "detail": str(e),
            },
        )


# ==============================================================
# POST /videos/upload/complete
# Finalize DB record after client confirms storage upload
# ==============================================================

@router.post("/upload/complete", status_code=status.HTTP_200_OK)
async def complete_video_upload(
    body: VideoCompleteRequest,
    current_user=Depends(get_current_user),
):
    """
    Finalize the video record after the direct storage upload.

    The video remains 'unprocessed' so the AI worker can claim it.
    """

    try:
        record = VideoService.complete_video_upload(
            video_id=body.video_id,
            blob_url=body.blob_url,
            storage_path=body.storage_path,
        )

        return {
            "success": True,
            "message": "Video upload completed",
            "data": record,
        }

    except Exception as e:
        logger.exception(
            f"Failed to complete video upload: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Failed to complete video upload",
                "detail": str(e),
            },
        )


# ==============================================================
# POST /videos/upload
# Legacy direct upload endpoint
# ==============================================================

@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """
    Legacy direct upload endpoint.

    The large-file /upload/init + /upload/complete flow remains
    preferred for production use because it bypasses Vercel's
    request payload limit.
    """

    user_id = (
        current_user.get("id")
        if isinstance(current_user, dict)
        else getattr(current_user, "id", None)
    )

    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": "Invalid file type",
                "detail": (
                    f"Expected a video file, got: "
                    f"{file.content_type}"
                ),
            },
        )

    try:
        logger.info(
            f"Upload request from user {user_id} "
            f"— file: {file.filename}"
        )

        # Step 1: Save locally
        saved = StorageService.save_locally(file)

        # Step 2: Persist DB record
        #
        # This legacy endpoint does not currently receive
        # vehicle_type, so it remains None.
        record = VideoService.create_video_record(
            filename=saved["filename"],
            original_name=file.filename,
            blob_url="",
            user_id=user_id,
            vehicle_type=None,
        )

        # Preserve the local path for this legacy upload.
        # The main large-file flow uses local_path during init.
        try:
            from app.database.supabase import supabase

            supabase.table("videos").update(
                {
                    "local_path": saved["local_path"],
                    "video_url": saved.get("local_path"),
                }
            ).eq("id", record["id"]).execute()

        except Exception as e:
            logger.warning(
                f"Could not update local path for video "
                f"{record['id']}: {str(e)}"
            )

        logger.info(
            f"Video record created: {record['id']} "
            f"— status: unprocessed"
        )

        return {
            "success": True,
            "message": "Video uploaded successfully",
            "data": {
                "video_id": record["id"],
                "filename": record["filename"],
                "original_name": record["original_name"],
                "status": record["status"],
                "uploaded_at": record["uploaded_at"],
                "vehicle_type": record.get("vehicle_type"),
                "video_url": record.get("video_url"),
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            f"Video upload failed: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Video upload failed",
                "detail": str(e),
            },
        )


# ==============================================================
# POST /videos/register
# Register a video already uploaded to Supabase Storage
# ==============================================================

@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register_video(
    body: VideoRegisterRequest,
    current_user=Depends(get_current_user),
):
    """
    Register metadata for a video already uploaded directly
    to Supabase Storage.
    """

    user_id = (
        current_user.get("id")
        if isinstance(current_user, dict)
        else getattr(current_user, "id", None)
    )

    try:
        logger.info(
            f"Register request from user {user_id} "
            f"— blob_url: {body.blob_url}"
        )

        record = VideoService.create_video_record(
            filename=body.filename,
            original_name=body.original_name,
            blob_url=body.blob_url,
            user_id=user_id,
            vehicle_type=body.vehicle_type,
        )

        logger.info(
            f"Video record created: {record['id']} "
            f"— status: unprocessed"
        )

        return {
            "success": True,
            "message": "Video registered successfully",
            "data": {
                "video_id": record["id"],
                "filename": record["filename"],
                "original_name": record["original_name"],
                "status": record["status"],
                "uploaded_at": record["uploaded_at"],
                "vehicle_type": record.get("vehicle_type"),
                "video_url": record.get("video_url"),
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(
            f"Video registration failed: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Video registration failed",
                "detail": str(e),
            },
        )


# ==============================================================
# GET /videos/unprocessed
# Fetch videos waiting for AI processing
# ==============================================================

@router.get("/unprocessed")
async def get_unprocessed_videos(
    current_user=Depends(get_current_user),
):
    """
    Return video records with status = 'unprocessed'.

    IMPORTANT:
    The AI worker no longer relies on this endpoint as its queue.
    It directly polls PostgreSQL and atomically claims videos.

    This endpoint remains useful for frontend/debugging/admin use.
    """

    try:
        videos = VideoService.get_unprocessed_videos()

        return {
            "success": True,
            "count": len(videos),
            "data": videos,
        }

    except Exception as e:
        logger.exception(
            f"Failed to fetch unprocessed videos: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Failed to fetch unprocessed videos",
                "detail": str(e),
            },
        )


# ==============================================================
# PATCH /videos/{video_id}/status
# Update video processing status
# ==============================================================

@router.patch("/{video_id}/status")
async def update_video_status(
    video_id: str,
    body: dict,
    current_user=Depends(get_current_user),
):
    """
    Update processing status.

    Supported statuses:
        processing
        completed
        failed

    Request body:
        {
            "status": "processing",
            "error_reason": "optional"
        }
    """

    new_status = body.get("status")
    error_reason = body.get("error_reason")

    # Backward compatibility with old clients
    if not error_reason:
        error_reason = body.get("error_message")

    if not new_status:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": "'status' is required in request body",
            },
        )

    try:
        updated = VideoService.update_video_status(
            video_id=video_id,
            status=new_status,
            error_reason=error_reason,
        )

        return {
            "success": True,
            "message": (
                f"Video status updated to '{new_status}'"
            ),
            "data": updated,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": str(e),
            },
        )

    except Exception as e:
        logger.exception(
            f"Failed to update video status: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Failed to update video status",
                "detail": str(e),
            },
        )


# ==============================================================
# PATCH /videos/{video_id}/score
# Update computed score of a video
# ==============================================================

@router.patch("/{video_id}/score")
async def update_video_score(
    video_id: str,
    body: dict,
    current_user=Depends(get_current_user),
):
    """
    Update the score of a video.

    Request body:
        {
            "score": 8.5
        }
    """

    score = body.get("score")

    if score is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": "'score' is required in request body",
            },
        )

    try:
        updated = VideoService.update_video_score(
            video_id=video_id,
            score=score,
        )

        return {
            "success": True,
            "message": f"Video score updated to {score}",
            "data": updated,
        }

    except Exception as e:
        logger.exception(
            f"Failed to update video score: {str(e)}"
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Failed to update video score",
                "detail": str(e),
            },
        )
