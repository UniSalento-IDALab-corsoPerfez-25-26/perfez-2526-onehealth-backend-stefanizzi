from fastapi import APIRouter
from services.ai.app.dss_repository import DSSRepository
from services.analytics.app.service import AnalyticsService
from services.ai.app.scenarios import compare_scenarios, get_options

from services.ai.app.service import (
    AIService,
)


router = APIRouter()

ai_service = AIService(AnalyticsService(DSSRepository()))


@router.get("/ranking")
def get_ranking(
    indicator_code: str,
    year: int,
):
    return ai_service.get_ranking(
        indicator_code=indicator_code,
        year=year,
    )


@router.get("/priority")
def get_priority(
    indicator_code: str,
    year: int,
    asl: str,
):
    return ai_service.get_priority(
        indicator_code=indicator_code,
        year=year,
        asl=asl,
    )


@router.get("/explain")
def explain_priority(
    indicator_code: str,
    year: int,
    asl: str,
):
    return ai_service.explain_priority(
        indicator_code=indicator_code,
        year=year,
        asl=asl,
    )


@router.get("/model-card")
def get_model_card():
    return ai_service.get_model_card()

@router.get("/dss/options")
def dss_options():
    return get_options(ai_service.analytics_service.repository)


@router.get("/dss/scenarios")
def dss_scenarios(indicator_code: str, year: int):
    return compare_scenarios(ai_service.analytics_service.repository, indicator_code, year)
