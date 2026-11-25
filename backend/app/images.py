import io

from flask import current_app, request
from flask_smorest import abort
from PIL import Image as PILImage
from PIL import ImageOps, UnidentifiedImageError

from app.extensions import db
from app.models import Image

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
PIL_MAX_PIXELS = 50_000_000


def read_upload(field="photo"):
    limit = current_app.config["MAX_UPLOAD_BYTES"]
    request.max_content_length = limit + 64 * 1024
    upload = request.files.get(field)
    if upload is None or not upload.filename:
        abort(400, message="Choose a photo to upload (JPEG, PNG or WebP, up to 5 MB).")
    raw = upload.read(limit + 1)
    if len(raw) > limit:
        abort(413, message="The photo is larger than 5 MB. Choose a smaller one.")
    return raw


def store_image(raw):
    PILImage.MAX_IMAGE_PIXELS = PIL_MAX_PIXELS
    try:
        with PILImage.open(io.BytesIO(raw)) as probe:
            fmt = probe.format
            probe.verify()
    except (UnidentifiedImageError, OSError, PILImage.DecompressionBombError):
        abort(400, message="That file is not a JPEG, PNG or WebP image.")
    if fmt not in ALLOWED_FORMATS:
        abort(400, message="Only JPEG, PNG and WebP photos are accepted.")

    with PILImage.open(io.BytesIO(raw)) as picture:
        picture = ImageOps.exif_transpose(picture)
        side = current_app.config["IMAGE_MAX_SIDE"]
        picture.thumbnail((side, side))
        if picture.mode not in ("RGB", "RGBA"):
            picture = picture.convert("RGBA" if "transparency" in picture.info else "RGB")
        out = io.BytesIO()
        picture.save(out, format="WEBP", quality=85, method=4)
        image = Image(
            content_type="image/webp",
            data=out.getvalue(),
            width=picture.width,
            height=picture.height,
        )
    db.session.add(image)
    db.session.flush()
    return image


def replace_photo(item, raw):
    old_id = item.image_id
    image = store_image(raw)
    item.image_id = image.id
    item.image_url = image_url(image.id)
    if old_id:
        db.session.execute(db.delete(Image).where(Image.id == old_id))
    return image


def remove_photo(item):
    old_id = item.image_id
    item.image_id = None
    item.image_url = None
    if old_id:
        db.session.execute(db.delete(Image).where(Image.id == old_id))


def image_url(image_id):
    return f"/api/images/{image_id}"
