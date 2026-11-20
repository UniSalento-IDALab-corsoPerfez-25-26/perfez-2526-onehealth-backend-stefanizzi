from fastapi import (
    APIRouter,
    Query,
)

from services.analytics.app.service import (
    AnalyticsService,
)


router = APIRouter()

analytics_service = AnalyticsService()


@router.get("/summary")
def get_summary():
    return analytics_service.get_summary()


@router.get("/kpi")
def get_kpi(
    indicator_code: str,
    year: int,
    asl: str | None = Query(
        default=None
    ),
    sex: str = Query(
        default="ALL"
    ),
):
    return analytics_service.get_kpi(
        indicator_code=indicator_code,
        year=year,
        asl=asl,
        sex=sex,
    )


@router.get("/trends")
def get_trends(
    indicator_code: str,
    asl: str,
    sex: str = Query(
        default="ALL"
    ),
):
    items = analytics_service.get_trend(
        indicator_code=indicator_code,
        asl=asl,
        sex=sex,
    )

    return {
        "items": items,
        "count": len(items),
    }


@router.get("/territories")
def get_territories(
    indicator_code: str,
    year: int,
    sex: str = Query(
        default="ALL"
    ),
):
    items = (
        analytics_service
        .get_territorial_ranking(
            indicator_code=indicator_code,
            year=year,
            sex=sex,
        )
    )

    return {
        "items": items,
        "count": len(items),
    }


@router.get("/correlations")
def get_correlations(
    indicator_code: str,
):
    return (
        analytics_service
        .get_correlations(
            indicator_code=indicator_code
        )
    )