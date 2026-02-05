from sqlmodel import SQLModel, Session, create_engine
import sqlalchemy.dialects.postgresql
from sqlalchemy import JSON

# Monkeypatch JSONB to JSON for SQLite compatibility
sqlalchemy.dialects.postgresql.JSONB = JSON

from app.models.evaluation_run import EvaluationRun
from app.models.analysis_result import AnalysisResult


def verify_models():
    # Setup in-memory database
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        # Create EvaluationRun (Simplified)
        run = EvaluationRun(evaluation_key="test-repo:1:sha:hash:v1")
        session.add(run)
        session.commit()
        session.refresh(run)

        print(f"Created Run ID: {run.id}")

        # Create AnalysisResult
        result = AnalysisResult(
            run_id=run.id,
            node_name="test_node",
            reason_code="TEST_CODE",
            summary="Test Summary",
        )
        session.add(result)
        session.commit()
        session.refresh(result)

        print(f"Created Result ID: {result.id} linked to Run ID: {result.run_id}")

        # Verify Link from Run side
        session.refresh(run)
        assert len(run.analysis_results) == 1
        assert run.analysis_results[0].id == result.id
        print("Verification Successful: Run -> AnalysisResults link works.")

        # Verify Link from Result side
        assert result.evaluation_run.id == run.id
        print("Verification Successful: AnalysisResult -> EvaluationRun link works.")


if __name__ == "__main__":
    verify_models()
