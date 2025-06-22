# Arbitrage Platform

This is a Django-based platform for cryptocurrency arbitrage scanning and trading.

## Project Structure

*(Details about project structure can be added here as it evolves)*

## Setup and Installation

*(Instructions for local setup, virtual environments, dependencies etc.)*

## Running the Application

*(How to run the development server, access the API, etc.)*

## Deployment Notes

### SSL/HTTPS for Production

**It is critically important to use SSL/HTTPS for any production deployment of this application.** This platform handles sensitive data, including user credentials, exchange API keys, and financial information. Transmitting this data over unencrypted HTTP would expose it to significant security risks.

While Django has some SSL-related settings, SSL/TLS termination itself is **not typically handled directly within the Django application** when using a WSGI server like Gunicorn (as configured in the `Dockerfile`). Instead, the common and recommended practice is to use a **reverse proxy** server in front of the Django/Gunicorn application.

**Role of a Reverse Proxy:**

*   **SSL/TLS Termination:** The reverse proxy (e.g., Nginx, Caddy, Traefik, or cloud provider services like AWS Application Load Balancer, Google Cloud Load Balancer) listens for incoming HTTPS connections from clients.
*   **Certificate Management:** It manages SSL/TLS certificates. For automated certificate issuance and renewal from Let's Encrypt, tools like **Certbot** can be used when self-hosting the reverse proxy.
*   **Request Forwarding:** After decrypting the HTTPS traffic, the reverse proxy forwards the plain HTTP request to the Django application (Gunicorn) running internally (e.g., within its Docker container on a private network or on `localhost`). The traffic between the reverse proxy and Gunicorn can be HTTP as it's within your trusted infrastructure.
*   **Other Benefits:** Reverse proxies can also provide benefits like load balancing, serving static files, caching, and additional security layers.

**Django Settings for HTTPS:**

Once your reverse proxy is configured to handle HTTPS and forward requests, you'll need to configure Django to recognize that it's running behind a secure proxy. Key settings in `settings.py` include:

*   `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')`: Tells Django to trust the `X-Forwarded-Proto` header from your proxy to determine if a request came in via HTTPS.
*   `SECURE_SSL_REDIRECT = True`: Redirects all HTTP requests to HTTPS (the proxy should ideally handle this as well, but Django can enforce it).
*   `SESSION_COOKIE_SECURE = True`: Ensures session cookies are only sent over HTTPS.
*   `CSRF_COOKIE_SECURE = True`: Ensures CSRF cookies are only sent over HTTPS.
*   `SECURE_HSTS_SECONDS`, `SECURE_HSTS_INCLUDE_SUBDOMAINS`, `SECURE_HSTS_PRELOAD`: For configuring HTTP Strict Transport Security (HSTS) for enhanced security, if desired.

**Summary for SSL/HTTPS:** Do not run this application in production without a reverse proxy handling SSL/TLS. Configure your chosen proxy to manage certificates and terminate HTTPS, then ensure Django's settings are correctly configured to work behind this secure proxy.

---

*(Other sections like Features, API Endpoints, etc., can be added later)*
