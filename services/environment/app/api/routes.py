from fastapi import APIRouter


router = APIRouter()


@router.get("/stations")
def get_stations() -> dict:
    return {
        "items": [],
        "count": 0,
    }


@router.get("/measurements")
def get_measurements() -> dict:
    return {
        "items": [],
        "count": 0,
    }


@router.get("/exposure")
def get_exposure() -> dict:
    return {
        "items": [],
        "count": 0,
    }


@router.get("/quality")
def get_quality() -> dict:
    return {
        "status": "NOT_IMPLEMENTED",
    }


@router.post("/ingestion/run")
def run_ingestion() -> dict:
    return {
        "status": "NOT_IMPLEMENTED",
    }