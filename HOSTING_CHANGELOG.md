# Hosting Changelog

- ## NEXT FUTURE RELEASE

- ### [0.12.0]

  No changes required

- ### [0.11.0]

  No changes required
  
- ### [0.10.0] 2025-06-27

  No changes required

- ### [0.9.0] 2025-03-10

  No changes required

- ### [0.8.0] 2025-01-17

  No changes required

- ### [0.7.0] 2024-12-13

  #### Added

  - 'oauth' section
    - mock_oauth_servers
            boolean - enables mocked OAuth endpoints

  - `telemetry` section
    - enabled
      - boolean - determines whether to collect telemetry data.
    - service_name
      - string - The name to use for this service to send telemetry data to the gRPC server.
    - collector_grpc_url
      - string - The URL of the gRPC server that will receive the telemetry data.
      - example: <http://jaeger:4317>

- ### [0.6.0] 2024-10-04

  No changes required

- ### [0.5.0] 2024-09-18

  No changes required

- ### [0.4.1] 2024-07-25

  No changes required

- ### [0.4.0] 2024-07-23

  No changes required

- ### [0.3.1] - 2024-06-20

  No changes required

- ### [0.3.0] - 2024-06-19

  No changes required

- ### [0.2.1] - 2024-06-06

  No changes required

- ### [0.2.0] - 2024-06-05

  No changes required

- ### [0.1.0] - 2024-05-27

  No changes required

- ### [0.0.3]

  #### Change

    [app.conf](app.conf)
  - `default.base_url`: make sure the URL starts with: "https://"

    [entrypoint]
  - Add the following arguments to the Uvicorn command to configure a secured mTLS connection with the Proxy application:
    - `--ssl-keyfile`=/example/server.key
    - `--ssl-certfile`=/example/server.crt
    - `--ssl-ca-certs`=/example/ca.crt
    - `--ssl-cert-reqs=2`
