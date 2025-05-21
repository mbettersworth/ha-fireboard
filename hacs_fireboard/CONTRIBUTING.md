# Contributing to Fireboard Integration for Home Assistant

Thank you for considering contributing to this integration! Here are some guidelines to help you get started.

## Development Environment Setup

1. Fork the repository
2. Clone your fork
3. Set up a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   pip install -r requirements_test.txt
   ```

## Guidelines

- Follow the [Home Assistant code style](https://developers.home-assistant.io/docs/development_guidelines)
- Write tests for new features
- Keep the dependencies minimal
- Update documentation as needed

## Testing

Run tests using pytest:

```bash
pytest
```

## Pull Request Process

1. Ensure your code follows the style guidelines
2. Update the documentation
3. Write or update tests as needed
4. Submit a pull request

## Adding Features

If you're planning to add a major feature, please open an issue first to discuss it.

## Issues and Bug Reports

When reporting issues, please include:
- Your Home Assistant version
- Your Fireboard device model
- Steps to reproduce the issue
- Expected behavior
- Actual behavior

## Code of Conduct

Please be respectful and constructive in your interactions with others.