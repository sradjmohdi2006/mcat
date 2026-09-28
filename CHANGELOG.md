# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Unified Search System** (`Ctrl+Shift+F`): Search across 4 sources simultaneously:
  - In-Memory segments (currently loaded file)
  - TM Sources (translation memory source segments)
  - TM Targets (translation memory target segments)
  - Glossary (terminology database with descriptions)
- **Fuzzy Matching**: RapidFuzz algorithms (ratio, token_sort_ratio, partial_ratio)
- **Semantic Search**: Vector embeddings via fastembed + sqlite-vec
- **Search Dialog**: Tabbed results, filters, language filtering, field selection
- **Glossary Search**: Search terms, translations, and descriptions
- **Search Integration**: Double-click to navigate (in-memory) or apply (TM/Glossary)

### Changed
- Updated SearchFetcher to accept both TM and Glossary database paths
- Enhanced SearchDialog with Glossary tab and field selectors
- Improved result display with color-coded scores and context labels

### Fixed
- Various UI improvements and bug fixes

## [1.0.0] - 2024-01-15

### Added
- Initial release
- Multi-format support (PO, XLIFF, MQXLIFF, SDLXLIFF, TMX, TS, CSV, TXT, PDF, DOCX, PPTX, XLSX, ODT, ODS, ODP)
- Translation Memory with fuzzy matching
- Glossary/Terminology management with collections
- Project management (native, OmegaT, memoQ)
- Quality Assurance checks
- Spell checking (Hunspell)
- Dark theme UI
- Keyboard shortcuts
- Tag handling
- Chapter/Bookmark view
- Windows installer (Inno Setup)