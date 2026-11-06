"""Check exported PDF content and remove variable producer timestamps.

Run with the isolated document runtime (pypdf), not the analysis environment.
"""

import argparse
import hashlib
import json
import re
from io import BytesIO
from pathlib import Path


def validate(root):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, ByteStringObject

    checks = {}
    for name in ("report", "slides"):
        path = root / f"reports/rendered/{name}.pdf"
        reader = PdfReader(BytesIO(path.read_bytes()))
        text = "\n".join(page.extract_text() for page in reader.pages)
        if "{{v:" in text or "{{meta:" in text:
            raise ValueError("Unresolved PDF placeholders")
        if "Дмитро Степанюк" not in text or "МУП-1" not in text:
            raise ValueError("Missing Ukrainian author/group in PDF")
        if name == "slides" and len(reader.pages) != 16:
            raise ValueError("Expected exactly sixteen PDF slides")
        if name == "report" and not all(
            t in text for t in ("Бібліографія", "guardian_mother", "HC3")
        ):
            raise ValueError("Report PDF lost bibliography or model appendix")
        writer = PdfWriter(clone_from=reader)
        writer.add_metadata({"/CreationDate": "D:20261106000000Z", "/ModDate": "D:20261106000000Z"})
        stable_id = hashlib.sha256(text.encode()).digest()[:16]
        writer._ID = ArrayObject([ByteStringObject(stable_id), ByteStringObject(stable_id)])
        if "/Metadata" in writer.root_object:
            metadata = writer.root_object["/Metadata"].get_object()
            xml = metadata.get_data().decode("utf-8")
            for field in ("ModifyDate", "CreateDate"):
                xml = re.sub(
                    rf"<xmp:{field}>.*?</xmp:{field}>",
                    f"<xmp:{field}>2026-11-06T00:00:00Z</xmp:{field}>",
                    xml,
                )
            for field in ("InstanceID", "DocumentID"):
                xml = re.sub(
                    rf"<xmpMM:{field}>.*?</xmpMM:{field}>",
                    f"<xmpMM:{field}>{stable_id.hex()}</xmpMM:{field}>",
                    xml,
                )
            metadata.set_data(xml.encode("utf-8"))
        temporary = path.with_suffix(".normalized.pdf")
        writer.write(temporary)
        reader.close()
        temporary.replace(path)
        checks[name] = {
            "pages": len(writer.pages),
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
    qa = root / "build/p08"
    (qa / "pdf_validation.json").write_text(json.dumps(checks, indent=2) + "\n", encoding="utf-8")
    return checks


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    print(json.dumps(validate(parser.parse_args().root)))
