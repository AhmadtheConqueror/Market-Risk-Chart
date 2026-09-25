const assert = require("node:assert/strict");
const http = require("node:http");
const { spawn } = require("node:child_process");
const path = require("node:path");
const test = require("node:test");

function listen(server) {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => resolve(server.address().port));
  });
}

function waitForServer(child, pattern) {
  return new Promise((resolve, reject) => {
    let output = "";
    const timeout = setTimeout(() => {
      child.kill("SIGTERM");
      reject(new Error(`Timed out waiting for server. Output: ${output}`));
    }, 15000);

    const onData = (chunk) => {
      output += chunk.toString();
      if (pattern.test(output)) {
        clearTimeout(timeout);
        child.stdout.off("data", onData);
        resolve();
      }
    };

    child.stdout.on("data", onData);
    child.once("exit", (code) => {
      clearTimeout(timeout);
      reject(new Error(`Proxy server exited with code ${code}. Output: ${output}`));
    });
  });
}

test("Node proxy forwards workbook multipart stream and boundary unchanged", async () => {
  let forwardedRequest = null;
  const upstream = http.createServer((req, res) => {
    const chunks = [];
    req.on("data", (chunk) => chunks.push(chunk));
    req.on("end", () => {
      forwardedRequest = {
        headers: req.headers,
        body: Buffer.concat(chunks).toString("latin1")
      };
      res.writeHead(200, { "content-type": "application/json" });
      res.end(JSON.stringify({ rows_read: 178, provider: "internal_excel" }));
    });
  });
  const upstreamPort = await listen(upstream);
  const proxyPort = await (async () => {
    const probe = http.createServer();
    const port = await listen(probe);
    await new Promise((resolve) => probe.close(resolve));
    return port;
  })();

  const child = spawn(process.execPath, [path.join(__dirname, "..", "server.js")], {
    cwd: path.join(__dirname, ".."),
    env: {
      ...process.env,
      PORT: String(proxyPort),
      FASTAPI_URL: `http://127.0.0.1:${upstreamPort}`,
      SESSION_SECRET: "proxy-test-session-secret"
    },
    stdio: ["ignore", "pipe", "pipe"]
  });

  try {
    await waitForServer(child, /Daily Oil Trading Risk Dashboard running/);
    const formData = new FormData();
    formData.append(
      "workbook",
      new Blob(["xlsx-payload"], { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" }),
      "sample.xlsx"
    );
    const response = await fetch(`http://127.0.0.1:${proxyPort}/api/market/import-excel`, {
      method: "POST",
      body: formData
    });

    assert.equal(response.status, 200);
    assert.deepEqual(await response.json(), { rows_read: 178, provider: "internal_excel" });
    assert.ok(forwardedRequest);
    assert.match(forwardedRequest.headers["content-type"], /^multipart\/form-data; boundary=/);
    assert.match(forwardedRequest.body, /name="workbook"/);
    assert.match(forwardedRequest.body, /filename="sample\.xlsx"/);
    assert.match(forwardedRequest.body, /xlsx-payload/);

    const newsResponse = await fetch(`http://127.0.0.1:${proxyPort}/api/news/latest`);
    assert.equal(newsResponse.status, 200);
    assert.deepEqual(await newsResponse.json(), { rows_read: 178, provider: "internal_excel" });
  } finally {
    child.kill("SIGTERM");
    await new Promise((resolve) => child.once("exit", resolve));
    await new Promise((resolve) => upstream.close(resolve));
  }
});
