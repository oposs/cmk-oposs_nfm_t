# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### New

### Changed

### Fixed
- nameing inconsistancy

## 1.0.6 - 2025-11-19
### Fixed
- Port field now uses Integer type for compatibility with Check MK 2.3 NetworkPort validator

## 1.0.5 - 2025-11-19
### Changed
- allow install on 2.3

## 1.0.4 - 2025-11-18
### Fixed
- make ssl cert validation config look nicer

## 1.0.3 - 2025-11-18

## 1.0.2 - 2025-11-18
### New
- add option to disable cert validation

### Fixed
- use host address not ip address

## 1.0.1 - 2025-11-18
### Fixed
- Password handling

## 1.0.0 - 2025-11-17
### New
- Added `graphing/translations.py` for seamless metric migration
- Added `__init__.py` package marker
- Added type-safe parameter validation via Pydantic

### Changed
- **BREAKING**: Complete migration to Checkmk 2.4+ architecture
- Migrated plugin structure to `cmk_addons/plugins/oposs_nfm_t/` (unified location)
- Upgraded check plugin from v1 API to v2 API (`cmk.agent_based.v2`)
- Upgraded ruleset from old WATO API to `cmk.rulesets.v1`
- Created new `server_side_calls` component with type-safe Pydantic models
- Changed section name from `nfm_t` to `oposs_nfm_t` for consistency
- Renamed metrics with proper prefixes (`oposs_nfm_t_*`) to prevent conflicts
- Added metric translations to preserve historical RRD data during renaming
- Special agent now in `libexec/agent_oposs_nfm_t` (executable, no .py extension)
- Removed all old plugin files from legacy locations

### Fixed
- Improved password handling with modern password store integration
- Better alignment with Checkmk 2.4 naming conventions


