"""SSL/TLS utilities for HTTPS support."""

import logging
import os
import ssl
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_self_signed_cert(hostname: str = "localhost", cert_dir: str | None = None) -> tuple[str, str]:
    """Generate a self-signed certificate for HTTPS.
    
    Args:
        hostname: The hostname for the certificate (default: localhost)
        cert_dir: Directory to save certificates (default: ./.certs/)
    
    Returns:
        Tuple of (cert_path, key_path)
    """
    try:
        from cryptography import x509
        from cryptography.hazmat.backends import default_backend
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.x509.oid import NameOID
    except ImportError:
        logger.error("cryptography package not installed. Install with: pip install cryptography")
        raise ImportError("cryptography package required for SSL certificate generation")
    
    # Create cert directory if not specified
    if cert_dir is None:
        cert_dir = Path.cwd() / ".certs"
    else:
        cert_dir = Path(cert_dir)
    
    cert_dir.mkdir(exist_ok=True)
    
    cert_path = cert_dir / f"{hostname}.crt"
    key_path = cert_dir / f"{hostname}.key"
    
    # Check if certificate already exists
    if cert_path.exists() and key_path.exists():
        logger.info(f"Using existing certificate: {cert_path}")
        return str(cert_path), str(key_path)
    
    logger.info(f"Generating self-signed certificate for {hostname}")
    
    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
        backend=default_backend()
    )
    
    # Create certificate
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Zammad MCP Server"),
        x509.NameAttribute(NameOID.COMMON_NAME, hostname),
    ])
    
    # Certificate valid for 365 days
    cert = x509.CertificateBuilder().subject_name(
        subject
    ).issuer_name(
        issuer
    ).public_key(
        private_key.public_key()
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.utcnow()
    ).not_valid_after(
        datetime.utcnow() + timedelta(days=365)
    ).add_extension(
        x509.SubjectAlternativeName([
            x509.DNSName(hostname),
            x509.DNSName("localhost"),
            x509.DNSName("127.0.0.1"),
            x509.DNSName("::1"),
        ]),
        critical=False,
    ).sign(private_key, hashes.SHA256(), default_backend())
    
    # Write private key
    with open(key_path, "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption()
        ))
    
    # Write certificate
    with open(cert_path, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    
    # Set appropriate permissions (read-only for owner)
    os.chmod(key_path, 0o600)
    os.chmod(cert_path, 0o644)
    
    logger.info(f"Certificate generated: {cert_path}")
    logger.info(f"Private key generated: {key_path}")
    
    return str(cert_path), str(key_path)


def create_ssl_context(cert_path: str, key_path: str) -> ssl.SSLContext:
    """Create an SSL context for HTTPS server.
    
    Args:
        cert_path: Path to certificate file
        key_path: Path to private key file
    
    Returns:
        Configured SSLContext
    """
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(cert_path, key_path)
    
    # Use TLS 1.2 or higher
    ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
    
    return ssl_context