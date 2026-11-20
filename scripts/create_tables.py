from app.core.database import Base, engine
import app.models  # noqa: F401


def main() -> None:
    Base.metadata.create_all(engine)
    print("Tabelle create correttamente.")


if __name__ == "__main__":
    main()