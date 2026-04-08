# Contributing to Easy AI Shell

Thank you for your interest in contributing to Easy AI Shell! This document provides guidelines and instructions for contributing to the project.

## Table of Contents
- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Workflow](#development-workflow)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Style Guides](#style-guides)
- [Reporting Issues](#reporting-issues)

## Code of Conduct
By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting Started
1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/easy-ai.git`
3. Create a new branch: `git checkout -b feature/your-feature-name`
4. Install dependencies (if any): Currently zero-dependencies, just Python standard library
5. Make your changes
6. Test your changes thoroughly
7. Commit your changes with a descriptive commit message
8. Push to your fork: `git push origin feature/your-feature-name`
9. Submit a pull request

## Development Workflow
- Always create a new branch for your feature or bug fix
- Keep your changes focused on a single issue/feature
- Follow the existing code style and patterns
- Add/update documentation as needed
- Test your changes in different environments if possible

## Pull Request Guidelines
- Fill out the PR template completely
- Describe the problem and solution clearly
- Include any relevant issue numbers
- Ensure all tests pass (if applicable)
- Keep PRs reasonably sized (preferably under 500 lines of changes)
- Update documentation if your changes affect user-facing functionality

## Style Guides
### Python
- Follow PEP 8 style guide
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions reasonably short and focused
- Use type hints where appropriate

### AGI Growth System
- Follow the five-layer architecture pattern (DNA/Soul/State/Consolidation/Inference)
- Ensure all components accept global_config parameter in constructors
- Maintain backward compatibility when adding new configuration options
- Add appropriate logging for debugging and monitoring
- Follow the existing configuration schema in agi_config.json

### Documentation
- Use clear, concise language
- Follow the existing documentation style
- Include examples where helpful
- Keep README.md up to date with any major changes

## Reporting Issues
When reporting issues, please include:
- A clear and descriptive title
- Steps to reproduce the issue
- Expected vs actual behavior
- Your environment (OS, Python version, etc.)
- Any relevant error messages or logs

## Questions?
If you have questions about contributing, feel free to open an issue with the "question" label.