# DVA Mock

## Disclaimer

This project and all associated code serve solely as documentation
and demonstration purposes to illustrate potential system
communication patterns and architectures.

This codebase:

- Is NOT intended for production use
- Does NOT represent a final specification
- Should NOT be considered feature-complete or secure
- May contain errors, omissions, or oversimplified implementations
- Has NOT been tested or hardened for real-world scenarios

The code examples are only meant to help understand concepts and demonstrate possibilities.

By using or referencing this code, you acknowledge that you do so at your own
risk and that the authors assume no liability for any consequences of its use.

## Configuration

The application utilizes a configuration file named `app.conf` to manage its
settings. The `app.conf.example` serves as a template with sane defaults. Copy
this template file to a new `app.conf` file. You can optionally choose to alter
some default configurations to meet your requirements.

## Usage

The DVA Mock contains a set of static ZIB (HCIM) Bundle and Resource data. This
data is exposed via several fixed endpoints as specified by MedMij. For example,
the "BgZ" dataservice implements to following specification:
[MedMij FHIR Implementation Guide: BgZ 3.1.26](https://informatiestandaarden.nictiz.nl/wiki/MedMij:V2020.01/FHIR_BGZ_2017).

To inspect the full list of endpoints (and in some cases their required URL
parameters), refer to [endpoints.json](./app/hcim/endpoints.json).

### Dataservices

| Dataservice ID | Dataservice name                                       | Implemented in DVA Mock (Y/N) |
| -------------- | ------------------------------------------------------ | ----------------------------- |
| 65             | Verzamelen Integrale Zwangerschapskaart 1.0            | N                             |
| 63             | Verzamelen Vaccinaties 1.0                             | N                             |
| 61             | Verzamelen Basisgegevens Langdurige Zorg 3.0           | N                             |
| 59             | Verzamelen Verwijzing naar vragenlijst 2.0             | N                             |
| 58             | Verzamelen Medicatiegerelateerde Overgevoeligheden 2.A | N                             |
| 54             | Verzamelen Overgevoeligheden 2.0                       | N                             |
| 52             | Verzamelen Meetwaarden vitale functies 2.0             | N                             |
| 51             | Verzamelen Documenten 3.0                              | Y                             |
| 50             | Verzamelen Basisgegevens GGZ 2.0                       | N                             |
| 49             | Verzamelen Huisartsgegevens 2.0                        | Y                             |
| 48             | Verzamelen Basisgegevens zorg 3.0                      | Y                             |
| 46             | Verzamelen Laboratoriumresultaten 2.0                  | N                             |
| 35             | Verzamelen Medicatiegegevens 9.A                       | N                             |
| 31             | Verzamelen Medicatiegegevens 9.0                       | N                             |

### Requesting resources

The endpoint mapping in [endpoints.json](./app/hcim/endpoints.json) is indexed
by the path, e.g. "/48/fhir/Patient". This is the path directly following the
DVA Mock domain. If the `required_params` defines specific URL parameters, these
must be included in the request. If the request is matched to an item in the
endpoint mapping, the static HCIM resource is retrieved from the location
specified in the `resource_path` property.

### Example

Request:
`GET https://dva-mock-domain/48/fhir/Observation?code=http://snomed.info/sct|228366006`
Response: [7-2-DrugUse.json](./fhir/resources/BGZ/7-2-DrugUse.json)

## Contributing

If you encounter any issues or have suggestions for improvements, please feel free to open an issue or submit a pull
request on the GitHub repository of this package.

## License

This repository follows the [REUSE Specification v3.2](https://reuse.software/spec-3.2/). The code is available under the
EUPL-1.2 license, but the fonts and images are not. Please see [LICENSES/](./LICENSES), [REUSE.toml](./REUSE.toml) and
the individual `*.license` files (if any) for copyright and license information.
