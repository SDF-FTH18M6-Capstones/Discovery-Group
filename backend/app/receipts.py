import base64
import json
import re
import urllib.error
import urllib.request
from datetime import date
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher

AMOUNT = re.compile(r"(?<![\d.])(\d{1,3}(?:,\d{3})+|\d+)\.(\d{2})(?!\d)")
QUANTITY = re.compile(r"(\d+(?:\.\d+)?)\s*[xX@*]\s*(\d[\d,]*\.\d{2})")
DATES = [
    (re.compile(r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b"), ("y", "m", "d")),
    (re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b"), ("d", "m", "y")),
    (re.compile(r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{2})\b"), ("d", "m", "y")),
]
MONTHS = "jan feb mar apr may jun jul aug sep oct nov dec".split()
WORDY_DATE = re.compile(
    r"\b(\d{1,2})[\s-]+(" + "|".join(MONTHS) + r")[a-z]*[\s,-]+(\d{2,4})\b", re.I
)
NUMBER = re.compile(
    r"\b(?:receipt|invoice|bill|trans(?:action)?|cu invoice|ticket|sale)[ \t]*"
    r"(?:no\.?|number|num|#|id)?[ \t]*[:.#-]?[ \t]*((?=[A-Z/-]*\d)[A-Z0-9][A-Z0-9/-]{2,24})",
    re.I,
)
TOTAL_WORDS = ("grand total", "total amount", "amount due", "total kes", "total ksh", "total")
NOT_TOTAL = (
    "subtotal",
    "sub total",
    "sub-total",
    "total tax",
    "total vat",
    "total items",
    "total qty",
)
TAX_WORDS = ("vat", "tax")
NOT_ITEMS = (
    "total",
    "vat",
    "tax",
    "cash",
    "change",
    "tender",
    "balance",
    "m-pesa",
    "mpesa",
    "paid",
    "discount",
    "items",
    "tel",
    "pin",
    "till",
    "paybill",
    "card",
    "rounding",
    "amount due",
)
BUSINESS_WORDS = (
    "ltd",
    "limited",
    "supermarket",
    "stores",
    "store",
    "shop",
    "wholesale",
    "wholesalers",
    "enterprises",
    "hardware",
    "pharmacy",
    "distributors",
    "traders",
    "mart",
)
HEADER_NOISE = ("welcome", "receipt", "tax invoice", "cash sale", "invoice", "copy", "duplicate")


def amount_of(text):
    found = AMOUNT.findall(text)
    if not found:
        return None
    whole, cents = found[-1]
    return Decimal(f"{whole.replace(',', '')}.{cents}")


def as_decimal(value):
    try:
        return Decimal(str(value).replace(",", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def find_date(text):
    match = WORDY_DATE.search(text)
    if match:
        day, month, year = match.groups()
        year = int(year) + (2000 if len(year) == 2 else 0)
        try:
            return date(year, MONTHS.index(month[:3].lower()) + 1, int(day))
        except ValueError:
            pass
    for pattern, order in DATES:
        for match in pattern.finditer(text):
            parts = dict(zip(order, (int(g) for g in match.groups()), strict=True))
            if parts["y"] < 100:
                parts["y"] += 2000
            try:
                return date(parts["y"], parts["m"], parts["d"])
            except ValueError:
                continue
    return None


def find_supplier(lines):
    top = [line for line in lines[:8] if len(re.sub(r"[^A-Za-z]", "", line)) >= 3]
    for line in top:
        if any(word in line.lower().split() or word in line.lower() for word in BUSINESS_WORDS):
            return line.strip(" *-=")
    for line in top:
        if not any(word in line.lower() for word in HEADER_NOISE) and not AMOUNT.search(line):
            return line.strip(" *-=")
    return ""


def find_total(lines):
    for words in TOTAL_WORDS:
        for index, line in enumerate(lines):
            lowered = line.lower()
            if words in lowered and not any(word in lowered for word in NOT_TOTAL):
                value = amount_of(line)
                if value is None and index + 1 < len(lines):
                    value = amount_of(lines[index + 1])
                if value:
                    return value, index
    return None, len(lines)


def find_items(lines):
    items, waiting = [], None
    for line in lines:
        lowered = line.lower()
        if any(word in lowered for word in NOT_ITEMS):
            waiting = None
            continue
        price = QUANTITY.search(line)
        amount = amount_of(line)
        words = re.sub(r"[\d.,@xX*:/%-]+", " ", line).strip()
        if amount is None:
            waiting = line.strip() if len(re.sub(r"[^A-Za-z]", "", line)) >= 3 else None
            continue
        quantity, unit = (
            (Decimal(price.group(1)), as_decimal(price.group(2))) if price else (None, None)
        )
        description = re.sub(r"\s+", " ", (line[: price.start()] if price else line))
        description = AMOUNT.sub("", description).strip(" -:*")
        if len(re.sub(r"[^A-Za-z]", "", description)) < 3:
            if waiting is None:
                continue
            description = waiting
        elif not words:
            continue
        waiting = None
        if quantity is None:
            quantity, unit = Decimal(1), amount
        items.append(
            {
                "description": description[:150],
                "quantity": quantity.normalize() if quantity % 1 else int(quantity),
                "unit_price": unit,
                "amount": amount,
            }
        )
    return items


def parse_receipt_text(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    total, total_at = find_total(lines)
    tax = None
    for line in lines[total_at:] + lines[:total_at]:
        if (
            any(word in line.lower().split(":")[0] for word in TAX_WORDS)
            and "pin" not in line.lower()
        ):
            tax = amount_of(line)
            if tax:
                break
    number = NUMBER.search(text or "")
    items = find_items(lines[:total_at])
    if total is None and items:
        total = sum((item["amount"] for item in items), Decimal(0))
    return {
        "supplier": find_supplier(lines),
        "date": find_date(text or ""),
        "number": number.group(1) if number else None,
        "total": total,
        "tax": tax,
        "items": items,
    }


def similarity(a, b):
    a, b = a.lower().strip(), b.lower().strip()
    if not a or not b:
        return 0
    if a in b or b in a:
        return 0.9
    return SequenceMatcher(None, a, b).ratio()


def best_match(name, choices, threshold=0.6):
    scored = [(similarity(name, label), key) for key, label in choices]
    score, key = max(scored, default=(0, None))
    return key if score >= threshold else None


class ReaderError(Exception):
    pass


PROMPT = (
    "Read this purchase receipt from a shop in Kenya. Reply with JSON only, no other text, "
    'shaped like {"supplier": "", "date": "YYYY-MM-DD", "number": "", "total": 0, '
    '"tax": 0, "items": [{"description": "", "quantity": 1, "unit_price": 0, "amount": 0}]}. '
    "Use null for anything you cannot read. Amounts are in shillings, without commas."
)


def read_with_ai(image, media_type, config):
    body = {
        "model": config["RECEIPT_AI_MODEL"],
        "max_tokens": 2000,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": base64.b64encode(image).decode(),
                        },
                    },
                    {"type": "text", "text": PROMPT},
                ],
            }
        ],
    }
    request = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={
            "x-api-key": config["RECEIPT_AI_KEY"],
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            reply = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as err:
        raise ReaderError("The receipt could not be read online just now.") from err
    text = "".join(part.get("text", "") for part in reply.get("content", []))
    found = re.search(r"\{.*\}", text, re.S)
    if not found:
        raise ReaderError("The receipt could not be read. Try a clearer photo.")
    try:
        data = json.loads(found.group())
    except ValueError as err:
        raise ReaderError("The receipt could not be read. Try a clearer photo.") from err
    return clean_reading(data)


def clean_reading(data):
    try:
        when = date.fromisoformat(data.get("date") or "")
    except (TypeError, ValueError):
        when = None
    items = []
    for item in data.get("items") or []:
        amount = as_decimal(item.get("amount"))
        if not item.get("description") or amount is None:
            continue
        quantity = as_decimal(item.get("quantity") or 1) or Decimal(1)
        items.append(
            {
                "description": str(item["description"])[:150],
                "quantity": quantity.normalize() if quantity % 1 else int(quantity),
                "unit_price": as_decimal(item.get("unit_price")) or (amount / quantity),
                "amount": amount,
            }
        )
    return {
        "supplier": str(data.get("supplier") or "")[:150],
        "date": when,
        "number": (str(data["number"])[:40] if data.get("number") else None),
        "total": as_decimal(data.get("total")) if data.get("total") is not None else None,
        "tax": as_decimal(data.get("tax")) if data.get("tax") is not None else None,
        "items": items,
    }
