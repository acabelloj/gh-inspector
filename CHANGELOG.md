# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.2](https://github.com/acabelloj/gh-inspector/compare/gh-inspector-v0.3.1...gh-inspector-v0.3.2) (2026-03-07)


### Bug Fixes

* **ci:** add ghcr.io to publish job allowlist ([#38](https://github.com/acabelloj/gh-inspector/issues/38)) ([fa7c486](https://github.com/acabelloj/gh-inspector/commit/fa7c486803546917c438ee39679de47c3989a1bf))

## [0.3.1](https://github.com/acabelloj/gh-inspector/compare/gh-inspector-v0.3.0...gh-inspector-v0.3.1) (2026-03-07)


### Bug Fixes

* **ci:** add sigstore endpoints to build allowlist and uv.lock pre-commit hook ([#35](https://github.com/acabelloj/gh-inspector/issues/35)) ([7432d2c](https://github.com/acabelloj/gh-inspector/commit/7432d2cc35e3ba06fabcaf9fb3c25d4f40dd3c6e))

## [0.3.0](https://github.com/acabelloj/gh-inspector/compare/gh-inspector-v0.2.2...gh-inspector-v0.3.0) (2026-03-07)


### Features

* add --version flag to CLI ([#10](https://github.com/acabelloj/gh-inspector/issues/10)) ([a7df24e](https://github.com/acabelloj/gh-inspector/commit/a7df24e1f9f992a7069d8d42d5b001d097de020f))
* add CI/CD pipeline, tests, Makefile, docs, and bug fixes ([#2](https://github.com/acabelloj/gh-inspector/issues/2)) ([70cb053](https://github.com/acabelloj/gh-inspector/commit/70cb0539ebc9940b4b8638b3752e46da30c60ab0))
* add find-codeowners command ([#28](https://github.com/acabelloj/gh-inspector/issues/28)) ([5221389](https://github.com/acabelloj/gh-inspector/commit/5221389f05a8250e305f14e7811243676320405c))
* add find-licenses command ([#29](https://github.com/acabelloj/gh-inspector/issues/29)) ([d6babfe](https://github.com/acabelloj/gh-inspector/commit/d6babfe24a8349362ae5b4b509342c35e495f56c))
* modularize find-python-library with multi-format parser support ([#13](https://github.com/acabelloj/gh-inspector/issues/13)) ([f7335ad](https://github.com/acabelloj/gh-inspector/commit/f7335ad160adff525cc52729a825fd66116ff20e))


### Bug Fixes

* add Python version classifiers and pin to 3.14 ([#6](https://github.com/acabelloj/gh-inspector/issues/6)) ([a896c51](https://github.com/acabelloj/gh-inspector/commit/a896c5150c1de9ef10e86a37b34a573628e29bae))
* **ci:** add release-assets.githubusercontent.com to secret-scan allowlist ([#34](https://github.com/acabelloj/gh-inspector/issues/34)) ([6611a76](https://github.com/acabelloj/gh-inspector/commit/6611a7670c6e73e32be0ad111bfd7ef964e94123))
* handle timeout=0 correctly in GitHubClient ([#24](https://github.com/acabelloj/gh-inspector/issues/24)) ([8dd0699](https://github.com/acabelloj/gh-inspector/commit/8dd0699681e1da064e1d38a242868b3fda2a0c86))
* trigger PyPI publish from release-please workflow ([#14](https://github.com/acabelloj/gh-inspector/issues/14)) ([9049126](https://github.com/acabelloj/gh-inspector/commit/904912634601aa6d3d62b3e35e6df01b2b86f249))
* update e2e expected Python version to 3.14 ([#8](https://github.com/acabelloj/gh-inspector/issues/8)) ([0db1b6e](https://github.com/acabelloj/gh-inspector/commit/0db1b6ed2e684ec5a19cf358bb35a6e4b723f844))
* use commit SHA for pypa/gh-action-pypi-publish ([#9](https://github.com/acabelloj/gh-inspector/issues/9)) ([0dc20ca](https://github.com/acabelloj/gh-inspector/commit/0dc20ca98b00f37c7bd268435497e9523692a8d9))


### Documentation

* improve CLI help text with examples and accepted values ([#26](https://github.com/acabelloj/gh-inspector/issues/26)) ([f87610b](https://github.com/acabelloj/gh-inspector/commit/f87610bead9f8181933e733b87dcefa72c68d553))

## [0.2.2](https://github.com/acabelloj/gh-inspector/compare/gh-inspector-v0.2.1...gh-inspector-v0.2.2) (2026-03-05)


### Bug Fixes

* handle timeout=0 correctly in GitHubClient ([#24](https://github.com/acabelloj/gh-inspector/issues/24)) ([4fdc622](https://github.com/acabelloj/gh-inspector/commit/4fdc6221caf0b6a08c8faca417587e83b1d9b41e))

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
