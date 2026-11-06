from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class HRCClassification(str, Enum):
    GLOBAL_HRC = "GLOBAL_HRC"
    GLOBAL_OTHER_RISK = "GLOBAL_OTHER_RISK"
    NATIONAL_HRC = "NATIONAL_HRC"

class HRCReference(BaseModel):
    code: str
    classification: HRCClassification
    title: str
    source_document_id: str
    source_section: Optional[str] = None
    jurisdiction: Optional[str] = None
    version: int = 1
    approval_status: str = "published"
