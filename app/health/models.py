from pydantic import BaseModel


class HealthResponse(BaseModel):
    healthy: bool
    externals: dict[str, bool]
