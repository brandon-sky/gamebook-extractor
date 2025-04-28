# Dependencies
import re

from pydantic import BaseModel, field_validator


class GameEvent(BaseModel):
    possession: str
    downanddistance: str
    yardline: str
    details: str

    @field_validator("possession")
    def validate_possession(cls, v):
        if not re.match(r"^[A-Z]{2}$", v):
            raise ValueError("Possession must be two uppercase letters")
        return v

    @field_validator("downanddistance")
    def validate_down_and_distance(cls, v):
        if v and not re.match(r"^\d+&\d+$", v):
            raise ValueError('Down and distance must be in the format "X&Y"')
        return v

    @field_validator("yardline")
    def validate_yardline(cls, v):
        if v and not re.match(r"^@ [A-Z]+\d+$", v):
            raise ValueError(
                'Yardline must start with "@" followed by a team and number'
            )
        return v

    def dump_model(self):
        return {
            "Index": self.possession,
            "Down&Distance": self.downanddistance,
            "YardLine": self.yardline,
            "Details": self.details,
        }
