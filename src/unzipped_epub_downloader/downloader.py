import os
import zipfile
from io import BytesIO
import requests
from defusedxml.ElementTree import fromstring
import sys
from urllib.parse import urljoin
from tqdm import tqdm


# Function to download the content of a file given its URL
def download_file(session, url):
    response = session.get(url)
    response.raise_for_status()
    return response.content


# Function to parse XML content
def parse_xml(xml_content):
    return fromstring(xml_content)


# Main function to download the EPUB
def download_epub(base_url, session):
    namespaces = {
        "c": "urn:oasis:names:tc:opendocument:xmlns:container",
        "opf": "http://www.idpf.org/2007/opf",
        "dc": "http://purl.org/dc/elements/1.1/",
    }

    mimetype = download_file(session, urljoin(base_url, "mimetype"))

    # Step 1: Retrieve META-INF/container.xml
    container_url = urljoin(base_url, "META-INF/container.xml")
    container_xml_content = download_file(session, container_url)

    # Step 2: Parse META-INF/container.xml and get rootfile path
    container_xml = parse_xml(container_xml_content)
    rootfile_element = container_xml.find("c:rootfiles/c:rootfile", namespaces)
    rootfile_path = rootfile_element.attrib["full-path"]
    rootfile_mime = rootfile_element.attrib["media-type"]

    # Step 3: Download the rootfile (typically content.opf)
    rootfile_url = urljoin(base_url, rootfile_path)
    rootfile_content = download_file(session, rootfile_url)

    # Step 4: Parse the rootfile (content.opf) and extract the manifest and title
    rootfile_xml = parse_xml(rootfile_content)

    # Extract title from the metadata
    title = rootfile_xml.find("opf:metadata/dc:title", namespaces).text

    epub_filename = f"{title}.epub"
    with zipfile.ZipFile(epub_filename, "w", zipfile.ZIP_DEFLATED) as epub_zip:
        epub_zip.writestr("mimetype", mimetype, compress_type=zipfile.ZIP_STORED)
        epub_zip.writestr(rootfile_path, rootfile_content)
        epub_zip.writestr("META-INF/container.xml", container_xml_content)

        # Step 5: Download all files mentioned in the manifest
        manifest = rootfile_xml.findall("opf:manifest/opf:item", namespaces)

        for item in tqdm(manifest):
            href = item.attrib["href"]
            file_url = urljoin(rootfile_url, href)
            file_path = urljoin(rootfile_path, href)
            file_content = download_file(session, file_url)
            epub_zip.writestr(file_path, file_content)

    print(f"EPUB '{epub_filename}' created successfully!")


# Example usage:
if __name__ == "__main__":
    base_url = sys.argv[1]  # Base URL of the unzipped EPUB
    session = requests.Session()

    download_epub(base_url, session)
