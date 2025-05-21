from typing import List
from pydantic import BaseModel

class Resource(BaseModel):
    name: str
    endpoints: List[str]
