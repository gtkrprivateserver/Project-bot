// server.js
const http = require("http"); // import module http

// buat server
const server = http.createServer((req, res) => {
  res.writeHead(200, { "Content-Type": "text/plain" }); // optional, set header
  res.end("uptime!");
});

// jalankan server di port 8080
server.listen(8080, () => {
  console.log("Server running on port 8080");
});