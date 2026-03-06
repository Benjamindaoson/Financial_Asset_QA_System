# Contributing to Financial Asset QA System

Thank you for your interest in contributing! This document provides guidelines and instructions for contributing to the project.

## 🌟 Ways to Contribute

- 🐛 Report bugs and issues
- 💡 Suggest new features or enhancements
- 📝 Improve documentation
- 🧪 Add or improve tests
- 💻 Submit code contributions
- 🌍 Translate documentation

## 🚀 Getting Started

### 1. Fork and Clone

```bash
# Fork the repository on GitHub
# Then clone your fork
git clone https://github.com/YOUR_USERNAME/Financial_Asset_QA_System.git
cd Financial_Asset_QA_System
```

### 2. Set Up Development Environment

#### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Development dependencies
```

#### Frontend

```bash
cd frontend
npm install
```

### 3. Create a Branch

```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/your-bug-fix
```

## 📋 Development Guidelines

### Code Style

#### Python (Backend)

- Follow PEP 8 style guide
- Use Black for formatting: `black app/ tests/`
- Use isort for imports: `isort app/ tests/`
- Use flake8 for linting: `flake8 app/ tests/`
- Type hints are encouraged

```python
# Good
async def get_price(self, symbol: str) -> MarketData:
    """Get current price for a symbol."""
    normalized = self.ticker_mapper.normalize(symbol)
    return await self._fetch_data(normalized)

# Bad
async def get_price(self, symbol):
    normalized = self.ticker_mapper.normalize(symbol)
    return await self._fetch_data(normalized)
```

#### JavaScript (Frontend)

- Follow ESLint configuration
- Use Prettier for formatting: `npm run format`
- Use functional components with hooks
- Prefer const over let

```javascript
// Good
const ChatPanel = ({ onSendMessage }) => {
  const [message, setMessage] = useState('');

  const handleSubmit = useCallback(() => {
    onSendMessage(message);
    setMessage('');
  }, [message, onSendMessage]);

  return <div>...</div>;
};

// Bad
function ChatPanel(props) {
  var message = '';
  // ...
}
```

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/) format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples:**

```bash
feat(reasoning): add DeepAnalyzer module for complex queries

- Implement multi-step reasoning
- Add cross-asset comparison
- Include historical pattern analysis

Closes #123

fix(market): handle Alpha Vantage rate limit errors

- Add exponential backoff retry logic
- Improve error messages
- Update tests

test(agent): increase ResponseGuard test coverage to 100%
```

### Testing

#### Backend Tests

```bash
cd backend

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_agent_core.py -v

# Run with coverage
pytest tests/ --cov=app --cov-report=term-missing

# Run specific test
pytest tests/test_agent_core.py::TestAgentCore::test_initialization -v
```

**Test Requirements:**
- All new features must include tests
- Maintain or improve code coverage (currently 85%)
- Tests must pass before PR submission
- Include both unit and integration tests where appropriate

#### Frontend Tests

```bash
cd frontend

# Run tests
npm test

# Run with coverage
npm run test:coverage
```

### Documentation

- Update README.md for user-facing changes
- Add docstrings to all public functions and classes
- Update API documentation for endpoint changes
- Include inline comments for complex logic

```python
def calculate_technical_score(self, technical: Dict[str, Any]) -> float:
    """
    Calculate technical analysis score (0-1).

    Args:
        technical: Technical indicators including RSI, MACD, Bollinger Bands

    Returns:
        Score between 0.0 (bearish) and 1.0 (bullish)

    Example:
        >>> engine = DecisionEngine()
        >>> score = engine.calculate_technical_score({
        ...     "rsi": {"value": 65, "level": "中性"},
        ...     "macd": {"signal_type": "金叉"}
        ... })
        >>> assert 0.5 <= score <= 1.0
    """
    # Implementation...
```

## 🐛 Reporting Bugs

### Before Submitting

1. Check existing issues to avoid duplicates
2. Verify the bug exists in the latest version
3. Collect relevant information

### Bug Report Template

```markdown
**Describe the bug**
A clear description of what the bug is.

**To Reproduce**
Steps to reproduce:
1. Go to '...'
2. Click on '...'
3. See error

**Expected behavior**
What you expected to happen.

**Actual behavior**
What actually happened.

**Screenshots**
If applicable, add screenshots.

**Environment:**
- OS: [e.g., Windows 11]
- Python version: [e.g., 3.11.5]
- Node version: [e.g., 18.17.0]
- Browser: [e.g., Chrome 120]

**Additional context**
Any other relevant information.
```

## 💡 Suggesting Features

### Feature Request Template

```markdown
**Is your feature request related to a problem?**
A clear description of the problem.

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Alternative solutions or features you've considered.

**Additional context**
Any other context, mockups, or examples.
```

## 🔄 Pull Request Process

### 1. Before Submitting

- [ ] Code follows style guidelines
- [ ] All tests pass
- [ ] New tests added for new features
- [ ] Documentation updated
- [ ] Commit messages follow convention
- [ ] Branch is up to date with main

### 2. PR Checklist

```markdown
## Description
Brief description of changes.

## Type of Change
- [ ] Bug fix (non-breaking change)
- [ ] New feature (non-breaking change)
- [ ] Breaking change (fix or feature that would cause existing functionality to change)
- [ ] Documentation update

## Testing
- [ ] All existing tests pass
- [ ] New tests added
- [ ] Manual testing completed

## Screenshots (if applicable)
Add screenshots for UI changes.

## Related Issues
Closes #123
```

### 3. Review Process

1. Automated checks must pass (tests, linting)
2. At least one maintainer review required
3. Address review feedback
4. Maintainer will merge when approved

## 🏗️ Project Structure

```
Financial_Asset_QA_System/
├── backend/
│   ├── app/
│   │   ├── agent/          # Agent orchestration
│   │   ├── api/            # FastAPI routes
│   │   ├── market/         # Market data services
│   │   ├── rag/            # RAG pipeline
│   │   ├── reasoning/      # Reasoning layer
│   │   ├── routing/        # Query routing
│   │   └── search/         # Web search
│   ├── tests/              # Test suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/     # React components
│   │   ├── services/       # API services
│   │   └── utils/          # Utilities
│   └── package.json
├── data/                   # Knowledge base data
├── docker/                 # Docker configuration
└── docs/                   # Documentation
```

## 📚 Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [React Documentation](https://react.dev/)
- [Anthropic Claude API](https://docs.anthropic.com/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Conventional Commits](https://www.conventionalcommits.org/)

## 🤔 Questions?

- Open a [GitHub Discussion](https://github.com/Benjamindaoson/Financial_Asset_QA_System/discussions)
- Check existing [Issues](https://github.com/Benjamindaoson/Financial_Asset_QA_System/issues)
- Review [Documentation](README.md)

## 📜 Code of Conduct

### Our Pledge

We pledge to make participation in our project a harassment-free experience for everyone, regardless of age, body size, disability, ethnicity, gender identity and expression, level of experience, nationality, personal appearance, race, religion, or sexual identity and orientation.

### Our Standards

**Positive behavior:**
- Using welcoming and inclusive language
- Being respectful of differing viewpoints
- Gracefully accepting constructive criticism
- Focusing on what is best for the community

**Unacceptable behavior:**
- Trolling, insulting/derogatory comments, and personal attacks
- Public or private harassment
- Publishing others' private information without permission
- Other conduct which could reasonably be considered inappropriate

### Enforcement

Instances of abusive, harassing, or otherwise unacceptable behavior may be reported by opening an issue or contacting the project maintainers. All complaints will be reviewed and investigated promptly and fairly.

---

Thank you for contributing to Financial Asset QA System! 🎉
