#!/usr/bin/env python3
"""
Generate a secure random JWT secret key
"""
import secrets
import sys


def generate_secret_key(length: int = 64) -> str:
    """
    Generate a secure random secret key

    Args:
        length: Length of the key in bytes (default: 64 bytes = 128 hex characters)

    Returns:
        Random hexadecimal string
    """
    return secrets.token_hex(length)


def main():
    """Generate and print a new JWT secret key"""
    print("🔐 Generating secure JWT secret key...")
    print()

    # Generate 64-byte key (128 hex characters)
    secret_key = generate_secret_key(64)

    print("✅ Generated JWT_SECRET_KEY:")
    print()
    print(f"JWT_SECRET_KEY={secret_key}")
    print()
    print("📝 Add this line to your .env file:")
    print(f"   JWT_SECRET_KEY={secret_key}")
    print()
    print("⚠️  IMPORTANT:")
    print("   - Keep this key secret!")
    print("   - Never commit it to version control")
    print("   - Use different keys for development and production")
    print("   - If key is compromised, regenerate it and all users will need to re-login")


if __name__ == "__main__":
    main()










