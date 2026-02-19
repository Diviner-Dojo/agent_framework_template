"""Tests for scripts/redact_secrets.py — read-time secret redaction."""

from scripts.redact_secrets import redact_secrets


class TestGenericSecrets:
    """Test generic key=value secret patterns."""

    def test_api_key_with_equals(self) -> None:
        text = "API_KEY= sk-abc123def456ghi789jkl"
        result = redact_secrets(text)
        assert "API_KEY=" in result
        assert "sk-abc123" not in result
        assert "[REDACTED]" in result

    def test_secret_key_with_colon(self) -> None:
        text = 'secret_key: "my_super_secret_value_1234"'
        result = redact_secrets(text)
        assert "secret_key:" in result
        assert "my_super_secret" not in result
        assert "[REDACTED]" in result

    def test_password_with_single_quotes(self) -> None:
        text = "password= 'longpasswordvalue12345678'"
        result = redact_secrets(text)
        assert "password=" in result
        assert "longpasswordvalue" not in result

    def test_token_preserves_key_name(self) -> None:
        text = "AUTH_TOKEN= abcdefghijklmnopqrstuv"
        result = redact_secrets(text)
        assert "AUTH_TOKEN=" in result
        assert "[REDACTED]" in result

    def test_short_value_not_redacted(self) -> None:
        text = "token= short"
        result = redact_secrets(text)
        assert result == text  # Too short to match (< 16 chars)


class TestAWSKeys:
    """Test AWS credential patterns."""

    def test_aws_access_key_id(self) -> None:
        text = "AKIAIOSFODNN7EXAMPLE"
        result = redact_secrets(text)
        assert "AKIA" not in result or "[REDACTED]" in result

    def test_aws_secret_access_key(self) -> None:
        text = "aws_secret_access_key= wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        result = redact_secrets(text)
        assert "aws_secret_access_key=" in result
        assert "wJalrXUtnFEMI" not in result
        assert "[REDACTED]" in result


class TestJWT:
    """Test JWT token pattern."""

    def test_jwt_token_redacted(self) -> None:
        token = (
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0."
            "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        )
        result = redact_secrets(token)
        assert "eyJ" not in result
        assert "[REDACTED]" in result

    def test_jwt_in_context(self) -> None:
        text = (
            "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9."
            "eyJzdWIiOiIxIn0."
            "rEGJ_BN4tHqoJW_eAGRoLjMnNqOQbxrN9brA5L78_0s"
        )
        result = redact_secrets(text)
        assert "eyJ" not in result


class TestGitHubTokens:
    """Test GitHub token patterns."""

    def test_github_pat(self) -> None:
        text = "token= ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefgh"
        result = redact_secrets(text)
        assert "ghp_" not in result
        assert "[REDACTED]" in result

    def test_github_fine_grained(self) -> None:
        text = "github_pat_" + "A" * 60
        result = redact_secrets(text)
        assert "github_pat_" not in result
        assert "[REDACTED]" in result


class TestSlackTokens:
    """Test Slack token patterns."""

    def test_slack_bot_token(self) -> None:
        text = "SLACK_TOKEN= xoxb-1234567890-abcdefghij"
        result = redact_secrets(text)
        assert "xoxb-" not in result
        assert "[REDACTED]" in result

    def test_slack_user_token(self) -> None:
        text = "xoxp-1234567890-abcdefghij"
        result = redact_secrets(text)
        assert "xoxp-" not in result

    def test_slack_app_token(self) -> None:
        text = "xoxa-1234567890-abcdefghij"
        result = redact_secrets(text)
        assert "xoxa-" not in result


class TestBearerTokens:
    """Test Bearer/Authorization header patterns."""

    def test_bearer_header(self) -> None:
        text = "Authorization: Bearer abc123def456ghi789jkl012"
        result = redact_secrets(text)
        assert "Authorization:" in result or "authorization:" in result.lower()
        assert "abc123def456" not in result
        assert "[REDACTED]" in result

    def test_bearer_equals(self) -> None:
        text = "bearer= abc123def456ghi789jkl012"
        result = redact_secrets(text)
        assert "abc123def456" not in result


class TestPrivateKeys:
    """Test PEM private key patterns."""

    def test_rsa_private_key(self) -> None:
        text = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA7q8c3mN...\n"
            "-----END RSA PRIVATE KEY-----"
        )
        result = redact_secrets(text)
        assert "BEGIN RSA PRIVATE KEY" in result
        assert "MIIEowIBAAKCAQEA7q8c3mN" not in result
        assert "[REDACTED PRIVATE KEY]" in result

    def test_generic_private_key(self) -> None:
        text = (
            "-----BEGIN PRIVATE KEY-----\nMIIEvgIBADANBgkqhkiG9w0B...\n-----END PRIVATE KEY-----"
        )
        result = redact_secrets(text)
        assert "MIIEvgIBADANBgkqhkiG9w0B" not in result


class TestConnectionStrings:
    """Test connection string patterns."""

    def test_postgres_connection(self) -> None:
        text = "DATABASE_URL= postgres://admin:secretpass@localhost:5432/mydb"
        result = redact_secrets(text)
        assert "postgres://" in result
        assert "secretpass" not in result
        assert "[REDACTED]@" in result

    def test_mongodb_connection(self) -> None:
        text = "mongodb://user:password123@cluster.mongodb.net/db"
        result = redact_secrets(text)
        assert "mongodb://" in result
        assert "password123" not in result

    def test_redis_connection(self) -> None:
        text = "redis://default:mypassword@redis-host:6379"
        result = redact_secrets(text)
        assert "redis://" in result
        assert "mypassword" not in result


class TestExportedSecrets:
    """Test shell export patterns."""

    def test_exported_api_key(self) -> None:
        text = "export API_KEY='sk-1234567890abcdefghij'"
        result = redact_secrets(text)
        assert "export API_KEY=" in result
        assert "sk-1234567890" not in result
        assert "[REDACTED]" in result

    def test_exported_aws_key(self) -> None:
        text = 'export AWS_SECRET_ACCESS_KEY="wJalrXUtnFEMI/K7MDENG/bPx"'
        result = redact_secrets(text)
        assert "export AWS_SECRET_ACCESS_KEY=" in result
        assert "wJalrXUtnFEMI" not in result


class TestNonSecrets:
    """Verify that non-secret content passes through unchanged."""

    def test_normal_code(self) -> None:
        text = "def calculate_total(items: list[int]) -> int:\n    return sum(items)"
        assert redact_secrets(text) == text

    def test_normal_config(self) -> None:
        text = "DEBUG= true\nPORT= 8080\nHOST= localhost"
        assert redact_secrets(text) == text

    def test_comments_preserved(self) -> None:
        text = "# This is a comment about API keys\n# No actual key here"
        assert redact_secrets(text) == text

    def test_empty_string(self) -> None:
        assert redact_secrets("") == ""

    def test_multiline_preserves_structure(self) -> None:
        text = "line1\nline2\nline3\n"
        assert redact_secrets(text) == text


class TestMultipleSecrets:
    """Test files with multiple secrets."""

    def test_multiple_secrets_in_one_text(self) -> None:
        text = (
            "API_KEY= sk-abc123def456ghi789jkl\n"
            "SLACK_TOKEN= xoxb-1234567890-abcdefghij\n"
            "DATABASE_URL= postgres://admin:pass@localhost/db\n"
            "DEBUG= true\n"
        )
        result = redact_secrets(text)
        assert "sk-abc123" not in result
        assert "xoxb-" not in result
        assert "admin:pass" not in result
        assert "DEBUG= true" in result  # Non-secret preserved
        assert result.count("[REDACTED]") >= 3
