# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0](https://github.com/acabelloj/gh-inspector/compare/gh-inspector-v0.0.1...gh-inspector-v0.1.0) (2026-03-05)


### Features

* add CI/CD pipeline, tests, Makefile, docs, and bug fixes ([#2](https://github.com/acabelloj/gh-inspector/issues/2)) ([f7a3eb0](https://github.com/acabelloj/gh-inspector/commit/f7a3eb0822d5ef8107df965c5247debffea6b260))

## [Unreleased]

### Added
- Initial project setup
- `find-python-library` command to analyze library usage across GitHub organizations
- Support for requirements.txt files
- Rich console output with formatted tables
- Progress bars for repository processing
- Concurrent processing with ThreadPoolExecutor
- Multiple output formats (default, only_repo)
- Source filtering (default, dev, all)
- Shell completion support for Bash, Zsh, and Fish
- Documentation (README, LICENSE, CONTRIBUTING, SECURITY, CHANGELOG)
- Development tools configuration (Ruff, pre-commit)

[Unreleased]: https://github.com/acabelloj/gh-inspector/compare/...HEAD
