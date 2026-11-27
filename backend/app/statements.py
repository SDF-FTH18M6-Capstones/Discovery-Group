import csv
import io
import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation

from pypdf import PdfReader
from pypdf.errors import FileNotDecryptedError, PdfReadError

RECEIPT = r"[A-Z0-9]{10}"
ROW_START = re.compile(
    rf"(?m)^\s*({RECEIPT})\s+(\d{{4}}-\d{{2}}-\d{{2}})(?:\s+(\d{{2}}:\d{{2}}:\d{{2}}))?"
)
STATUS = re.compile(
    r"\b(Completed|COMPLETED|Failed|FAILED|Cancelled|CANCELLED|Reversed|REVERSED)\b"
)
NUMBER = re.compile(r"-?\d[\d,]*\.\d{2}")
TIME = re.compile(r"\b(\d{2}:\d{2}:\d{2})\b")
NOISE = re.compile(
    r"^\s*(Receipt No|Status$|n$|Page \d+ of \d+|.*conditions apply|For self-help|"
    r"DETAILED STATEMENT)",
    re.IGNORECASE,
)
PHONE = re.compile(r"(?:\+?254|0)\s?[17][\d*]{6,10}\d")


class StatementError(Exception):
    pass


@dataclass
class Entry:
    receipt: str
    occurred_at: datetime
    direction: str
    amount: Decimal
    details: str
    balance: Decimal | None = None
    counterparty: str = ""
    phone: str | None = None
    kind: str = "other"
    extra: dict = field(default_factory=dict)


KINDS = [
    ("fee", ("charge", "transaction cost")),
    ("withdrawal", ("withdrawal at agent", "customer withdrawal", "withdraw ")),
    ("deposit", ("deposit of funds", "agent deposit", "give ")),
    ("airtime", ("airtime", "bundle purchase", "data bundle")),
    ("loan", ("fuliza", "m-shwari", "od loan", "overdraft", "kcb m-pesa", "loan")),
    ("paybill", ("pay bill",)),
    ("merchant", ("merchant payment", "buy goods", "customer payment to small business")),
    (
        "customer_payment",
        ("merchant customer payment from", "business payment from", "pay bill from"),
    ),
    ("received", ("funds received", "received from", "customer transfer from", "transfer from")),
    ("sent", ("customer transfer to", "transfer to", "sent to", "send money")),
    ("reversal", ("reversal",)),
]


def classify(details):
    lowered = details.lower()
    for kind, words in KINDS:
        if any(word in lowered for word in words):
            return kind
    return "other"


def money(text):
    try:
        return Decimal(text.replace(",", ""))
    except (InvalidOperation, AttributeError):
        return None


def counterparty_of(details, kind="other"):
    if kind == "fee":
        return "M-Pesa charges", None
    phone_match = PHONE.search(details)
    phone = phone_match.group().replace(" ", "").replace("+", "") if phone_match else None
    rest = details
    for marker in (" - ", " from ", " to ", " by "):
        if marker in rest:
            rest = rest.split(marker, 1)[1]
            break
    rest = PHONE.sub("", rest)
    rest = re.sub(r"^\s*\d{5,}\s*-?\s*", "", rest)
    rest = re.sub(r"\s+Acc\.?.*$", "", rest, flags=re.IGNORECASE)
    name = re.sub(r"\s+", " ", rest).strip(" -.")
    return name[:120], phone


def _rows(text):
    starts = list(ROW_START.finditer(text))
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        yield match, text[match.end() : end]


def parse_statement_text(text):
    entries, skipped = [], 0
    for match, body in _rows(text):
        receipt, day, clock = match.groups()
        body = "\n".join(line for line in body.splitlines() if not NOISE.search(line))
        status = STATUS.search(body)
        if status is None:
            skipped += 1
            continue
        if status.group(1).lower() != "completed":
            skipped += 1
            continue
        before, after = body[: status.start()], body[status.end() :]
        first_line, _, wrapped = after.partition("\n")
        numbers = NUMBER.findall(first_line)
        if clock is None:
            found = TIME.search(body)
            clock = found.group(1) if found else "00:00:00"
            before = TIME.sub(" ", before)
            wrapped = TIME.sub(" ", wrapped)
        if len(numbers) >= 3:
            paid_in, withdrawn, balance = (money(n) for n in numbers[-3:])
            direction = "in" if paid_in and paid_in > 0 else "out"
            amount = paid_in if direction == "in" else abs(withdrawn or Decimal(0))
        elif len(numbers) == 2:
            signed, balance = money(numbers[0]), money(numbers[1])
            direction = "out" if signed < 0 else "in"
            amount = abs(signed)
        else:
            skipped += 1
            continue
        if not amount:
            skipped += 1
            continue
        details = re.sub(r"\s+", " ", f"{before} {wrapped}").strip()
        kind = classify(details)
        name, phone = counterparty_of(details, kind)
        entries.append(
            Entry(
                receipt=receipt,
                occurred_at=datetime.fromisoformat(f"{day}T{clock}"),
                direction=direction,
                amount=amount,
                balance=balance,
                details=details[:300],
                counterparty=name,
                phone=phone,
                kind=kind,
            )
        )
    return entries, skipped


def read_pdf(data, password=""):
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted and not reader.decrypt(password or ""):
            raise StatementError("That password did not open the statement.")
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    except FileNotDecryptedError as err:
        raise StatementError("That password did not open the statement.") from err
    except PdfReadError as err:
        raise StatementError("This file is not a readable PDF.") from err


COLUMNS = {
    "receipt": ("receipt no", "receipt no.", "receipt", "transaction id"),
    "time": ("completion time", "date", "transaction date"),
    "details": ("details", "description", "narration"),
    "status": ("transaction status", "status"),
    "paid_in": ("paid in", "money in", "credit"),
    "withdrawn": ("withdrawn", "withdraw", "paid out", "money out", "debit"),
    "balance": ("balance",),
}


def parse_csv(data):
    text = data.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))
    headers = {(name or "").strip().lower(): name for name in reader.fieldnames or []}
    column = {}
    for key, names in COLUMNS.items():
        column[key] = next((headers[n] for n in names if n in headers), None)
    if not all(column[k] for k in ("receipt", "time", "details")):
        raise StatementError("The CSV needs Receipt No, Completion Time and Details columns.")
    entries, skipped = [], 0
    for line in reader:
        status = (line.get(column["status"]) or "Completed") if column["status"] else "Completed"
        paid_in = money(line.get(column["paid_in"]) or "0") if column["paid_in"] else None
        withdrawn = money(line.get(column["withdrawn"]) or "0") if column["withdrawn"] else None
        receipt = (line.get(column["receipt"]) or "").strip()
        if status.strip().lower() != "completed" or not re.fullmatch(RECEIPT, receipt):
            skipped += 1
            continue
        try:
            occurred = datetime.fromisoformat((line.get(column["time"]) or "").strip())
        except ValueError:
            skipped += 1
            continue
        if paid_in and paid_in > 0:
            direction, amount = "in", paid_in
        elif withdrawn:
            direction, amount = "out", abs(withdrawn)
        else:
            skipped += 1
            continue
        details = (line.get(column["details"]) or "").strip()
        kind = classify(details)
        name, phone = counterparty_of(details, kind)
        balance = money(line.get(column["balance"]) or "") if column["balance"] else None
        entries.append(
            Entry(receipt, occurred, direction, amount, details[:300], balance, name, phone, kind)
        )
    return entries, skipped


SMS_START = re.compile(rf"\b({RECEIPT})\s+Confirmed\b\.?", re.IGNORECASE)
KSH = r"Ksh\s?([\d,]+(?:\.\d{1,2})?)"
SMS_WHEN = re.compile(
    r"on\s+(\d{1,2})/(\d{1,2})/(\d{2,4})\s+at\s+(\d{1,2}):(\d{2})\s*([AP]M)", re.IGNORECASE
)
SMS_BALANCE = re.compile(rf"balance is\s+{KSH}", re.IGNORECASE)
SMS_COST = re.compile(rf"Transaction cost,?\s+{KSH}", re.IGNORECASE)
SMS_PATTERNS = [
    ("in", "received", re.compile(rf"received\s+{KSH}\s+from\s+(.+?)\s+on\s+\d", re.IGNORECASE)),
    (
        "in",
        "received",
        re.compile(
            rf"{KSH}\s+received from\s+(.+?)(?:\s+on\s+\d|\s+Account|\s+New)", re.IGNORECASE
        ),
    ),
    ("in", "deposit", re.compile(rf"Give\s+{KSH}\s+cash to\s+(.+?)\s+New", re.IGNORECASE)),
    ("out", "withdrawal", re.compile(rf"Withdraw\s+{KSH}\s+from\s+(.+?)\s+New", re.IGNORECASE)),
    (
        "out",
        "paybill",
        re.compile(rf"{KSH}\s+sent to\s+(.+?)\s+for account\s+(\S+)", re.IGNORECASE),
    ),
    ("out", "sent", re.compile(rf"{KSH}\s+sent to\s+(.+?)\s+on\s+\d", re.IGNORECASE)),
    ("out", "merchant", re.compile(rf"{KSH}\s+paid to\s+(.+?)\.?\s+on\s+\d", re.IGNORECASE)),
    ("out", "airtime", re.compile(rf"bought\s+{KSH}\s+of airtime()", re.IGNORECASE)),
]


def _sms_time(text):
    found = SMS_WHEN.search(text)
    if not found:
        return None
    day, month, year, hour, minute, half = found.groups()
    year = int(year) + (2000 if len(year) == 2 else 0)
    hour = int(hour) % 12 + (12 if half.upper() == "PM" else 0)
    return datetime(year, int(month), int(day), hour, int(minute))


def parse_sms(text):
    starts = list(SMS_START.finditer(text))
    entries, skipped = [], 0
    for index, match in enumerate(starts):
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        message = re.sub(r"\s+", " ", text[match.start() : end]).strip()
        occurred = _sms_time(message)
        parsed = None
        for direction, kind, pattern in SMS_PATTERNS:
            found = pattern.search(message)
            if found:
                parsed = (direction, kind, found)
                break
        if parsed is None or occurred is None:
            skipped += 1
            continue
        direction, kind, found = parsed
        amount = money(found.group(1))
        who = (found.group(2) or "").strip() if found.lastindex and found.lastindex >= 2 else ""
        name, phone = counterparty_of(f" - {who}") if who else ("Safaricom", None)
        balance = SMS_BALANCE.search(message)
        entry = Entry(
            receipt=match.group(1).upper(),
            occurred_at=occurred,
            direction=direction,
            amount=amount,
            details=message[:300],
            balance=money(balance.group(1)) if balance else None,
            counterparty=name or who[:120],
            phone=phone,
            kind=kind,
        )
        cost = SMS_COST.search(message)
        if cost and money(cost.group(1)):
            entry.extra["fee"] = money(cost.group(1))
        entries.append(entry)
    return entries, skipped
