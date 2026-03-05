# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.1](https://github.com/acabelloj/gh-inspector/compare/gh-inspector-v0.2.0...gh-inspector-v0.2.1) (2026-03-05)


### Bug Fixes

* trigger PyPI publish from release-please workflow ([#14](https://github.com/acabelloj/gh-inspector/issues/14)) ([e3d1674](https://github.com/acabelloj/gh-inspector/commit/e3d1674a821909146297851ca6f317dec028cc2f))

## [0.2.0](https://github.com/acabelloj/gh-inspector/compare/gh-inspector-v0.1.0...gh-inspector-v0.2.0) (2026-03-05)


### Features

* add --version flag to CLI ([#10](https://github.com/acabelloj/gh-inspector/issues/10)) ([e689cc3](https://github.com/acabelloj/gh-inspector/commit/e689cc3068cc433685ba675131361e489ba75716))
* modularize find-python-library with multi-format parser support ([#13](https://github.com/acabelloj/gh-inspector/issues/13)) ([8baf359](https://github.com/acabelloj/gh-inspector/commit/8baf35930da64c090af9639387e26a61fe022ec5))

## [0.1.0](https://github.com/acabelloj/gh-inspector/compare/gh-inspector-v0.0.1...gh-inspector-v0.1.0) (2026-03-05)


### Features

* add CI/CD pipeline, tests, Makefile, docs, and bug fixes ([#2](https://github.com/acabelloj/gh-inspector/issues/2)) ([f7a3eb0](https://github.com/acabelloj/gh-inspector/commit/f7a3eb0822d5ef8107df965c5247debffea6b260))


### Bug Fixes

* add Python version classifiers and pin to 3.14 ([#6](https://github.com/acabelloj/gh-inspector/issues/6)) ([9428b37](https://github.com/acabelloj/gh-inspector/commit/9428b37030ecc2d0ab4e49e4512e84442bf25b22))

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
