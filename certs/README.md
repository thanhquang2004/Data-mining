# Certificates Directory

This directory contains SSL/TLS certificates for secure database connections.

## ⚠️ Security Notice

**NEVER commit certificate files to version control!**

Certificate files are automatically ignored by `.gitignore`.

## Certificate Files

Place your certificate files here:

- **`ca-cert.pem`** - Certificate Authority (CA) root certificate
- **`client-cert.pem`** - Client SSL certificate
- **`client-key.pem`** - Private key for client certificate

## Setup Instructions

1. **Copy your certificates to this directory:**

   ```bash
   cp /path/to/your/ca.pem certs/ca-cert.pem
   cp /path/to/your/client-cert.pem certs/client-cert.pem
   cp /path/to/your/client-key.pem certs/client-key.pem
   ```

2. **Set appropriate permissions:**

   ```bash
   chmod 600 certs/*.pem
   ```

3. **Configure in `.env`:**

   ```bash
   DB_SSL_ENABLED=true
   DB_SSL_CA=ca-cert.pem
   DB_SSL_CERT=client-cert.pem
   DB_SSL_KEY=client-key.pem
   ```

4. **Test the connection:**
   ```bash
   python test_db_ssl.py
   ```

## File Permissions

Recommended permissions:

- Directory: `700` (owner only)
- Certificate files: `600` (owner read/write only)

```bash
chmod 700 certs/
chmod 600 certs/*.pem
```

## Cloud Provider Certificates

### AWS RDS

```bash
wget https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem -O certs/rds-ca-bundle.pem
```

### Google Cloud SQL

Download from Cloud Console → SQL → Instance → Connections → Server CA → Download

### Azure MySQL

```bash
wget https://dl.cacerts.digicert.com/DigiCertGlobalRootCA.crt.pem -O certs/azure-ca.pem
```

## Need Certificates?

If you need to generate self-signed certificates for testing:

```bash
# Generate CA key and certificate
openssl genrsa 2048 > ca-key.pem
openssl req -new -x509 -nodes -days 365000 -key ca-key.pem -out ca-cert.pem

# Generate client certificate and key
openssl req -newkey rsa:2048 -days 365000 -nodes -keyout client-key.pem -out client-req.pem
openssl rsa -in client-key.pem -out client-key.pem
openssl x509 -req -in client-req.pem -days 365000 -CA ca-cert.pem -CAkey ca-key.pem -set_serial 01 -out client-cert.pem
```

⚠️ **Note:** Self-signed certificates should only be used for testing/development.

## More Information

See `DATABASE_SSL_SETUP.md` in the project root for complete setup guide.
