from app.config import Settings
from app.rag import RagEngine
from app.storage import Storage


if __name__ == "__main__":
    settings = Settings.from_env()
    storage = Storage(settings.database_path)
    try:
        print(f"{RagEngine(storage, settings.knowledge_dir).reindex()} chunk diindeks")
    finally:
        storage.close()
