const express = require("express");
const client = require("prom-client");

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json());

client.collectDefaultMetrics();

const httpRequestCounter = new client.Counter({
  name: "nodeapp_http_requests_total",
  help: "Total HTTP requests",
  labelNames: ["method", "route", "status"]
});

app.use((req, res, next) => {
  res.on("finish", () => {
    httpRequestCounter.inc({
      method: req.method,
      route: req.route ? req.route.path : req.path,
      status: res.statusCode
    });
  });
  next();
});

app.get("/", (req, res) => {
  res.status(200).json({
    message: "AI CI/CD Failure Analyzer App is running",
    version: "1.0.0",
    status: "success"
  });
});

app.get("/health", (req, res) => {
  res.status(200).json({
    status: "UP"
  });
});

app.get("/api/products", (req, res) => {
  res.status(200).json([
    { id: 1, name: "DevOps Course", price: 999 },
    { id: 2, name: "Kubernetes Course", price: 1499 },
    { id: 3, name: "AIOps Course", price: 1999 }
  ]);
});

app.get("/metrics", async (req, res) => {
  res.set("Content-Type", client.register.contentType);
  res.end(await client.register.metrics());
});

if (require.main === module) {
  app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
  });
}

module.exports = app;
