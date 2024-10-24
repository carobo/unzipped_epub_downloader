import click
import os
import requests
import sys
import zipfile
from defusedxml.ElementTree import fromstring
from io import BytesIO
from tqdm import tqdm
from urllib.parse import urljoin


# Function to download the content of a file given its URL
def download_file(session, url):
    response = session.get(url)
    response.raise_for_status()
    return response.content


# Function to parse XML content
def parse_xml(xml_content):
    return fromstring(xml_content)


# Main function to download the EPUB
def download_epub(base_url, epub_filename, session):
    namespaces = {
        "c": "urn:oasis:names:tc:opendocument:xmlns:container",
        "opf": "http://www.idpf.org/2007/opf",
        "dc": "http://purl.org/dc/elements/1.1/",
    }

    optional_meta_files = [
        "META-INF/encryption.xml",
        "META-INF/manifest.xml",
        "META-INF/metadata.xml",
        "META-INF/rights.xml",
        "META-INF/signatures.xml",
    ]

    mimetype = download_file(session, urljoin(base_url, "mimetype"))

    container_url = urljoin(base_url, "META-INF/container.xml")
    container_xml_content = download_file(session, container_url)

    container_xml = parse_xml(container_xml_content)
    rootfile_elements = container_xml.findall("c:rootfiles/c:rootfile", namespaces)
    rootfile_paths = [r.attrib["full-path"] for r in rootfile_elements]

    with zipfile.ZipFile(epub_filename, "w", zipfile.ZIP_DEFLATED) as epub_zip:
        epub_zip.writestr("mimetype", mimetype, compress_type=zipfile.ZIP_STORED)

        epub_zip.writestr("META-INF/container.xml", container_xml_content)

        for meta_file in optional_meta_files:
            try:
                content = download_file(session, urljoin(base_url, meta_file))
                epub_zip.writestr(meta_file, content)
            except requests.exceptions.HTTPError:
                pass

        for rootfile_path in rootfile_paths:
            rootfile_url = urljoin(base_url, rootfile_path)
            rootfile_content = download_file(session, rootfile_url)
            rootfile_xml = parse_xml(rootfile_content)
            epub_zip.writestr(rootfile_path, rootfile_content)

            manifest = rootfile_xml.findall("opf:manifest/opf:item", namespaces)

            for item in tqdm(manifest):
                href = item.attrib["href"]
                file_url = urljoin(rootfile_url, href)
                file_path = urljoin(rootfile_path, href)
                file_content = download_file(session, file_url)
                epub_zip.writestr(file_path, file_content)


# Utility function to parse auth in "username:password" format
def parse_auth(ctx, param, value):
    if value is None:
        return None
    try:
        username, password = value.split(":", 1)
        return (username, password)
    except ValueError:
        raise click.BadParameter(
            'Authentication must be in "username:password" format.'
        )


# Utility function to parse headers in "key: value" format
def parse_headers(ctx, param, value):
    headers = {}
    for header in value:
        try:
            key, val = header.split(":", 1)
            headers[key.strip()] = val.strip()
        except ValueError:
            raise click.BadParameter('Headers must be in "key: value" format.')
    return headers


# Utility function to parse cookies in "key=value" format
def parse_cookies(ctx, param, value):
    cookies = {}
    for cookie in value:
        try:
            key, val = cookie.split("=", 1)
            cookies[key.strip()] = val.strip()
        except ValueError:
            raise click.BadParameter('Cookies must be in "key=value" format.')
    return cookies


# Utility function to parse query parameters in "key=value" format
def parse_params(ctx, param, value):
    params = {}
    for param in value:
        try:
            key, val = param.split("=", 1)
            params[key.strip()] = val.strip()
        except ValueError:
            raise click.BadParameter('Parameters must be in "key=value" format.')
    return params


@click.command()
@click.argument("base_url")
@click.argument("output_file")
@click.option(
    "--auth",
    callback=parse_auth,
    help="Authentication credentials in username:password format.",
)
@click.option("--cert", help="Path to SSL client certificate file (.pem).")
@click.option(
    "--cookie",
    multiple=True,
    callback=parse_cookies,
    help="Cookies to include in the request, in format key=value.",
)
@click.option(
    "--header",
    "-H",
    multiple=True,
    callback=parse_headers,
    help="Additional headers in key: value format.",
)
@click.option("--max-redirects", type=int, help="Maximum number of redirects allowed.")
@click.option(
    "--no-verify",
    is_flag=True,
    default=False,
    help="Whether to verify TLS certificates.",
)
@click.option(
    "--param",
    multiple=True,
    callback=parse_params,
    help="Additional query parameters to add to each request, in format key=value.",
)
@click.option("--proxy", help="Proxy to use, in format server:port.")
@click.option("--user-agent", help="User-Agent header to send")
def main(
    base_url,
    output_file,
    auth,
    cert,
    cookie,
    header,
    max_redirects,
    no_verify,
    param,
    proxy,
    user_agent,
):
    session = requests.Session()

    if auth:
        session.auth = auth

    if cert:
        session.cert = cert

    if cookie:
        session.cookies.update(cookie)

    if user_agent:
        session.headers["User-Agent"] = user_agent

    if header:
        session.headers.update(header)

    if max_redirects is not None:
        session.max_redirects = max_redirects

    if proxy:
        session.proxies = {"http": proxy, "https": proxy}

    if param:
        session.params.update(param)

    session.verify = not no_verify

    download_epub(base_url, output_file, session)


if __name__ == "__main__":
    main()
