const request = require("supertest");
const app = require("./server");

describe("AI CI/CD Node App", () => {
  test("GET / should return success message", async () => {
    const response = await request(app).get("/");
    expect(response.statusCode).toBe(200);
    expect(response.body.status).toBe("success");
  });

  test("GET /health should return UP", async () => {
    const response = await request(app).get("/health");
    expect(response.statusCode).toBe(200);
    expect(response.body.status).toBe("UP");
  });

  test("GET /api/products should return products", async () => {
    const response = await request(app).get("/api/products");
    expect(response.statusCode).toBe(200);
    expect(response.body.length).toBeGreaterThan(0);
  });
});
