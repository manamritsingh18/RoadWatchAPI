import logging

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    HTTPException,
    status,
    Depends,
)

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
# POST /videos/upload
# Upload a video — saved locally, status set to 'unprocessed'
# ==============================================================
@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """
    Upload a video file.

    - Saves the file to local storage (cloud upload is deferred).
    - Creates a record in the 'videos' table with status = 'unprocessed'.
    - Returns the video record ID for use by the processing service.
    """
    user_id = (
        current_user.get("id")
        if isinstance(current_user, dict)
        else getattr(current_user, "id", None)
    )

    # Basic content-type validation
    if file.content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "success": False,
                "error": "Invalid file type",
                "detail": (
                    f"Expected a video file, got: {file.content_type}"
                ),
            },
        )

    try:
        logger.info(
            f"Upload request from user {user_id} — file: {file.filename}"
        )

        # Step 1: Save to local filesystem
        saved = StorageService.save_locally(file)

        # Step 2: Persist record to DB
        record = VideoService.create_video_record(
            filename=saved["filename"],
            original_name=file.filename,
            local_path=saved["local_path"],
            user_id=user_id,
        )

        logger.info(
            f"Video record created: {record['id']} — status: unprocessed"
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
            },
        }

    except HTTPException:
        raise

    except Exception as e:
        logger.exception(f"Video upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Video upload failed",
                "detail": str(e),
            },
        )


# ==============================================================
# GET /videos/unprocessed
# Fetch all videos with status = 'unprocessed'
# ==============================================================
@router.get("/unprocessed")
async def get_unprocessed_videos(
    current_user=Depends(get_current_user),
):
    """
    Return all video records with status = 'unprocessed'.

    Intended to be called by the AI processing service to
    retrieve its work queue.
    """
    try:
        videos = VideoService.get_unprocessed_videos()

        return {
            "success": True,
            "count": len(videos),
            "data": videos,
        }

    except Exception as e:
        logger.exception(f"Failed to fetch unprocessed videos: {str(e)}")
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
# Update status of a video (processing | processed | failed)
# ==============================================================
@router.patch("/{video_id}/status")
async def update_video_status(
    video_id: str,
    body: dict,
    current_user=Depends(get_current_user),
):
    """
    Update the processing status of a video.

    Request body:
        {
            "status": "processing" | "processed" | "failed",
            "error_message": "optional — only for failed"
        }
    """
    new_status = body.get("status")
    error_message = body.get("error_message")

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
            error_message=error_message,
        )

        return {
            "success": True,
            "message": f"Video status updated to '{new_status}'",
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
        logger.exception(f"Failed to update video status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "success": False,
                "error": "Failed to update video status",
                "detail": str(e),
            },
        )