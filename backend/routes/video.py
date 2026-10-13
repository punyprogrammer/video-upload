from fastapi import APIRouter, Depends
from sqlalchemy import or_
from sqlalchemy.orm import Session

from db.db import get_db
from db.middleware.auth_middleware import get_current_user
from db.models.video import ProcessingStatus, Video, VisibilityStatus

router = APIRouter()


# get all videos
@router.get("/all")
def get_all_videos(db: Session = Depends(get_db), user=Depends(get_current_user)):
    all_videos = (
        db.query(Video)
        .filter(
            Video.is_processing == ProcessingStatus.COMPLETED,
            Video.visibility == VisibilityStatus.PUBLIC,
        )
        .all()
    )
    return all_videos


# get video info
@router.get("/")
def get_video_info(
    video_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)
):
    video = (
        db.query(Video)
        .filter(
            Video.id == video_id,
            Video.is_processing == ProcessingStatus.COMPLETED,
            or_(
                Video.visibility == VisibilityStatus.PUBLIC,
                Video.visibility == VisibilityStatus.UNLISTED,
            ),
        )
        .all()
    )
    return video
