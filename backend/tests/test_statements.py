from datetime import datetime
from decimal import Decimal

import pytest

from app.statements import (
    StatementError,
    parse_csv,
    parse_sms,
    parse_statement_text,
    read_pdf,
)
from tests.statement_files import statement_pdf

STATEMENT = "\n".join(
    [
        "Receipt No. Completion Time Details Transaction Status Paid In Withdrawn Balance",
        "SC35W6JO6D 2024-03-03 21:45:19 Merchant Payment to 6350966 - Completed -5,410.00 7.95",
        "WINFRED NDANU NZILU",
        "TAQ7N0TEJR 2025-01-26 10:02:03 Customer Transfer of Funds Charge"
        " COMPLETED 0.00 7.00 10,066.71",
        "TAQ3K8PO97 2025-01-26 09:00:00 Pay Bill Online to 770809 - KPLC"
        " PREPAID COMPLETED 0.00 500.00 10,723.71",
        "conditions apply",
        "Page 2 of 12",
        "Receipt No Completion Time Details Transaction Status Paid in Withdraw Balance",
        "n",
        "TAQ1AAAAAA 2025-01-25 08:00:00 Funds received from - 2547******123"
        " JOHN DOE COMPLETED 1,500.00 0.00 11,223.71",
        "RHU5GB7Q7X 2023-08-30 Customer Transfer of Completed -13.00 878.66",
        "12:00:01 Funds Charge",
        "TAQ2BBBBBB 2025-01-25 07:00:00 Customer Withdrawal At Agent Till 123"
        " - JANE COMPLETED 0.00 1,000.00 9,723.71",
        "TAQ3CCCCCC 2025-01-24 07:00:00 Customer Transfer to 0712***678 -"
        " PETER Failed 0.00 100.00 9,423.71",
    ]
)


def test_statement_rows_are_read_with_direction_and_balance():
    entries, skipped = parse_statement_text(STATEMENT)

    assert skipped == 1
    assert [(e.receipt, e.direction, e.amount, e.kind) for e in entries] == [
        ("SC35W6JO6D", "out", Decimal("5410.00"), "merchant"),
        ("TAQ7N0TEJR", "out", Decimal("7.00"), "fee"),
        ("TAQ3K8PO97", "out", Decimal("500.00"), "paybill"),
        ("TAQ1AAAAAA", "in", Decimal("1500.00"), "received"),
        ("RHU5GB7Q7X", "out", Decimal("13.00"), "fee"),
        ("TAQ2BBBBBB", "out", Decimal("1000.00"), "withdrawal"),
    ]
    merchant, charge, paybill, received, _, _ = entries
    assert merchant.counterparty == "WINFRED NDANU NZILU"
    assert merchant.balance == Decimal("7.95")
    assert charge.counterparty == "M-Pesa charges"
    assert paybill.counterparty == "KPLC PREPAID"
    assert (received.counterparty, received.phone) == ("JOHN DOE", "2547******123")
    assert received.occurred_at == datetime(2025, 1, 25, 8, 0)
    assert entries[4].occurred_at == datetime(2023, 8, 30, 12, 0, 1)


def test_rows_without_amounts_are_skipped():
    entries, skipped = parse_statement_text("ABCDEFGH12 2025-01-01 10:00:00 Odd row COMPLETED")

    assert (entries, skipped) == ([], 1)


def test_a_protected_pdf_opens_with_its_password():
    data = statement_pdf(
        [
            "TAQ1AAAAAA 2025-01-25 08:00:00 Funds received from - 0712***678 MARY COMPLETED "
            "300.00 0.00 1,300.00"
        ]
    )

    entries, _ = parse_statement_text(read_pdf(data, "4321"))

    assert [(e.receipt, e.amount, e.counterparty) for e in entries] == [
        ("TAQ1AAAAAA", Decimal("300.00"), "MARY")
    ]
    with pytest.raises(StatementError, match="password did not open"):
        read_pdf(data, "wrong")


def test_files_that_are_not_pdfs_are_refused():
    with pytest.raises(StatementError, match="not a readable PDF"):
        read_pdf(b"%PDF-1.4 broken")


def test_csv_statements_are_read():
    data = (
        b"Receipt No,Completion Time,Details,Transaction Status,Paid In,Withdrawn,Balance\n"
        b"TAQ1AAAAAA,2025-01-25 08:00:00,Funds received from - 0712***678 MARY,Completed,300.00,,"
        b"1300.00\n"
        b"TAQ1AAAAAB,2025-01-25 09:00:00,Pay Bill Online to 888880 - NAIROBI WATER,Completed,,"
        b"450.00,850.00\n"
        b"TAQ1AAAAAC,2025-01-25 10:00:00,Customer Transfer to - PETER,Failed,,100.00,850.00\n"
        b"bad,2025-01-25 10:00:00,Nothing,Completed,1.00,,1.00\n"
        b"TAQ1AAAAAD,not a date,Nothing,Completed,1.00,,1.00\n"
    )

    entries, skipped = parse_csv(data)

    assert [(e.receipt, e.direction, e.amount) for e in entries] == [
        ("TAQ1AAAAAA", "in", Decimal("300.00")),
        ("TAQ1AAAAAB", "out", Decimal("450.00")),
    ]
    assert skipped == 3


def test_csv_needs_the_main_columns():
    with pytest.raises(StatementError, match="needs Receipt No"):
        parse_csv(b"Date,Amount\n2025-01-01,5\n")


SMS = """QK71ZP3X12 Confirmed. You have received Ksh1,500.00 from JOHN KAMAU 0712345678 on
18/11/26 at 9:41 AM New M-PESA balance is Ksh12,345.00. Separate personal and business funds.
XXXYYYZZZ9 Confirmed. Ksh80.00 sent to MSEE WA CHIPO 0704444444 on 12/4/26 at 1:57 PM. New
M-PESA balance is Ksh100.00. Transaction cost, Ksh7.00.
ABCDEF1234 Confirmed. Ksh200.00 paid to MAMA MBOGA SHOP. on 1/11/26 at 10:23 AM.New M-PESA
balance is Ksh900.00. Transaction cost, Ksh0.00.
ABCDEF1235 Confirmed. Ksh500.00 sent to KPLC PREPAID for account 37185000 on 2/11/26 at 8:00 PM
New M-PESA balance is Ksh400.00.
ABCDEF1236 Confirmed. on 3/11/26 at 1:00 PMWithdraw Ksh1,000.00 from 123456 - JANE AGENT SHOP
New M-PESA balance is Ksh0.00. Transaction cost, Ksh29.00.
ABCDEF1237 Confirmed. You bought Ksh50.00 of airtime on 4/11/26 at 7:00 AM. New M-PESA balance
is Ksh10.00.
ABCDEF1238 Confirmed. on 5/11/26 at 6:00 PM Give Ksh2,000.00 cash to JOE AGENT New M-PESA
balance is Ksh2,010.00.
ABCDEF1239 Confirmed. Ksh100 received from 2547******321 ALI HASSAN on 6/11/26 at 9:00 AM New
Utility balance is Ksh5,100.00.
ABCDEF1240 Confirmed. Something new we have never seen.
"""


def test_pasted_sms_messages_are_understood():
    entries, skipped = parse_sms(SMS)

    assert skipped == 1
    assert [(e.receipt, e.direction, e.kind, e.amount, e.counterparty) for e in entries] == [
        ("QK71ZP3X12", "in", "received", Decimal("1500.00"), "JOHN KAMAU"),
        ("XXXYYYZZZ9", "out", "sent", Decimal("80.00"), "MSEE WA CHIPO"),
        ("ABCDEF1234", "out", "merchant", Decimal("200.00"), "MAMA MBOGA SHOP"),
        ("ABCDEF1235", "out", "paybill", Decimal("500.00"), "KPLC PREPAID"),
        ("ABCDEF1236", "out", "withdrawal", Decimal("1000.00"), "JANE AGENT SHOP"),
        ("ABCDEF1237", "out", "airtime", Decimal("50.00"), "Safaricom"),
        ("ABCDEF1238", "in", "deposit", Decimal("2000.00"), "JOE AGENT"),
        ("ABCDEF1239", "in", "received", Decimal("100"), "ALI HASSAN"),
    ]
    first = entries[0]
    assert (first.phone, first.balance) == ("0712345678", Decimal("12345.00"))
    assert first.occurred_at == datetime(2026, 11, 18, 9, 41)
    assert entries[1].extra == {"fee": Decimal("7.00")}
    assert entries[2].extra == {}
    assert entries[4].occurred_at == datetime(2026, 11, 3, 13, 0)
