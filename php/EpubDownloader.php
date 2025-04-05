<?php

final class EpubDownloader {
    private $optional_meta_files = [
        "META-INF/encryption.xml",
        "META-INF/manifest.xml",
        "META-INF/metadata.xml",
        "META-INF/rights.xml",
        "META-INF/signatures.xml",
    ];

    public function __construct(
        private $downloader
    ) {
    }

    private function downloadOptional($path) {
        return $this->downloader->downloadFile($path);
    }

    private function downloadMandatory($path) {
        $contents  = $this->downloader->downloadFile($path);
        if (empty($contents)) {
            throw new DownloadException($path);
        }
        return $contents;
    }

    public function downloadEpub($destination) {
        $tmpfile = "$destination.tmp";
        $zip = new ZipArchive();
        $res = $zip->open($tmpfile, ZipArchive::CREATE | ZipArchive::EXCL);
        if ($res !== true) {
            throw new FileInputOutputException($res);
        }

        $mimetype = $this->downloadMandatory('mimetype');
        $zip->addFromString('mimetype', $mimetype, ZipArchive::CM_STORE);

        $container = $this->downloadMandatory('META-INF/container.xml');
        $zip->addFromString('META-INF/container.xml', $container);

        foreach ($this->optional_meta_files as $path) {
            $contents = $this->downloadOptional($path);
            if ($contents) {
                $zip->addFromString($path, $contents);
            }
        }

        $rootfiles = $this->getFilesFromContainerXml($container);
        $index = 1;
        $count = count($rootfiles);
        foreach ($rootfiles as $rootfile) {
            $contents = $this->downloadMandatory($rootfile);
            $zip->addFromString($rootfile, $contents);

            $rootfileDir = dirname($rootfile);
            $manifestFiles = $this->getFilesFromPackageXml($contents);
            $count = count($manifestFiles);
            $index = 1;
            foreach ($manifestFiles as $path) {
                echo "$index/$count\n";
                $index += 1;
                
                if ($rootfileDir != '.') {
                    $path = $rootfileDir . '/'. $path;
                }
                $contents = $this->downloadMandatory($path);
                $zip->addFromString($path, $contents);
            }
        }
        $zip->close();
        rename($tmpfile, $destination);
    }

    private function getFilesFromContainerXml($xml_string) {
        $dom = new DOMDocument();
        $dom->loadXML($xml_string);
        $rootfiles = $dom->getElementsByTagname('rootfile');
        $result = [];
        foreach ($rootfiles as $node) {
            $result[] = $node->getAttribute('full-path');
        }
        return $result;
    }

    private function getFilesFromPackageXml($xml_string) {
        $dom = new DOMDocument();
        $dom->loadXML($xml_string);
        $rootfiles = $dom->getElementsByTagname('item');
        $result = [];
        foreach ($rootfiles as $node) {
            $result[] = urldecode($node->getAttribute('href'));
        }
        return $result;
    }
}

