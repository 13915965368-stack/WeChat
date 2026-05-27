from datetime import datetime, timezone


def test_upload_image_attachment_returns_attachment_metadata_and_preview(client):
    response = client.post(
        "/api/v1/attachments/images",
        files={"file": ("wireframe.png", b"fake-image-bytes", "image/png")},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["attachmentId"].startswith("attachment-")
    assert body["mimeType"] == "image/png"
    assert body["previewUrl"] == f"/api/v1/attachments/images/{body['attachmentId']}/preview"
    assert datetime.fromisoformat(body["expiresAt"].replace("Z", "+00:00")) > datetime.now(timezone.utc)

    preview_response = client.get(body["previewUrl"])
    assert preview_response.status_code == 200
    assert preview_response.content == b"fake-image-bytes"
    assert preview_response.headers["content-type"] == "image/png"


def test_upload_image_attachment_rejects_non_image_file(client):
    response = client.post(
        "/api/v1/attachments/images",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {"code": "validation_error", "message": "file must be an image"}
    }


def test_uploaded_image_preview_expires_with_in_memory_lifecycle(client):
    client.app.state.attachment_store.ttl_seconds = 0

    upload_response = client.post(
        "/api/v1/attachments/images",
        files={"file": ("wireframe.png", b"fake-image-bytes", "image/png")},
    )
    assert upload_response.status_code == 201

    preview_response = client.get(upload_response.json()["previewUrl"])
    assert preview_response.status_code == 404
    assert preview_response.json() == {
        "error": {"code": "attachment_not_found", "message": "Attachment not found"}
    }
