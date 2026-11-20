from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from services.orchestrator.app.client import (
    OrchestratorClient,
    ServiceCallError,
)
from services.orchestrator.app.config import (
    AI_SERVICE_URL,
    ANALYTICS_SERVICE_URL,
    DEMOGRAPHY_SERVICE_URL,
    ENVIRONMENT_SERVICE_URL,
    HEALTH_SERVICE_URL,
    INTEGRATION_SERVICE_URL,
    METEOROLOGY_SERVICE_URL,
    REQUEST_TIMEOUT_SECONDS,
)


class OrchestratorService:
    """
    Application-level workflow orchestrator.

    Workflow:

        Health ingestion
        Demography ingestion
        Environment ingestion
        Meteorology ingestion
        Integration
        Analytics validation
        AI validation

    The workflow is sequential and fail-fast.

    No ETL pipeline is imported or executed directly.
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        client: OrchestratorClient | None = None,
    ):
        self.client = (
            client
            or OrchestratorClient(
                timeout_seconds=
                    REQUEST_TIMEOUT_SECONDS
            )
        )

    @staticmethod
    def _utc_now() -> str:
        return (
            datetime.now(timezone.utc)
            .isoformat()
        )

    async def _run_step(
        self,
        *,
        name: str,
        service: str,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
    ) -> dict:
        """
        Execute one workflow step and return
        execution metadata.
        """

        started_at = self._utc_now()

        payload = await self.client.request(
            service=service,
            method=method,
            url=url,
            params=params,
        )

        finished_at = self._utc_now()

        if name.endswith("_ingestion") or name == "one_health_integration":
            upstream_status = str(
                payload.get("status", "")
            ).upper()

            if upstream_status != "OK":
                raise ServiceCallError(
                    service=service,
                    method=method,
                    url=url,
                    status_code=502,
                    detail=(
                        "Stato applicativo non valido: "
                        f"{upstream_status or 'MISSING_STATUS'}"
                    ),
                )

        return {
            "name": name,
            "service": service,
            "status": "OK",
            "started_at": started_at,
            "finished_at": finished_at,
            "response": payload,
        }

    async def run_workflow(
        self,
        *,
        meteorology_year: int = 2023,
        start_year: int = 2021,
        end_year: int = 2023,
    ) -> dict:
        """
        Execute the complete OneHealthAI workflow.

        Domain ingestion steps are executed first.
        Integration is executed only after all source
        domains complete successfully.

        Analytics and AI are read-only downstream
        services, therefore they are validated rather
        than ingested.
        """

        workflow_id = str(
            uuid4()
        )

        workflow_started_at = (
            self._utc_now()
        )

        steps: list[dict] = []

        workflow_plan = [
            {
                "name":
                    "health_ingestion",
                "service":
                    "health-service",
                "method":
                    "POST",
                "url":
                    (
                        f"{HEALTH_SERVICE_URL}"
                        "/v1/ingestion/run"
                    ),
                "params":
                    None,
            },
            {
                "name":
                    "demography_ingestion",
                "service":
                    "demography-service",
                "method":
                    "POST",
                "url":
                    (
                        f"{DEMOGRAPHY_SERVICE_URL}"
                        "/v1/ingestion/run"
                    ),
                "params":
                    None,
            },
            {
                "name":
                    "environment_ingestion",
                "service":
                    "environment-service",
                "method":
                    "POST",
                "url":
                    (
                        f"{ENVIRONMENT_SERVICE_URL}"
                        "/v1/ingestion/run"
                    ),
                "params":
                    None,
            },
            {
                "name":
                    "meteorology_ingestion",
                "service":
                    "meteorology-service",
                "method":
                    "POST",
                "url":
                    (
                        f"{METEOROLOGY_SERVICE_URL}"
                        "/v1/ingestion/run"
                    ),
                "params": {
                    "year":
                        meteorology_year,
                },
            },
            {
                "name":
                    "one_health_integration",
                "service":
                    "integration-service",
                "method":
                    "POST",
                "url":
                    (
                        f"{INTEGRATION_SERVICE_URL}"
                        "/v1/ingestion/run"
                    ),
                "params": {
                    "start_year":
                        start_year,
                    "end_year":
                        end_year,
                },
            },
            {
                "name":
                    "analytics_validation",
                "service":
                    "analytics-service",
                "method":
                    "GET",
                "url":
                    (
                        f"{ANALYTICS_SERVICE_URL}"
                        "/v1/summary"
                    ),
                "params":
                    None,
            },
            {
                "name":
                    "ai_validation",
                "service":
                    "ai-service",
                "method":
                    "GET",
                "url":
                    (
                        f"{AI_SERVICE_URL}"
                        "/v1/model-card"
                    ),
                "params":
                    None,
            },
        ]

        for step_definition in workflow_plan:
            try:
                step_result = (
                    await self._run_step(
                        **step_definition
                    )
                )

                steps.append(
                    step_result
                )

            except ServiceCallError as exc:
                failed_at = self._utc_now()

                steps.append(
                    {
                        "name":
                            step_definition[
                                "name"
                            ],
                        "service":
                            step_definition[
                                "service"
                            ],
                        "status":
                            "FAILED",
                        "finished_at":
                            failed_at,
                        "error": {
                            "status_code":
                                exc.status_code,
                            "detail":
                                exc.detail,
                        },
                    }
                )

                return {
                    "status":
                        "FAILED",

                    "workflow_id":
                        workflow_id,

                    "orchestrator_version":
                        self.VERSION,

                    "started_at":
                        workflow_started_at,

                    "finished_at":
                        failed_at,

                    "meteorology_year":
                        meteorology_year,

                    "integration_period": {
                        "start_year":
                            start_year,
                        "end_year":
                            end_year,
                    },

                    "completed_steps":
                        sum(
                            1
                            for step
                            in steps
                            if (
                                step[
                                    "status"
                                ]
                                == "OK"
                            )
                        ),

                    "total_steps":
                        len(
                            workflow_plan
                        ),

                    "failed_step":
                        step_definition[
                            "name"
                        ],

                    "steps":
                        steps,
                }

        workflow_finished_at = (
            self._utc_now()
        )

        return {
            "status":
                "OK",

            "workflow_id":
                workflow_id,

            "orchestrator_version":
                self.VERSION,

            "started_at":
                workflow_started_at,

            "finished_at":
                workflow_finished_at,

            "meteorology_year":
                meteorology_year,

            "integration_period": {
                "start_year":
                    start_year,
                "end_year":
                    end_year,
            },

            "completed_steps":
                len(steps),

            "total_steps":
                len(
                    workflow_plan
                ),

            "failed_step":
                None,

            "steps":
                steps,
        }

    def get_workflow_plan(
        self,
    ) -> dict:
        """
        Describe the workflow without executing it.
        """

        return {
            "orchestrator_version":
                self.VERSION,

            "execution_policy":
                "SEQUENTIAL_FAIL_FAST",

            "steps": [
                {
                    "order": 1,
                    "name":
                        "health_ingestion",
                    "service":
                        "health-service",
                },
                {
                    "order": 2,
                    "name":
                        "demography_ingestion",
                    "service":
                        "demography-service",
                },
                {
                    "order": 3,
                    "name":
                        "environment_ingestion",
                    "service":
                        "environment-service",
                },
                {
                    "order": 4,
                    "name":
                        "meteorology_ingestion",
                    "service":
                        "meteorology-service",
                },
                {
                    "order": 5,
                    "name":
                        "one_health_integration",
                    "service":
                        "integration-service",
                },
                {
                    "order": 6,
                    "name":
                        "analytics_validation",
                    "service":
                        "analytics-service",
                },
                {
                    "order": 7,
                    "name":
                        "ai_validation",
                    "service":
                        "ai-service",
                },
            ],

            "principles": [
                (
                    "Services are coordinated "
                    "through HTTP APIs."
                ),
                (
                    "The orchestrator does not "
                    "execute ETL code directly."
                ),
                (
                    "Integration starts only after "
                    "all required domain ingestion "
                    "steps succeed."
                ),
                (
                    "Execution stops immediately "
                    "when a required step fails."
                ),
                (
                    "Analytics and AI are validated "
                    "as downstream read-only "
                    "services."
                ),
            ],
        }