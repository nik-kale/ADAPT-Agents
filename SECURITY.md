# Security Policy

## 🔒 Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 3.0.x   | ✅ Yes            |
| 2.0.x   | ⚠️  Security fixes only |
| < 2.0   | ❌ No             |

## 🚨 Reporting a Vulnerability

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report them via:

1. **GitHub Security Advisories** (preferred)
   - Go to the repository Security tab
   - Click "Report a vulnerability"
   - Fill out the form with details

2. **Email**: security@adapt-agents.io

### What to Include

Please include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if you have one)
- Your contact information

### Response Timeline

- **Initial Response**: Within 48 hours
- **Status Update**: Within 7 days
- **Fix Timeline**: Depends on severity
  - **Critical**: 1-7 days
  - **High**: 7-14 days
  - **Medium**: 14-30 days
  - **Low**: Next regular release

## 🛡️ Security Features

ADAPT-Agents includes several built-in security features:

### PII Filtering

Automatically filters sensitive data from logs:

```python
orchestrator = AsyncAgentOrchestrator(filter_pii=True)
```

Redacts:
- Email addresses
- Social Security Numbers
- Credit card numbers
- Phone numbers
- API keys
- JWT tokens

### API Authentication

When enabled, requires API key for all requests:

```bash
ADAPT_API_KEY=your-secret-key-here
```

### Secrets Management

Never commit secrets! Use environment variables:

```bash
# ❌ DON'T
api_key = "sk-1234567890abcdef"

# ✅ DO
import os
api_key = os.getenv("ADAPT_LLM_API_KEY")
```

### Container Security

- Runs as non-root user
- Minimal base image (python:3.11-slim)
- No unnecessary packages
- Health checks enabled

### Kubernetes Security

- Secrets stored in K8s secrets (not ConfigMaps)
- RBAC configured
- Network policies recommended
- Pod security policies

## 🔍 Security Best Practices

### For Users

1. **Keep Updated**: Always use the latest version
2. **Use HTTPS**: Enable TLS in production (see Ingress config)
3. **Rotate Keys**: Regularly rotate LLM API keys
4. **Audit Logs**: Enable audit logging for compliance
5. **Network Isolation**: Use private networks for Redis, databases
6. **PII Filtering**: Always enable in production

### For Developers

1. **Dependencies**: Run `pip audit` regularly
2. **Pre-commit Hooks**: Use Bandit for security scanning
3. **Code Review**: All PRs require review
4. **Test Security**: Include security tests
5. **Principle of Least Privilege**: Minimize permissions

## 🔧 Security Configuration

### Enable All Security Features

```bash
# .env
ADAPT_ENABLE_PII_FILTERING=true
ADAPT_ENABLE_AUDIT_LOGGING=true
ADAPT_API_KEY=strong-random-key-here
ADAPT_AUDIT_LOG_PATH=/var/log/adapt-agents/audit.log
```

### API Key Generation

```bash
# Generate secure random API key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### TLS/SSL

Use certificates in production:

```yaml
# k8s/ingress.yaml
spec:
  tls:
  - hosts:
    - adapt-agents.example.com
    secretName: adapt-agents-tls
```

## 📊 Known Security Considerations

### LLM API Keys

- Store in secrets manager (K8s secrets, AWS Secrets Manager, etc.)
- Never log API keys
- Use environment-specific keys
- Rotate regularly

### Redis Cache

- Use password authentication
- Enable TLS for Redis connections
- Isolate on private network
- Set appropriate TTL to limit data exposure

### Input Validation

- All inputs validated via Pydantic schemas
- Type checking enforced
- Size limits on uploads
- Sanitization of user inputs

## 🚫 Out of Scope

The following are explicitly out of scope for security reports:

- Theoretical attacks without proof of concept
- Social engineering
- Physical security
- Attacks requiring physical access
- Denial of Service (unless critical)
- Issues in third-party dependencies (report to maintainers directly)

## 📝 Security Updates

Security updates will be announced via:

- GitHub Security Advisories
- CHANGELOG.md (Security section)
- Release notes

## 🏆 Security Hall of Fame

We appreciate responsible disclosure! Contributors will be acknowledged (with permission) in:

- This file
- Release notes
- Project README

## 📞 Contact

- **Security Email**: security@adapt-agents.io
- **General Issues**: https://github.com/yourusername/ADAPT-Agents/issues
- **Discussions**: https://github.com/yourusername/ADAPT-Agents/discussions

---

**Last Updated**: 2025-01-16
**Policy Version**: 1.0
