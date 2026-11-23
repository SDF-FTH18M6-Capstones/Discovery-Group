from flask_jwt_extended import current_user
from flask_smorest import Blueprint
from marshmallow import fields, validate
from sqlalchemy.orm import selectinload

from app.audit import audit
from app.auth import roles_required
from app.crud import PageQuery, delete, get_or_404, page_schema, paginate, save
from app.extensions import db
from app.models import Expense
from app.schemas import Schema

blp = Blueprint("expenses", __name__, url_prefix="/api/expenses", description="Expenses (Admin)")


class ExpenseSchema(Schema):
    id = fields.Integer(dump_only=True)
    spent_on = fields.Date(required=True)
    category = fields.String(required=True, validate=validate.Length(min=2, max=60))
    description = fields.String(
        allow_none=True, load_default=None, validate=validate.Length(max=300)
    )
    amount = fields.Decimal(
        required=True, places=2, as_string=True, validate=validate.Range(min=0.01, max=10**9)
    )
    created_by_name = fields.String(attribute="creator.full_name", dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class ExpenseQuery(PageQuery):
    date_from = fields.Date(load_default=None)
    date_to = fields.Date(load_default=None)
    category = fields.String(load_default=None)


@blp.route("/")
@blp.arguments(ExpenseQuery, location="query")
@blp.response(200, page_schema(ExpenseSchema))
@roles_required("admin")
def list_expenses(args):
    query = (
        db.select(Expense)
        .options(selectinload(Expense.creator))
        .order_by(Expense.spent_on.desc(), Expense.id.desc())
    )
    if args["date_from"]:
        query = query.where(Expense.spent_on >= args["date_from"])
    if args["date_to"]:
        query = query.where(Expense.spent_on <= args["date_to"])
    if args["category"]:
        query = query.where(Expense.category == args["category"])
    return paginate(query, args["page"], args["per_page"])


@blp.route("/", methods=["POST"])
@blp.arguments(ExpenseSchema)
@blp.response(201, ExpenseSchema)
@roles_required("admin")
def create_expense(data):
    expense = save(Expense(**data, created_by=current_user.id), "Could not save this expense")
    audit("created", "expense", expense.id, f"Expense {expense.category} {expense.amount}")
    db.session.commit()
    return expense


@blp.route("/<int:expense_id>", methods=["PUT"])
@blp.arguments(ExpenseSchema)
@blp.response(200, ExpenseSchema)
@roles_required("admin")
def update_expense(data, expense_id):
    expense = get_or_404(Expense, expense_id)
    for key, value in data.items():
        setattr(expense, key, value)
    audit("updated", "expense", expense.id, f"Expense {expense.category} {expense.amount}")
    return save(expense, "Could not save this expense")


@blp.route("/<int:expense_id>", methods=["DELETE"])
@blp.response(204)
@roles_required("admin")
def delete_expense(expense_id):
    expense = get_or_404(Expense, expense_id)
    audit("deleted", "expense", expense.id, f"Expense {expense.category} {expense.amount} deleted")
    delete(expense, "Could not delete this expense")
