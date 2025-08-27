from typing import Generic, TypeVar, List, Optional
from pydantic import BaseModel
from pydantic.generics import GenericModel

T = TypeVar("T")

class ResponseDTO(GenericModel, Generic[T]):
    success: bool
    message: str
    data: Optional[T] = None
