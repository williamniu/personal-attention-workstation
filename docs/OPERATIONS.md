# Operations

## Local controls

```bash
./bin/jobintel start
./bin/jobintel stop
./bin/jobintel pause
./bin/jobintel resume
./bin/jobintel status
./bin/jobintel health
./bin/jobintel doctor
```

`start` launches API and dashboard as independent background processes. `pause` leaves read-only
services available while recording that scheduled collection must not start. Runtime state and logs
live under ignored `data/` paths.

Docker Compose is an alternative once Docker is installed. It binds all exposed ports to localhost.

