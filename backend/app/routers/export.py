import csv
import io
import json
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import ContentItem, Document

router = APIRouter(prefix="/export", tags=["export"])

FORMATS = ("json", "csv", "qti", "anki")


def _items(db, document_id):
    doc = db.query(Document).get(document_id)
    if not doc:
        raise HTTPException(404, "Document not found")
    return doc, db.query(ContentItem).filter(ContentItem.document_id == document_id).all()


@router.get("/{document_id}")
def export(document_id: int, format: str = Query("json"), db: Session = Depends(get_db)):
    doc, items = _items(db, document_id)
    if format == "json":
        data = [{"id": it.id, "type": it.item_type, "status": it.status, "bloom_level": it.bloom_level,
                 "quality_score": it.quality_score, "payload": it.payload_obj()} for it in items]
        return {"document": doc.title, "items": data}
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["id", "type", "status", "bloom_level", "quality_score", "payload_json"])
        for it in items:
            w.writerow([it.id, it.item_type, it.status, it.bloom_level, it.quality_score, json.dumps(it.payload_obj())])
        return Response(content=buf.getvalue(), media_type="text/csv",
                       headers={"Content-Disposition": f"attachment; filename=export_{document_id}.csv"})
    if format == "anki":
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["Front", "Back", "Tags"])
        for it in items:
            if it.item_type != "flashcard":
                continue
            p = it.payload_obj()
            w.writerow([p.get("front", ""), p.get("back", ""), " ".join(p.get("tags", []))])
        return Response(content=buf.getvalue(), media_type="text/csv",
                       headers={"Content-Disposition": f"attachment; filename=anki_{document_id}.csv"})
    if format == "qti":
        # Minimal QTI 2.1 XML for MCQs
        lines = ['<?xml version="1.0" encoding="UTF-8"?>',
                 '<assessmentTest xmlns="http://www.imsglobal.org/xsd/imsqti_v2p1" identifier="test">']
        for it in items:
            if it.item_type != "mcq":
                continue
            p = it.payload_obj()
            lines.append(f'  <assessmentItem identifier="item_{it.id}" title="MCQ">')
            lines.append(f'    <itemBody><p>{_escape(p.get("stem",""))}</p>')
            lines.append("      <choiceInteraction responseIdentifier=\"RESPONSE\" shuffle=\"true\" maxChoices=\"1\">")
            lines.append("        <simpleChoice identifier=\"A\">" + _escape(p["options"][0]["text"]) + "</simpleChoice>")
            # simplify: include all options
            for idx, o in enumerate(p.get("options", [])):
                ident = chr(ord("A") + idx)
                lines.append(f"        <simpleChoice identifier=\"{ident}\">{_escape(o['text'])}</simpleChoice>")
            lines.append("      </choiceInteraction></itemBody>")
            lines.append("  </assessmentItem>")
        lines.append("</assessmentTest>")
        xml = "\n".join(lines)
        return Response(content=xml, media_type="application/xml",
                       headers={"Content-Disposition": f"attachment; filename=qti_{document_id}.xml"})
    raise HTTPException(400, f"Unknown format. Use one of {FORMATS}")


def _escape(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")