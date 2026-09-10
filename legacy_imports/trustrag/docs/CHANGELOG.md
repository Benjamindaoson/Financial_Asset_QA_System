# Changelog

All notable changes to this project will be documented in this file.

## [1.0.0] - 2025-12-23
### Added
- **Productization**: Added `init_artifacts.py` for automated environment setup.
- **Data**: Added `demo_data/` with Nvidia FY2023 mock data and gold standards.
- **Engineering Guarantees**: Defined deterministic behavior and cognitive isolation in `docs/ENGINEERING_GUARANTEES.md`.
- **System Protection**: Implemented mandatory refusals for out-of-scope queries.
- **Baseline**: Established performance and behavior baseline in `baseline.json`.
- **CI/CD**: Added GitHub Actions workflow for production regression testing.

### Fixed
- **Architecture**: Unified system entry in `trust_rag/system.py`.
- **Imports**: Fixed all relative and absolute import paths after reorganization.

### Changed
- **Status**: System is now FEATURE FROZEN and VALIDATION READY.

