from pathlib import Path

from app.core.config import settings


class DatasetRegistry:
    def __init__(self) -> None:
        self.demo_dataset_dir = Path(settings.demo_dataset_dir)
        self.app_dataset_dir = Path(settings.app_dataset_dir)
        self.demo_model_dir = Path(settings.demo_model_dir)
        self.app_model_dir = Path(settings.app_model_dir)

        self._ensure_directories()

    def _ensure_directories(self) -> None:
        self.demo_dataset_dir.mkdir(parents=True, exist_ok=True)
        self.app_dataset_dir.mkdir(parents=True, exist_ok=True)
        self.demo_model_dir.mkdir(parents=True, exist_ok=True)
        self.app_model_dir.mkdir(parents=True, exist_ok=True)

    def get_dataset_dir(self, mode: str) -> Path:
        normalized_mode = mode.strip().lower()
        if normalized_mode == "demo":
            return self.demo_dataset_dir
        return self.app_dataset_dir

    def get_model_dir(self, mode: str) -> Path:
        normalized_mode = mode.strip().lower()
        if normalized_mode == "demo":
            return self.demo_model_dir
        return self.app_model_dir

    def list_dataset_files(self, mode: str) -> list[str]:
        dataset_dir = self.get_dataset_dir(mode)
        return sorted(
            [item.name for item in dataset_dir.iterdir() if item.is_file()]
        )

    def list_model_files(self, mode: str) -> list[str]:
        model_dir = self.get_model_dir(mode)
        return sorted(
            [item.name for item in model_dir.iterdir() if item.is_file()]
        )

    def get_dataset_summary(self, mode: str) -> dict:
        dataset_dir = self.get_dataset_dir(mode)
        files = self.list_dataset_files(mode)

        return {
            "mode": mode,
            "dataset_dir": str(dataset_dir).replace("\\", "/"),
            "file_count": len(files),
            "files": files,
        }

    def get_model_summary(self, mode: str) -> dict:
        model_dir = self.get_model_dir(mode)
        files = self.list_model_files(mode)

        return {
            "mode": mode,
            "model_dir": str(model_dir).replace("\\", "/"),
            "file_count": len(files),
            "files": files,
        }