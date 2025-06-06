# Cursor Rules

## Project Overview
- **Project Name**: finparse
- **Short Description**: Companion for Firefly III that parses israeli credit card expense reports
- **Tech Stack**: Latest and greatest python tech: New python, pydantic, typer, black, uv, ruff

### Decsription
Finparse is a companion CLI/TUI app for Firefly III, which is a personal finances manager. The goal of Finparse is to help track expenses, without having to manually input every expense.

### Technical overview
Since finparse is a CLI/TUI application, the main flow is uploading expenses via the upload command (in main.py). 
Expense reports can be downloaded as excel files from the sites of the credit card companies. Each company has a different format, so they have different parsers. 
The appropriate parser is selected automatically, the expenses are grouped by card, sometimes also grouped by local and foreign expense, in which case they have 2 currencies and amounts.
Each transaction is uploaded to Firefly III with the relevant extracted data

## Code Style Guidelines
- **Formatter**: black

## Documentation Requirements
- **Code Comments**: Don't document obvious stuff

## Testing Guidelines
- **Test Framework**: pytest

## Error Handling
- **Logging**: If code isn't debuggable via logging, it's impossible to investigate production bugs. Logs are embraced

## Dependencies
- **Package Management**: uv

## Maintenance
- **Code Review Process**: Keep it simple!
- **Refactoring Guidelines**: The project is small, so refactor at will
- **Technical Debt**: Avoid technical debt. Refactor and delete with bravery