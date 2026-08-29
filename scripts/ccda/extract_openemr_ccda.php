<?php

$ignoreAuth = true;

$_SERVER['HTTP_HOST'] = 'localhost';
$_SERVER['REQUEST_URI'] = '/';
$_SERVER['SCRIPT_NAME'] = '/index.php';
$_SERVER['DOCUMENT_ROOT'] = '/var/www/localhost/htdocs/openemr';
$_GET['site'] = 'default';

require_once '/var/www/localhost/htdocs/openemr/interface/globals.php';

use OpenEMR\Services\CDADocumentService;

if ($argc !== 2) {
    fwrite(STDERR, "Usage: php extract_ccda.php <uuid>\n");
    exit(2);
}

$uuid = $argv[1];

$uuidBytes = hex2bin(str_replace('-', '', $uuid));

if ($uuidBytes === false || strlen($uuidBytes) !== 16) {
    fwrite(STDERR, "Invalid UUID: $uuid\n");
    exit(2);
}

$service = new CDADocumentService();
$content = $service->getFile($uuidBytes);

if (!is_string($content) || $content === '') {
    fwrite(STDERR, "Unable to retrieve C-CDA content.\n");
    exit(1);
}

echo $content;
