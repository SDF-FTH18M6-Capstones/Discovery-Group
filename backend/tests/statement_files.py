import io

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

HEADER = "Receipt No. Completion Time Details Transaction Status Paid In Withdrawn Balance"


def escape(line):
    return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def statement_pdf(lines, password="4321"):
    writer = PdfWriter()
    page = writer.add_blank_page(612, 792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    text = " ".join(f"({escape(line)}) Tj T*" for line in [HEADER, *lines])
    stream = DecodedStreamObject()
    stream.set_data(f"BT /F1 7 Tf 20 770 Td 9 TL {text} ET".encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    if password:
        writer.encrypt(password, algorithm="AES-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()
