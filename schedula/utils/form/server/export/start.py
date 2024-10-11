import http.server
import socketserver
import webbrowser

# Step 1: Choose a random available port by using port 0
PORT = 0

# Step 2: Create a simple HTTP request handler
Handler = http.server.SimpleHTTPRequestHandler

# Step 3: Open a socket and bind to the port to get the random port number
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    # Get the port that the server is actually using
    PORT = httpd.server_address[1]

    # Step 4: Construct the URL for localhost and the assigned random port
    url = f"http://localhost:{PORT}/"
    print(f"Serving at {url}")

    # Step 5: Automatically open the browser
    webbrowser.open(url)

    # Step 6: Start the server and keep it running
    httpd.serve_forever()
