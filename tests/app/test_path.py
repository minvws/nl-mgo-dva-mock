import os

from app.path import project_root, resource_dir


def test_project_root() -> None:
    assert os.path.isdir(project_root())


def test_resource_dir() -> None:
    assert os.path.isdir(resource_dir())
    assert resource_dir("subfolder").endswith("/resources/subfolder")
    assert resource_dir("file.json").endswith("/resources/file.json")
    assert resource_dir("subfolder", "file.json").endswith(
        "/resources/subfolder/file.json"
    )
