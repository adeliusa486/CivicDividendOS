# Security and responsible use

## Reporting

This is research software with no network surface, no authentication and no
persistent service. If you find a vulnerability in the code — for example
unsafe deserialisation in the config loader — please open a private security
advisory rather than a public issue.

## What this software is not

- It is **not** a tax filing, assessment or compliance system.
- Its outputs are **not** legal, tax, financial or investment advice.
- Simulated rates are **not** real tax rates and must not be presented as such.
- The Deployment Nexus is a research construct, not a claim about any
  jurisdiction's law.

## Data protection

The framework as specified assumes task-level metering of production episodes.
Where episodes are attributable to identifiable workers this is personal data,
and the framework does **not** include the disclosure limits such metering
would require. Anyone implementing the measurement layer against real workplace
data needs a lawful basis, a data-protection impact assessment and minimisation
controls that this repository does not provide.

## No secrets

This repository contains no credentials, keys or tokens, and none should ever
be committed. `.gitignore` excludes `.env` and local environment files.

## Licensed data

No external data is redistributed here. Several intended calibration sources
prohibit redistribution; `configs/calibration.yaml` records their status.
Do not commit licensed series into this repository.
