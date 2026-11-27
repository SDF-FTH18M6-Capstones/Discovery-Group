from flask import request
from flask_jwt_extended import current_user
from flask_smorest import Blueprint, abort
from marshmallow import fields, validate

from app.auth import roles_required
from app.crud import PageQuery, get_or_404, page_schema, paginate
from app.extensions import db
from app.models import MoneyImport, MoneyTransaction
from app.models.money import CATEGORIES, MONEY_IN, MONEY_OUT
from app.money import import_entries, remember
from app.schemas import Schema
from app.statements import StatementError, parse_csv, parse_sms, parse_statement_text, read_pdf

blp = Blueprint("money", __name__, url_prefix="/api/money", description="M-Pesa money in and out")

MAX_STATEMENT_BYTES = 10 * 1024 * 1024


class ImportOut(Schema):
    id = fields.Integer()
    source = fields.String()
    filename = fields.String(allow_none=True)
    added = fields.Integer()
    duplicates = fields.Integer()
    skipped = fields.Integer()
    first_at = fields.DateTime(allow_none=True)
    last_at = fields.DateTime(allow_none=True)
    created_at = fields.DateTime()


class TransactionOut(Schema):
    id = fields.Integer()
    receipt = fields.String()
    occurred_at = fields.DateTime()
    direction = fields.String()
    amount = fields.Decimal(places=2, as_string=True)
    balance = fields.Decimal(places=2, as_string=True, allow_none=True)
    kind = fields.String()
    category = fields.String()
    counterparty = fields.String(allow_none=True)
    phone = fields.String(allow_none=True)
    details = fields.String(allow_none=True)
    sale_id = fields.Integer(allow_none=True)


class TransactionQuery(PageQuery):
    direction = fields.String(load_default=None, validate=validate.OneOf(("in", "out")))
    category = fields.String(load_default=None, validate=validate.OneOf(CATEGORIES))
    search = fields.String(load_default=None)
    import_id = fields.Integer(load_default=None)


class SmsIn(Schema):
    text = fields.String(
        required=True,
        validate=validate.Length(min=20, max=100_000, error="Paste at least one M-Pesa message."),
    )


class CategoryIn(Schema):
    category = fields.String(required=True, validate=validate.OneOf(CATEGORIES))
    remember = fields.Boolean(load_default=True)


class CategoryOut(Schema):
    transaction = fields.Nested(TransactionOut)
    also_changed = fields.Integer()


class CategoriesOut(Schema):
    money_in = fields.List(fields.String())
    money_out = fields.List(fields.String())


def finish(entries, skipped, source, filename):
    if not entries:
        db.session.rollback()
        abort(
            422,
            message="No completed M-Pesa transactions were found. Check that this is a full "
            "M-Pesa statement or a set of M-Pesa messages.",
        )
    batch = import_entries(entries, skipped, source, filename, current_user)
    db.session.commit()
    return batch


@blp.route("/categories")
@blp.response(200, CategoriesOut)
@roles_required("admin")
def categories():
    return {"money_in": MONEY_IN, "money_out": MONEY_OUT}


@blp.route("/statement", methods=["POST"])
@blp.response(201, ImportOut)
@roles_required("admin")
def upload_statement():
    request.max_content_length = MAX_STATEMENT_BYTES + 64 * 1024
    upload = request.files.get("file")
    if upload is None or not upload.filename:
        abort(400, message="Choose an M-Pesa statement (PDF or CSV).")
    data = upload.read(MAX_STATEMENT_BYTES + 1)
    if len(data) > MAX_STATEMENT_BYTES:
        abort(413, message="The statement is larger than 10 MB.")
    name = upload.filename[:200]
    try:
        if data.startswith(b"%PDF"):
            entries, skipped = parse_statement_text(
                read_pdf(data, request.form.get("password", ""))
            )
            source = "statement"
        elif name.lower().endswith(".csv"):
            entries, skipped = parse_csv(data)
            source = "csv"
        else:
            abort(400, message="Upload the statement as a PDF or CSV file.")
    except StatementError as err:
        abort(422, message=str(err))
    return finish(entries, skipped, source, name)


@blp.route("/sms", methods=["POST"])
@blp.arguments(SmsIn)
@blp.response(201, ImportOut)
@roles_required("admin")
def paste_sms(data):
    entries, skipped = parse_sms(data["text"])
    return finish(entries, skipped, "sms", None)


@blp.route("/imports")
@blp.arguments(PageQuery, location="query")
@blp.response(200, page_schema(ImportOut))
@roles_required("admin")
def imports(args):
    query = db.select(MoneyImport).order_by(MoneyImport.created_at.desc(), MoneyImport.id.desc())
    return paginate(query, args["page"], args["per_page"])


@blp.route("/imports/<int:import_id>", methods=["DELETE"])
@blp.response(204)
@roles_required("admin")
def undo_import(import_id):
    db.session.delete(get_or_404(MoneyImport, import_id))
    db.session.commit()


@blp.route("/transactions")
@blp.arguments(TransactionQuery, location="query")
@blp.response(200, page_schema(TransactionOut))
@roles_required("admin")
def transactions(args):
    query = db.select(MoneyTransaction).order_by(
        MoneyTransaction.occurred_at.desc(), MoneyTransaction.id.desc()
    )
    for field in ("direction", "category", "import_id"):
        if args[field]:
            query = query.where(getattr(MoneyTransaction, field) == args[field])
    if args["search"]:
        term = f"%{args['search']}%"
        query = query.where(
            db.or_(
                MoneyTransaction.counterparty.ilike(term),
                MoneyTransaction.receipt.ilike(term),
                MoneyTransaction.phone.ilike(term),
            )
        )
    return paginate(query, args["page"], args["per_page"])


@blp.route("/transactions/<int:transaction_id>", methods=["PUT"])
@blp.arguments(CategoryIn)
@blp.response(200, CategoryOut)
@roles_required("admin")
def categorise(data, transaction_id):
    transaction = get_or_404(MoneyTransaction, transaction_id)
    allowed = MONEY_IN if transaction.direction == "in" else MONEY_OUT
    if data["category"] not in allowed:
        abort(422, message="That category is for money going the other way.")
    transaction.category = data["category"]
    also = remember(transaction, data["category"]) if data["remember"] else 0
    db.session.commit()
    return {"transaction": transaction, "also_changed": also}
