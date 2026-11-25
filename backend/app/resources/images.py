from flask import Response
from flask_smorest import Blueprint, abort

from app.extensions import db
from app.models import Image

blp = Blueprint("images", __name__, url_prefix="/api/images", description="Photos")


@blp.route("/<string:image_id>")
@blp.doc(security=[])
def get_image(image_id):
    image = db.session.get(Image, image_id) if len(image_id) <= 36 else None
    if image is None:
        abort(404, message="Photo not found")
    response = Response(image.data, mimetype=image.content_type)
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers["Cross-Origin-Resource-Policy"] = "cross-origin"
    return response
