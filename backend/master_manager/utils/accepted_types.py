from enum import Enum
from pydantic import BaseModel
from typing import Type, TypeVar, Optional

class ValidRanges(str, Enum):
    MINUTE = "1H"
    HOUR = "1W" 
    DAY = "1M"
    WEEK = "1Y"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None
    
class ValidViews(str, Enum):
    YES = "yes"
    NO = "no"

    @classmethod
    def _missing_(cls, value):
        if isinstance(value, str):
            for member in cls:
                if member.value.lower() == value.lower():
                    return member
        return None

T = TypeVar("T", bound=Enum)

def safe_enum_lookup(enum_cls: Type[T], value: str) -> Optional[T]:
    try:
        return enum_cls(value)
    except ValueError:
        return None