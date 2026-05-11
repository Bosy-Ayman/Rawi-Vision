from pydantic import BaseModel

class PlansBase(BaseModel):
    name: str
    tier: str
    description: str
    annual_pricing: int
    monthly_pricing: int

class PlansCreate(PlansBase):
    pass

class PlansUpdate(BaseModel):
    name: str | None = None
    tier: str | None = None
    description: str | None = None
    annual_pricing: int | None = None
    monthly_pricing: int | None = None

class PlansResponse(PlansBase):
    pass
