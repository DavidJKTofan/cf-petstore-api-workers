# API Token Generator

A Python utility for generating and validating JWT tokens for pet store customers with different access levels and metadata.

## Overview

This tool allows you to:
- Create customer profiles with metadata (premium/standard/free status, rate limits, etc.)
- Generate short-lived JWT tokens for API authentication
- Include customer-specific metadata in the token payload
- Save tokens to a specified directory
- Basic token validation (for demo purposes)

## Requirements

- Python 3.6+
- [Authlib](https://authlib.org/) library
- [Cryptography](https://cryptography.io/) library

## Installation

1. Clone this repository
2. Create a Python virtual environment:

```
python3 -m venv JWT_TOKENS
source JWT_TOKENS/bin/activate
```

3. Install the required dependencies:

```bash
pip install authlib cryptography
```

4. Ensure you have valid key files:
   - `private-key.pem` - For token signing
   - `public-key.pem` - For token validation

## Creating Key Pairs

You can create the necessary public and private keys using [mkjwk.org](https://mkjwk.org/):

1. Visit [mkjwk.org](https://mkjwk.org/)
2. Configure the key:
   - Key Size: 256 bits (recommended for ES256)
   - Key Use: Signature
   - Algorithm: ES256
   - Key ID (kid): `petstore-ec256` (or your preferred ID)
3. Click "Generate"
4. Save the generated keys:
   - Look for the `Private Key (X.509 PEM Format)` section and copy the PEM format key
   - Save this text to a file named `private-key.pem`
   - Look for the `Public Key (X.509 PEM Format)` section and copy the PEM format key
   - Save this text to a file named `public-key.pem`

> **IMPORTANT**: Make sure to use the PEM format keys (beginning with `-----BEGIN PRIVATE KEY-----` or `-----BEGIN PUBLIC KEY-----`), not the JSON format.

> Upload the `Public Key` part to Cloudflare's API Shield JWT Validation configuration.

Example of a valid `private-key.pem` file:
```
-----BEGIN PRIVATE KEY-----
MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgYirTZSx+5O8Y6tlG
cka6W6btJiocdrdolfcukSoNiEuhRANCAAQfwJNa+syUdtGBgxGYgF7fP/CSGHVs
rFMyF7ypydJ3VkmZW0Wn6Z+1iJN65K9mYVd3yBEpV0wN4TYSHGQmNN0L
-----END PRIVATE KEY-----
```

Example of a valid `public-key.pem` file:
```
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEH8CTWvrMlHbRgYMRmIBe3z/wkhh1
bKxTMhe8qcnSd1ZJmVtFp+mftYiTeuSvZmFXd8gRKVdMDeE2EhxkJjTdCw==
-----END PUBLIC KEY-----
```

## Usage

### Basic Usage

Run the script without any arguments to generate tokens for the example customers:

```bash
python create_customer_token.py
```

The script will:
1. Create sample customers (premium, standard, free)
2. Generate JWT tokens for each customer
3. Print the tokens and validated payload data

### Saving Tokens to a Folder

You can save the generated tokens to a specific folder using the `--output-dir` argument:

```bash
python create_customer_token.py --output-dir tokens
```

This will:
1. Create the specified directory if it doesn't exist
2. Save each token to a separate file in that directory
3. Use the naming format: `{username}_{customer_type}_{timestamp}.jwt`
4. Print the file path for each saved token

### Command-Line Arguments

The script supports the following command-line arguments:

```bash
# Example with all possible arguments
python create_customer_token.py \
    --key-path private-key.pem \
    --issuer https://petstore.automatic-demo.com \
    --audience petstore \
    --key-id petstore-ec256 \
    --username user1 \
    --customer-type premium \
    --email user1@example.com \
    --company "Acme Corp" \
    --subscription-tier enterprise \
    --expiration 3600 \
    --additional-metadata '{"rate_limit": 1000, "api_access_level": "full"}' \
    --output-dir tokens
```

Another example for 15 minutes of testing purposes:

```bash
python create_customer_token.py --username user1 --customer-type premium --email user1@example.com --expiration 900 --output-dir temp_tokens
```

#### Available Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--key-path` | Path to the private key file | `private-key.pem` |
| `--issuer` | JWT issuer claim | `https://petstore.automatic-demo.com` |
| `--audience` | JWT audience claim | `petstore` |
| `--key-id` | Key ID for JWT header | `petstore-ec256` |
| `--username` | Customer username | None |
| `--customer-type` | Customer type (premium, standard, free) | None |
| `--email` | Customer email | None |
| `--company` | Customer company | None |
| `--subscription-tier` | Customer subscription tier | None |
| `--expiration` | Token expiration in seconds | 3600 |
| `--additional-metadata` | JSON string with additional metadata | None |
| `--output-dir` | Directory to save token files | None (tokens only printed) |

### Using as a Module

You can import and use the classes in your own code:

```python
from create_customer_token import Customer, CustomerType, TokenGenerator

# Initialize token generator
token_generator = TokenGenerator(
    private_key_path="private-key.pem",
    issuer="https://your-api.example.com",
    audience="your-service",
    key_id="your-key-id"
)

# Create a customer
customer = Customer(
    username="customer123",
    customer_type=CustomerType.PREMIUM,
    email="customer@example.com",
    company="Example Inc",
    subscription_tier="enterprise",
    additional_metadata={
        "rate_limit": 1000,
        "api_access_level": "full"
    }
)

# Add customer to generator
token_generator.add_customer(customer)

# Generate token
token = token_generator.generate_token("customer123")
print(token)

# Validate token (demo)
payload = token_generator.validate_token(token)
print(payload)
```

## Verifying Tokens

You can verify tokens using [JWT.io](https://jwt.io/):

1. Visit [jwt.io](https://jwt.io/)
2. Paste your generated token in the "Encoded" section
3. In the "Verify Signature" section:
   - Paste your public key (or private key for testing)
   - Make sure the algorithm is set to ES256
4. The signature will show as "Verified" if the token is valid
5. You can examine the decoded payload in the center panel

## Customer Types

The script supports three customer types:

| Type | Description | Example Metadata |
|------|-------------|-----------------|
| PREMIUM | Full access with highest rate limits | `rate_limit: 1000`, `api_access_level: "full"` |
| STANDARD | Standard access with medium rate limits | `rate_limit: 500`, `api_access_level: "standard"` |
| FREE | Basic access with lowest rate limits | `rate_limit: 100`, `api_access_level: "basic"` |

## Adding Custom Metadata

You can add any custom metadata to a customer using the `additional_metadata` parameter:

```python
customer = Customer(
    username="user1",
    customer_type=CustomerType.PREMIUM,
    email="user1@example.com",
    additional_metadata={
        "feature_flags": ["advanced_search", "bulk_operations"],
        "region": "us-west",
        "account_manager": "john.doe@company.com"
    }
)
```

This metadata will be included in the JWT payload under the `customer` field.

## Token Format

Generated tokens follow this format:

```
header.payload.signature
```

The payload includes:
- Standard JWT claims (`iss`, `aud`, `sub`, `exp`, `iat`)
- Custom JWT claims (`username`, `customer_type`)
- Customer data in the `customer` field (nested values)

Example payload:
```json
{
  "iss": "https://petstore.automatic-demo.com",
  "aud": "petstore",
  "sub": "user1",
  "exp": 1713918245,
  "iat": 1713914645,
  "username": "user1",
  "customer_type": "premium",
  "customer": {
    "username": "user1",
    "customer_type": "premium",
    "email": "user1@example.com",
    "company": "Acme Corp",
    "subscription_tier": "enterprise",
    "rate_limit": 1000,
    "api_access_level": "full"
  }
}
```

## Token Expiration

By default, tokens expire after 1 hour (3600 seconds). You can customize this when generating a token:

```python
# Generate token that expires in 30 minutes
token = token_generator.generate_token("user1", expiration_seconds=1800)
```

## Security Considerations

- For production use, implement proper token validation using the public key
- Store private keys securely and never commit them to version control
- Consider using a shorter expiration time for sensitive operations
- Implement token revocation if needed for security incidents

## Troubleshooting

### Private Key Errors

If you encounter errors like:
```
ValueError: Could not deserialize key data. The data may be in an incorrect format...
```

Check the following:
1. Ensure your private key is in PEM format (starts with `-----BEGIN PRIVATE KEY-----`)
2. Make sure you're using the right key algorithm (EC keys for ES256)
3. Try regenerating the keys at [mkjwk.org](https://mkjwk.org/) and copy the PEM format keys

### Token Validation Errors

If token validation fails:
1. Make sure the token hasn't expired
2. Check that the public key matches the private key used for signing
3. Verify the algorithm specified in the token header matches the key type

## File Structure

- `create_customer_token.py` - Main script with Customer and TokenGenerator classes
- `private-key.pem` - Private key for signing tokens
- `public-key.pem` - Public key for validating tokens (not used in current implementation)

## Example: Generating a Token for a New Customer

```python
# Create a new customer
new_customer = Customer(
    username="alice",
    customer_type=CustomerType.STANDARD,
    email="alice@example.com",
    company="Wonderland Inc",
    subscription_tier="professional",
    additional_metadata={
        "rate_limit": 500,
        "api_access_level": "standard",
        "feature_flags": ["reporting", "dashboard"]
    }
)

# Add customer to generator
token_generator.add_customer(new_customer)

# Generate token
token = token_generator.generate_token("alice")
print(f"Token for Alice: {token}")
```

## Example: Generating Tokens with Different Expiration Times

```python
# Short-lived token (5 minutes)
short_token = token_generator.generate_token("user1", expiration_seconds=300)
print(f"Short-lived token: {short_token}")

# Long-lived token (1 day)
long_token = token_generator.generate_token("user1", expiration_seconds=86400)
print(f"Long-lived token: {long_token}")
```

---

## Disclaimer

Educational purposes only.