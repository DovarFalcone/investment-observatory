# Security policy

## Supported versions

Only the latest commit on `master` is supported.

## Reporting a vulnerability

Please do not open a public issue for a security vulnerability. Contact the repository owner through the private contact options on the [DovarFalcone GitHub profile](https://github.com/DovarFalcone), including:

- a concise description of the issue;
- the affected commit, route, workflow, or configuration;
- reproducible steps or a minimal proof of concept;
- any suggested mitigation.

Do not include real credentials, private keys, brokerage exports, or personal holdings data in an issue, pull request, or report.

This project is designed for self-hosting on a trusted LAN or behind an authenticated reverse proxy. It is not intended to be exposed directly to the public internet without additional access control and transport security.

## Public-data caution

The application uses replaceable external market and news adapters. Provider responses and terms can change. Do not add provider API keys or private account credentials to the repository; keep them in the deployment environment or a secret manager.

## Repository protections

The repository uses protected `master`, required CI checks, Dependabot, secret scanning, and push protection where supported by GitHub.

## Personal data

Do not commit database files, PostgreSQL dumps, backups, `.env` files, transaction exports, or holdings data. These paths are ignored locally, but contributors must still verify staged files before pushing.
