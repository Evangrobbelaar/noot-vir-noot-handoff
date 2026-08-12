import 'dart:convert';

import 'package:flutter/material.dart';
import 'dart:io';

class MyHttpServer {
  HttpServer? _server;
  Function(String)? onMessageReceived;

  Future<void> start() async {
    _server = await HttpServer.bind(InternetAddress.anyIPv4, 8089);
    print('Server listening on ${_server!.address.address}:${_server!.port}');

    await for (HttpRequest request in _server!) {
      handleRequest(request);
    }
  }

  void handleRequest(HttpRequest request) {
    print(
        'Received ${request.method} request from ${request.connectionInfo?.remoteAddress}');

    switch (request.method) {
      case 'GET':
        handleGetRequest(request);
        break;
      case 'POST':
        handlePostRequest(request);
        break;
      default:
        request.response
          ..statusCode = HttpStatus.methodNotAllowed
          ..write('Unsupported method')
          ..close();
    }
  }

  void handleGetRequest(HttpRequest request) {
    request.response
      ..statusCode = HttpStatus.ok
      ..write('Server is running')
      ..close();
  }

  void handlePostRequest(HttpRequest request) async {
    try {
      final buffer =
          await request.cast<List<int>>().transform(utf8.decoder).join();
      print('Received data: $buffer');

      if (onMessageReceived != null) {
        onMessageReceived!(buffer);
      }

      request.response
        ..statusCode = HttpStatus.ok
        ..write('Message received')
        ..close();
    } catch (e) {
      print('Error handling POST: $e');
      request.response
        ..statusCode = HttpStatus.internalServerError
        ..write('Error processing request')
        ..close();
    }
  }

  void stop() {
    _server?.close();
  }
}

void main() {
  runApp(const ServerApp());
}

class ServerApp extends StatefulWidget {
  const ServerApp({super.key});
  @override
  State<ServerApp> createState() => _ServerAppState();
}

class _ServerAppState extends State<ServerApp> {
  final MyHttpServer _httpServer = MyHttpServer();
  final List<String> _messages = [];

  @override
  void initState() {
    super.initState();
    _startServer();
  }

  Future<void> _startServer() async {
    _httpServer.onMessageReceived = (message) {
      setState(() {
        _messages.insert(0, message);
      });
    };
    await _httpServer.start();
  }

  @override
  void dispose() {
    _httpServer.stop();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        appBar: AppBar(
          title: const Text('HTTP Server'),
        ),
        body: ListView.builder(
          itemCount: _messages.length,
          itemBuilder: (context, index) {
            return ListTile(
              title: Text(_messages[index]),
            );
          },
        ),
      ),
    );
  }
}
