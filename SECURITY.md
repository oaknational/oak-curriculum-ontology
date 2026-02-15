# Security Policy

## Supported Versions

We currently support the following versions with security updates:

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take the security of the Oak Curriculum Ontology seriously. If you discover a security vulnerability, please help us by responsibly disclosing it.

### How to Report

**Please do NOT report security vulnerabilities through public GitHub issues.**

Instead, please report security vulnerabilities by emailing:

- **Email:** [security contact email to be added]
- **Subject Line:** "Security Vulnerability: Oak Curriculum Ontology"

Please include the following information:

- **Type of vulnerability** (e.g., injection, broken access control, etc.)
- **Location** (file path, URL, or specific component affected)
- **Step-by-step instructions** to reproduce the vulnerability
- **Potential impact** of the vulnerability
- **Suggested remediation** (if you have one)

### What to Expect

- **Acknowledgment:** We will acknowledge receipt of your vulnerability report within 3 business days.
- **Assessment:** We will assess the vulnerability and determine its severity and impact.
- **Updates:** We will provide regular updates (at least every 7 days) on our progress.
- **Resolution:** We aim to resolve critical vulnerabilities within 30 days.
- **Credit:** With your permission, we will credit you for the discovery in our security advisories.

## Security Considerations for Users

### Data Validation

- All curriculum data is validated against SHACL constraints before release
- CI/CD workflows automatically validate syntax and semantics
- Validation reports are generated for each build

### Distribution Integrity

All distribution files include:
- **SHA256 checksums** for file integrity verification
- **MD5 checksums** for compatibility
- **Metadata files** with build information

To verify a distribution file:

```bash
# Download the distribution and checksum file
wget https://github.com/oaknational/oak-curriculum-ontology-public/releases/latest/download/oak-curriculum-full.ttl
wget https://github.com/oaknational/oak-curriculum-ontology-public/releases/latest/download/checksums-sha256.txt

# Verify the checksum
sha256sum -c checksums-sha256.txt
```

### Dependency Security

- All Python dependencies are managed via `pyproject.toml`
- Dependencies are pinned to specific versions
- GitHub Dependabot is enabled for automated security updates
- Workflows use explicit permissions (least privilege principle)

### CI/CD Security

Our GitHub Actions workflows implement security best practices:

- ✅ **Explicit permissions** for each workflow (no default permissions)
- ✅ **Checksum verification** for all downloaded binaries
- ✅ **SSL/TLS verification** enabled by default
- ✅ **Secure file permissions** (no world-writable files)
- ✅ **Non-root container execution** where applicable
- ✅ **Concurrency limits** to prevent resource exhaustion

## Known Security Considerations

### 1. Ontology Import Resolution

The `merge_ttls_with_imports.py` script resolves `owl:imports` statements:

- **Default:** SSL certificate verification is ENABLED
- **Fallback:** If SSL verification fails, the script will retry with a warning
- **Recommendation:** Always use HTTPS URLs with valid certificates for imports

### 2. Docker Execution

The documentation generation workflow uses Docker:

- **Security:** Containers run with current user ID (not root)
- **Isolation:** Read-only mounts where possible
- **Image:** Official Widoco image from trusted source (`ghcr.io/dgarijo/widoco`)

### 3. GitHub Actions Permissions

All workflows use explicit minimal permissions:

```yaml
permissions:
  contents: read  # For code checkout
  pages: write    # Only when deploying documentation
  id-token: write # Only for GitHub Pages authentication
```

## Best Practices for Contributors

If you're contributing to this project:

1. **Never commit secrets** (API keys, passwords, tokens) to the repository
2. **Use environment variables** for sensitive configuration
3. **Validate all inputs** when processing user-provided data
4. **Follow secure coding practices** for Python and RDF/SPARQL
5. **Keep dependencies up to date** and review security advisories
6. **Test SHACL constraints** to ensure they can't be bypassed

## Security Audit History

| Date | Type | Findings | Status |
|------|------|----------|--------|
| 2026-02-15 | Self-assessment | Workflow security hardening | ✅ Resolved |

## References

- [GitHub Security Best Practices](https://docs.github.com/en/code-security)
- [OWASP Top Ten](https://owasp.org/www-project-top-ten/)
- [Semantic Web Security Considerations](https://www.w3.org/2001/tag/doc/web-https)
- [Supply Chain Security (SLSA)](https://slsa.dev/)

---

**Last Updated:** 2026-02-15
**Policy Version:** 1.0
