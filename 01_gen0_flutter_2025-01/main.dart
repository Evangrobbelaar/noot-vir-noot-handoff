import 'package:flutter/material.dart';
import 'dart:io';
import 'dart:async';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final server = await createServer();
  runApp(ServerApp(server: server));
}

Future<HttpServer> createServer() async {
  return await HttpServer.bind(InternetAddress.anyIPv4, 8090);
}

class ServerApp extends StatefulWidget {
  final HttpServer server;
  const ServerApp({super.key, required this.server});

  @override
  State<ServerApp> createState() => _ServerAppState();
}

class _ServerAppState extends State<ServerApp> {
  @override
  void initState() {
    super.initState();
    _handleRequests();
  }

  void _handleRequests() {
    widget.server.listen(
      (request) {
        request.response
          ..headers.contentType = ContentType.text
          ..write('Hello from Flutter Server!')
          ..close();
      },
      onError: print,
    );
  }

  @override
  void dispose() {
    widget.server.close();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      home: Scaffold(
        appBar: AppBar(title: const Text('Server')),
        body: Center(
          child: Text('Server Running on port 8090'),
        ),
      ),
    );
  }
}
