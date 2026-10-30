from backend.app.services.whatsapp_cloud_client import media_kind


def test_media_kind_maps_common_types():
    assert media_kind("photo.png") == ("image", "image/png")
    assert media_kind("clip.mp4")[0] == "video"
    assert media_kind("voice.ogg")[0] == "audio"
    assert media_kind("brochure.pdf") == ("document", "application/pdf")
    assert media_kind("notes.txt")[0] == "document"
