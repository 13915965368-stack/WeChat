from __future__ import annotations

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import Response

from app.common import error_response
from app.schemas import AttachmentUploadResponse
from app.services.attachment_store import InMemoryAttachmentStore

router = APIRouter(tags=["attachments"])


def get_attachment_store(request: Request) -> InMemoryAttachmentStore:
    return request.app.state.attachment_store


@router.post("/attachments/images", response_model=AttachmentUploadResponse, status_code=201)
async def upload_image_attachment(
    file: UploadFile = File(...),
    store: InMemoryAttachmentStore = Depends(get_attachment_store),
):
    if not file.content_type or not file.content_type.startswith("image/"):
        return error_response(422, "validation_error", "file must be an image")

    content = await file.read()
    if not content:
        return error_response(422, "validation_error", "file cannot be empty")

    attachment = store.save_image(content=content, mime_type=file.content_type)
    return AttachmentUploadResponse(
        attachmentId=attachment.attachment_id,
        mimeType=attachment.mime_type,
        previewUrl=store.build_preview_url(attachment.attachment_id),
        expiresAt=store.serialize_expires_at(attachment),
    )


@router.get("/attachments/images/{attachment_id}/preview")
def get_uploaded_image_preview(
    attachment_id: str,
    store: InMemoryAttachmentStore = Depends(get_attachment_store),
):
    attachment = store.get_active_image(attachment_id.strip())
    if attachment is None:
        return error_response(404, "attachment_not_found", "Attachment not found")

    return Response(
        content=attachment.content,
        media_type=attachment.mime_type,
        headers={"Cache-Control": "private, max-age=60"},
    )
