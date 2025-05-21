import os
from typing import List

from fhir.models import Resource


class ResourceScanner:
    INDEX_FILE_NAME = "Index.json"
    ZIB_PREFIX = "zib-"
    JSON_EXTENSION = ".json"
    FHIR_URI_PREFIX = "/fhir/"

    def __init__(self, resources_dir: str) -> None:
        self.resources_dir = resources_dir

    def scan(self) -> List[Resource]:
        resources = []

        for resource in sorted(os.listdir(self.resources_dir)):
            endpoints = self._list_endpoints(resource)

            if not endpoints:
                continue

            resources.append(Resource(name=resource, endpoints=endpoints))

        return resources

    def _list_endpoints(self, resource: str) -> List[str]:
        endpoints = []

        resource_dir = os.path.join(self.resources_dir, resource)
        index_file = os.path.join(resource_dir, self.INDEX_FILE_NAME)

        if os.path.exists(index_file):
            endpoints.append(self.FHIR_URI_PREFIX + resource)

        usecases = [
            filename.split(".")[0]
            for filename in os.listdir(resource_dir)
            if filename.endswith(self.JSON_EXTENSION)
            and filename != self.INDEX_FILE_NAME
            and not filename.startswith(self.ZIB_PREFIX)
        ]

        endpoints.extend(
            f"{self.FHIR_URI_PREFIX}{resource}/{file_name}" for file_name in usecases
        )
        endpoints.sort()

        return endpoints
