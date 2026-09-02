from pydantic import BaseModel
from typing import List

class PreferenceUpdate(BaseModel):
    preferred_areas: List[str] = []
    preferred_categories: List[str] = []


class PreferenceResponse(BaseModel):
    preferred_areas: List[str]
    preferred_categories: List[str]

    class Config:
        from_attributes = True