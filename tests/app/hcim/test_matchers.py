from os import path
from typing import List

import pytest
from fastapi import Request
from pydantic import ValidationError
from pytest_mock import MockerFixture
from starlette.datastructures import URL

from app.hcim.matchers import HCIMResource, HCIMResourceMatch, HCIMResourceMatcher

endpoints_stub = {
    "/only/uri": HCIMResource(
        data_service="Acme",
        matches=[
            HCIMResourceMatch(
                required_params=None, resource_path="OnlyUri.json", fhir_version="3.0"
            )
        ],
    ),
    "/uri/w/single/match": HCIMResource(
        data_service="Acme",
        matches=[
            HCIMResourceMatch(
                required_params=["first=foo", "second=bar"],
                resource_path="UriWithSingleMatch.json",
                fhir_version="3.0",
            )
        ],
    ),
    "/uri/w/multiple/possible/matches": HCIMResource(
        data_service="Acme",
        matches=[
            HCIMResourceMatch(
                required_params=["required=true"],
                resource_path="FirstPossibleMatch.json",
                fhir_version="3.0",
            ),
            HCIMResourceMatch(
                required_params=["foo=bar"],
                resource_path="SecondPossibleMatch.json",
                fhir_version="3.0",
            ),
            HCIMResourceMatch(
                required_params=["this=it"],
                resource_path="ThirdPossibleMatch.json",
                fhir_version="3.0",
            ),
        ],
    ),
    "/uri/w/multiple/same/param": HCIMResource(
        data_service="Acme",
        matches=[
            HCIMResourceMatch(
                required_params=["sameparam=firstvalue", "sameparam=secondvalue"],
                resource_path="UriWithMultipleSameParam.json",
                fhir_version="3.0",
            ),
        ],
    ),
    "/uri/w/reserved/chars": HCIMResource(
        data_service="Acme",
        matches=[
            HCIMResourceMatch(
                required_params=["reserved=ab&c[#1]"],
                resource_path="UriWithReservedChars.json",
                fhir_version="3.0",
            )
        ],
    ),
}


class TestHCIMResourceMatcher:
    def setup_method(self) -> None:
        self.matcher = HCIMResourceMatcher(endpoints=endpoints_stub)

    def __create_request_stub(self, path: str, query_string: str = "") -> Request:
        url = URL(path=path)
        scope = {
            "type": "http",
            "method": "GET",
            "path": url.path,
            "query_string": query_string.encode(),
            "headers": [],
        }

        request = Request(scope)
        request._url = url

        return request

    def test_match_is_found_by_uri_alone(self) -> None:
        match = self.matcher.match_resource(self.__create_request_stub("/only/uri"))

        assert match is not None
        assert match.resource_path == "OnlyUri.json"

    def test_match_is_found_by_required_params_in_correct_order(self) -> None:
        match = self.matcher.match_resource(
            self.__create_request_stub("/uri/w/single/match", "first=foo&second=bar")
        )

        assert match is not None
        assert match.resource_path == "UriWithSingleMatch.json"

    def test_match_is_found_by_required_params_in_different_order(self) -> None:
        match = self.matcher.match_resource(
            self.__create_request_stub("/uri/w/single/match", "second=bar&first=foo")
        )

        assert match is not None
        assert match.resource_path == "UriWithSingleMatch.json"

    def test_match_is_found_by_required_params_with_extra_params(self) -> None:
        match = self.matcher.match_resource(
            self.__create_request_stub(
                "/uri/w/single/match", "second=bar&third=lucky&first=foo"
            )
        )

        assert match is not None
        assert match.resource_path == "UriWithSingleMatch.json"

    def test_match_is_found_among_multiple_possible_matches(self) -> None:
        match = self.matcher.match_resource(
            self.__create_request_stub(
                "/uri/w/multiple/possible/matches", "required=true"
            )
        )

        assert match is not None
        assert match.resource_path == "FirstPossibleMatch.json"

        match = self.matcher.match_resource(
            self.__create_request_stub("/uri/w/multiple/possible/matches", "foo=bar")
        )

        assert match is not None
        assert match.resource_path == "SecondPossibleMatch.json"

        match = self.matcher.match_resource(
            self.__create_request_stub("/uri/w/multiple/possible/matches", "this=it")
        )

        assert match is not None
        assert match.resource_path == "ThirdPossibleMatch.json"

    def test_matching_works_with_multiple_occurrence_of_same_param(self) -> None:
        match = self.matcher.match_resource(
            self.__create_request_stub(
                "/uri/w/multiple/same/param", "sameparam=firstvalue"
            )
        )

        assert match is None

        match = self.matcher.match_resource(
            self.__create_request_stub(
                "/uri/w/multiple/same/param", "sameparam=secondvalue"
            )
        )

        assert match is None

        match = self.matcher.match_resource(
            self.__create_request_stub(
                "/uri/w/multiple/same/param",
                "sameparam=firstvalue&sameparam=secondvalue",
            )
        )

        assert match is not None
        assert match.resource_path == "UriWithMultipleSameParam.json"

    def test_no_match_is_found_by_uri(self) -> None:
        match = self.matcher.match_resource(self.__create_request_stub("/non/existing"))

        assert match is None

    def test_no_match_is_found_by_required_params(self) -> None:
        match = self.matcher.match_resource(
            self.__create_request_stub("/uri/w/single/match", "first=foo")
        )

        assert match is None

    def test_request_params_are_properly_url_decoded(self) -> None:
        match = self.matcher.match_resource(
            self.__create_request_stub(
                "/uri/w/reserved/chars", "reserved=ab%26c%5B%231%5D"
            )
        )

        assert match is not None
        assert match.resource_path == "UriWithReservedChars.json"

    def test_invalid_endpoints_yaml_raises_exception(self) -> None:
        with pytest.raises(ValidationError):
            current_dir = path.abspath(path.dirname(__file__))
            HCIMResourceMatcher(
                hcim_dir=current_dir,
                endpoints_filename="endpoints_containing_invalid_endpoint.json",
            )

    def test_omitted_hcim_dir_and_endpoints_raises_exception(self) -> None:
        with pytest.raises(
            ValueError, match="hcim_dir is required if endpoints is not provided"
        ):
            HCIMResourceMatcher()


class TestHCIMResourceMatch:
    @pytest.mark.parametrize(
        "required_params, request_params, expected_result, today_date",
        [
            (
                ["date={{TODAY}}"],
                ["date=2023-10-01"],
                True,
                "2023-10-01",
            ),  # Test with today placeholder
            (
                ["date={{TODAY}}", "_include=Observation:specimen"],
                ["date=2023-10-01", "_include=Observation:specimen"],
                True,
                "2023-10-01",
            ),  # Multiple placeholders
            (
                ["date={{TODAY}}"],
                ["date=2023-10-02"],
                False,
                "2023-10-01",
            ),  # Incorrect date
            (
                ["date=ge{{TODAY}}", "_include=Observation:specimen"],
                ["date=ge2023-10-01", "_include=Observation:related-target"],
                False,
                "2023-10-01",
            ),  # Correct date but incorrect _include value
        ],
    )
    def test_match_today_date_with_dynamic_placeholder(
        self,
        mocker: MockerFixture,
        required_params: List[str],
        request_params: List[str],
        expected_result: bool,
        today_date: str,
    ) -> None:
        mocker.patch("app.hcim.matchers.datetime.datetime")
        mock_datetime = mocker.patch("app.hcim.matchers.datetime.datetime.now")
        mock_datetime.return_value.strftime.return_value = today_date

        resource_match = HCIMResourceMatch(
            required_params=required_params,
            resource_path="101/funky/resource",
            fhir_version="3.0",
        )

        assert resource_match.match(request_params) is expected_result
