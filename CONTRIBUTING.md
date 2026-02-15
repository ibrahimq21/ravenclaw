# Contributing Guide

Thank you for considering contributing to this project! This document outlines the process for contributing.

## Getting Started

### Fork the Repository

1. Click the **Fork** button on the project's GitHub page
2. Clone your fork locally:
   ```bash
   git clone https://github.com/ibrahimq21/ravenclaw.git
   cd ravenclaw
   ```

### Set Up Upstream Remote

Keep your fork synchronized with the original repository:

```bash
git remote add upstream https://github.com/ibrahimq21/ravenclaw.git
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

- Follow the project's coding standards
- Write clear, self-documenting code
- Add comments for complex logic

### 3. Test Your Changes

```bash
npm test    # Node.js projects
pytest      # Python projects
cargo test  # Rust projects
flutter test # Flutter projects
```

### 4. Commit Your Changes

Use clear, descriptive commit messages:

```bash
git commit -m "Add: brief description of your changes"
git commit -m "Fix: resolve issue with login functionality"
git commit -m "Update: improve documentation clarity"
```

### 5. Sync with Upstream

Before pushing, ensure your branch is up-to-date:

```bash
git fetch upstream
git merge upstream/main
```

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub.

## Coding Standards

### General Guidelines

- Follow the project's existing style and conventions
- Use meaningful variable and function names
- Keep functions focused and small
- Write modular, reusable code

### Code Style

- **JavaScript/TypeScript**: ESLint configuration included
- **Python**: PEP 8 style guide
- **Dart/Flutter**: Effective Dart guidelines
- **General**: Run formatters before committing

### Documentation

- Update README.md for new features
- Add inline comments for complex logic
- Update API documentation as needed

## Pull Request Guidelines

### Before Submitting

- [ ] All tests pass
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No unnecessary dependencies added
- [ ] Commit messages are clear

### PR Description Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
Describe how you tested the changes

## Screenshots (if applicable)
Add screenshots for UI changes

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review
- [ ] I have commented my code
- [ ] I have made corresponding changes
- [ ] My changes generate no warnings
```

## Reporting Issues

### Before Reporting

- Search existing issues first
- Check if a similar issue already exists
- Review recent commits for fixes

### Issue Template

```markdown
## Bug Report

**Description**
Clear description of the bug

**Steps to Reproduce**
1. Step 1
2. Step 2
3. Step 3

**Expected Behavior**
What should happen

**Actual Behavior**
What actually happens

**Environment**
- OS: [e.g., Windows 11, macOS 14]
- Node/Python/Other: [version]
- Browser: [if applicable]

## Feature Request

**Description**
Clear description of the feature

**Use Case**
Why is this needed?

**Proposed Solution**
How should it work?

## Questions

Ask questions in Discussions or open an issue with the "question" label.
```

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/).

By participating, you are expected to uphold this code. Please report unacceptable behavior to the maintainers.

## Communication

- **Issues**: For bug reports and feature requests
- **Discussions**: For questions and ideas
- **Pull Requests**: For code contributions

## Recognition

Contributors will be recognized in the README.md file and release notes.

---

**Thank you for your contribution!**
