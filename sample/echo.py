import socket


sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.bind(('127.0.0.1', 8888))
sock.listen(1)


print('serving on {}'.format(sock.getsockname()))
running = True
while running:
    try:
        client, addr = sock.accept()
        message = client.recv(1024)
        print("received %r from %r" % (message, addr))
        print("send: %r" % message)
        client.send(message)
        client.close()
    except KeyboardInterrupt:
        break

print("closing echo server")
# Close the server
sock.close()

