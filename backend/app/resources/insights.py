from flask_jwt_extended import current_user
from flask_smorest import Blueprint
from marshmallow import fields

from app.auth import roles_required
from app.insights import build
from app.schemas import Schema

blp = Blueprint(
    "insights", __name__, url_prefix="/api/insights", description="Forecasts and insights"
)


class DayValue(Schema):
    date = fields.Date()
    takings = fields.Float()


class ForecastDay(Schema):
    date = fields.Date()
    expected = fields.Float()
    low = fields.Float()
    high = fields.Float()


class Comparison(Schema):
    key = fields.String()
    value = fields.Float()
    usual = fields.Float()
    change = fields.Integer()
    date = fields.Date()


class SalesOutlook(Schema):
    ready = fields.Boolean()
    days_of_history = fields.Integer()
    accuracy = fields.Integer(allow_none=True)
    history = fields.List(fields.Nested(DayValue))
    forecast = fields.List(fields.Nested(ForecastDay))
    comparisons = fields.List(fields.Nested(Comparison))


class RunningOut(Schema):
    id = fields.Integer()
    name = fields.String()
    quantity = fields.Integer()
    per_day = fields.Float()
    days_left = fields.Integer()
    suggested_order = fields.Integer()


class SlowMover(Schema):
    id = fields.Integer()
    name = fields.String()
    quantity = fields.Integer()
    tied_up = fields.Float()


class Profitable(Schema):
    id = fields.Integer()
    name = fields.String()
    profit = fields.Float()
    sold = fields.Integer()


class StockOutlook(Schema):
    running_out = fields.List(fields.Nested(RunningOut))
    slow_movers = fields.List(fields.Nested(SlowMover))
    most_profitable = fields.List(fields.Nested(Profitable))


class Customer(Schema):
    name = fields.String(allow_none=True)
    phone = fields.String(allow_none=True)
    total = fields.Float()
    visits = fields.Integer()
    last_at = fields.DateTime()


class CustomerOutlook(Schema):
    top = fields.List(fields.Nested(Customer))
    gone_quiet = fields.List(fields.Nested(Customer))


class Week(Schema):
    week = fields.Date()
    money_in = fields.Float(data_key="in", attribute="in")
    money_out = fields.Float(data_key="out", attribute="out")


class CashOutlook(Schema):
    ready = fields.Boolean()
    weeks = fields.List(fields.Nested(Week))
    expected_in = fields.Float(allow_none=True)
    expected_out = fields.Float(allow_none=True)
    expected_net = fields.Float(allow_none=True)
    balance = fields.Float(allow_none=True)
    balance_at = fields.DateTime(allow_none=True)
    projected_balance = fields.Float(allow_none=True)


class InsightsOut(Schema):
    sales = fields.Nested(SalesOutlook)
    stock = fields.Nested(StockOutlook)
    customers = fields.Nested(CustomerOutlook)
    cash = fields.Nested(CashOutlook)


@blp.route("")
@blp.response(200, InsightsOut)
@roles_required("admin")
def insights():
    return build(current_user.business)
