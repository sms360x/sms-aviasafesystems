import json
from pathlib import Path
from typing import List, Optional
from app.models.hrc_reference import HRCReference, HRCClassification

SEED_PATH = Path("data/seeds/hrc_reference_seed.json")

class HRCReferenceService:
    def __init__(self):
        data = json.loads(SEED_PATH.read_text(encoding="utf-8"))
        self._docs = {d["id"]: d for d in data["source_documents"]}
        self._items = []
        for c in data["categories"]:
            self._items.append(HRCReference(
                code=c["code"],
                classification=HRCClassification(c["classification"]),
                title=c["title"],
                source_document_id=c["source_document_id"],
                source_section=c.get("source_section"),
                jurisdiction=c.get("jurisdiction"),
            ))

    def list_all(self) -> List[HRCReference]:
        return list(self._items)

    def list_by_classification(self, cls: HRCClassification) -> List[HRCReference]:
        return [i for i in self._items if i.classification == cls]

    def list_national(self, jurisdiction: str) -> List[HRCReference]:
        return [i for i in self._items if i.classification == HRCClassification.NATIONAL_HRC and (i.jurisdiction or "").upper() == jurisdiction.upper()]

    def get(self, code: str, classification: HRCClassification, jurisdiction: Optional[str]=None) -> Optional[HRCReference]:
        for i in self._items:
            if i.code == code and i.classification == classification and (jurisdiction is None or (i.jurisdiction or "").upper()==jurisdiction.upper()):
                return i
        return None
