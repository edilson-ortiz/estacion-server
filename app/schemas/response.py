from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel

T = TypeVar("T")

class ResponseDTO(BaseModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None
