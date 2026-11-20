from pydantic import BaseModel


class IndicatorListResponse(
    BaseModel
):
    items: list[str]
    count: int


class HealthCasesResponse(
    BaseModel
):
    items: list[dict]
    count: int