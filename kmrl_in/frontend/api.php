<?php
$config = require __DIR__ . '/config.php';
$base = rtrim($config['backend_url'], '/');
$path = $_GET['path'] ?? '/api/ai/induction?action=comprehensive_plan';
$url = $base . '/' . ltrim($path, '/');
$method = $_SERVER['REQUEST_METHOD'];
$opts = ['http'=>['method'=>$method,'ignore_errors'=>true,'header'=>'Content-Type: application/json\r\n']];
if ($method !== 'GET') $opts['http']['content'] = file_get_contents('php://input') ?: '{}';
$ctx=stream_context_create($opts); $body=@file_get_contents($url,false,$ctx);
$status=200; if(isset($http_response_header[0]) && preg_match('/\s(\d{3})\s/',$http_response_header[0],$m)) $status=(int)$m[1];
http_response_code($status); header('Content-Type: application/json'); echo $body ?: json_encode(['error'=>'Backend unavailable','backend'=>$base]);
