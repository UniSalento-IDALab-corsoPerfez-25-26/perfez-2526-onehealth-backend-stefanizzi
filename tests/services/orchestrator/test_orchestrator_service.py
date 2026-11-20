import asyncio

from services.orchestrator.app.client import (
    ServiceCallError,
)
from services.orchestrator.app.service import (
    OrchestratorService,
)


class FakeSuccessfulClient:
    def __init__(self):
        self.calls = []

    async def request(
        self,
        *,
        service,
        method,
        url,
        params=None,
    ):
        self.calls.append(
            {
                "service": service,
                "method": method,
                "url": url,
                "params": params,
            }
        )

        return {
            "status": "OK",
            "service": service,
        }


class FakeFailingClient:
    def __init__(
        self,
        fail_service,
    ):
        self.fail_service = fail_service
        self.calls = []

    async def request(
        self,
        *,
        service,
        method,
        url,
        params=None,
    ):
        self.calls.append(service)

        if service == self.fail_service:
            raise ServiceCallError(
                service=service,
                method=method,
                url=url,
                status_code=500,
                detail="Simulated failure",
            )

        return {
            "status": "OK",
            "service": service,
        }


def test_complete_workflow():
    client = FakeSuccessfulClient()

    service = OrchestratorService(
        client=client
    )

    result = asyncio.run(
        service.run_workflow(
            meteorology_year=2023,
            start_year=2021,
            end_year=2023,
        )
    )

    assert result["status"] == "OK"
    assert result["completed_steps"] == 7
    assert result["total_steps"] == 7
    assert result["failed_step"] is None

    assert len(result["steps"]) == 7


def test_workflow_execution_order():
    client = FakeSuccessfulClient()

    service = OrchestratorService(
        client=client
    )

    asyncio.run(
        service.run_workflow(
            meteorology_year=2023,
            start_year=2021,
            end_year=2023,
        )
    )

    services = [
        call["service"]
        for call in client.calls
    ]

    assert services == [
        "health-service",
        "demography-service",
        "environment-service",
        "meteorology-service",
        "integration-service",
        "analytics-service",
        "ai-service",
    ]


def test_fail_fast_on_health():
    client = FakeFailingClient(
        fail_service="health-service"
    )

    service = OrchestratorService(
        client=client
    )

    result = asyncio.run(
        service.run_workflow()
    )

    assert result["status"] == "FAILED"

    assert result["completed_steps"] == 0

    assert (
        result["failed_step"]
        == "health_ingestion"
    )

    assert client.calls == [
        "health-service"
    ]


def test_fail_fast_on_integration():
    client = FakeFailingClient(
        fail_service="integration-service"
    )

    service = OrchestratorService(
        client=client
    )

    result = asyncio.run(
        service.run_workflow()
    )

    assert result["status"] == "FAILED"

    assert (
        result["failed_step"]
        == "one_health_integration"
    )

    assert result["completed_steps"] == 4

    assert client.calls == [
        "health-service",
        "demography-service",
        "environment-service",
        "meteorology-service",
        "integration-service",
    ]


def test_analytics_runs_after_integration():
    client = FakeSuccessfulClient()

    service = OrchestratorService(
        client=client
    )

    asyncio.run(
        service.run_workflow()
    )

    services = [
        call["service"]
        for call in client.calls
    ]

    assert (
        services.index(
            "analytics-service"
        )
        >
        services.index(
            "integration-service"
        )
    )


def test_ai_runs_after_analytics():
    client = FakeSuccessfulClient()

    service = OrchestratorService(
        client=client
    )

    asyncio.run(
        service.run_workflow()
    )

    services = [
        call["service"]
        for call in client.calls
    ]

    assert (
        services.index(
            "ai-service"
        )
        >
        services.index(
            "analytics-service"
        )
    )


def test_workflow_plan():
    service = OrchestratorService()

    plan = service.get_workflow_plan()

    assert (
        plan["execution_policy"]
        == "SEQUENTIAL_FAIL_FAST"
    )

    assert len(plan["steps"]) == 7

    assert [
        step["name"]
        for step in plan["steps"]
    ] == [
        "health_ingestion",
        "demography_ingestion",
        "environment_ingestion",
        "meteorology_ingestion",
        "one_health_integration",
        "analytics_validation",
        "ai_validation",
    ]