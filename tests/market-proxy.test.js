const assert = require("node:assert/strict");
const http = require("node:http");
const { spawn } = require("node:child_process");
const path = require("node:path");
const test = require("node:test");
const fs = require("node:fs");
const os = require("node:os");
const crypto = require("node:crypto");

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
      if (req.url === "/api/intelligence/documents/99/original") {
        res.writeHead(200, {"content-type":"application/octet-stream"});
        res.end(Buffer.from([0,255,128,65])); return;
      }
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

  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), "risk-auth-test-"));
  const password = crypto.randomBytes(24).toString("base64url");
  const child = spawn(process.execPath, [path.join(__dirname, "..", "server.js")], {
    cwd: path.join(__dirname, ".."),
    env: {
      ...process.env,
      PORT: String(proxyPort),
      FASTAPI_URL: `http://127.0.0.1:${upstreamPort}`,
      SESSION_SECRET: "proxy-test-session-secret",
      ADMIN_USERNAME: "fixtureadmin", ADMIN_PASSWORD: password,
      DASHBOARD_DB_PATH: path.join(temporary, "dashboard.db")
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
    const blocked = await fetch(`http://127.0.0.1:${proxyPort}/api/shipping/watchlist`, {
      method: "POST", headers: {"Content-Type": "application/json", "x-shipping-admin-token": "untrusted-client-token"},
      body: JSON.stringify({mmsi:"657106100"})
    });
    assert.equal(blocked.status, 401, "Anonymous watchlist mutation must be stopped by the proxy");
    const shipping = await fetch(`http://127.0.0.1:${proxyPort}/api/shipping/status`, {headers:{"x-shipping-admin-token":"untrusted-client-token"}});
    assert.equal(shipping.status, 200);
    assert.equal(forwardedRequest.headers["x-shipping-admin-token"], undefined, "Client-supplied private headers must be stripped");
    const blockedReport = await fetch(`http://127.0.0.1:${proxyPort}/api/intelligence/documents`, {
      method:"POST",headers:{"x-intelligence-admin-token":"untrusted-client-token"},body:formData
    });
    assert.equal(blockedReport.status,401,"Document upload requires a server administrator session");
    const invalid=await fetch(`http://127.0.0.1:${proxyPort}/api/auth/login`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:"fixtureadmin",password:"incorrect"})});
    assert.equal(invalid.status,401);
    const blockedSynthesis=await fetch(`http://127.0.0.1:${proxyPort}/api/intelligence/synthesis/refresh`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({window_start:"2026-10-01",window_end:"2026-10-14"})});
    assert.equal(blockedSynthesis.status,401);
    const login=await fetch(`http://127.0.0.1:${proxyPort}/api/auth/login`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({username:"fixtureadmin",password})});
    assert.equal(login.status,200);
    const cookie=login.headers.get("set-cookie").split(";")[0];
    const adminStatus=await fetch(`http://127.0.0.1:${proxyPort}/api/admin/market-data-status`,{headers:{cookie}});
    assert.equal(adminStatus.status,200,"Same session authorizes existing dashboard actions");
    const watched=await fetch(`http://127.0.0.1:${proxyPort}/api/shipping/watchlist`,{method:"POST",headers:{cookie,"Content-Type":"application/json"},body:JSON.stringify({mmsi:"657106100"})});
    assert.equal(watched.status,200,"Same session authorizes Shipping admin actions");
    assert.ok(forwardedRequest.headers["x-shipping-admin-token"]);
    const synthesis=await fetch(`http://127.0.0.1:${proxyPort}/api/intelligence/synthesis/refresh`,{method:"POST",headers:{cookie,"Content-Type":"application/json"},body:JSON.stringify({window_start:"2026-10-01",window_end:"2026-10-14"})});
    assert.equal(synthesis.status,200);
    assert.ok(forwardedRequest.headers["x-intelligence-admin-token"],"Synthesis uses the same private server credential");
    const report=new FormData();report.append("source_organisation","Other");report.append("title","Synthetic proxy fixture");report.append("report",new Blob(["synthetic-intelligence-bytes"],{type:"text/plain"}),"synthetic.txt");
    const reportResponse=await fetch(`http://127.0.0.1:${proxyPort}/api/intelligence/documents`,{method:"POST",headers:{cookie},body:report});
    assert.equal(reportResponse.status,200);
    assert.match(forwardedRequest.headers["content-type"],/^multipart\/form-data; boundary=/);
    assert.match(forwardedRequest.body,/synthetic-intelligence-bytes/);
    assert.equal(Boolean(forwardedRequest.headers["x-intelligence-admin-token"]),true,"Private header is injected server-side");
    const original=await fetch(`http://127.0.0.1:${proxyPort}/api/intelligence/documents/99/original`,{headers:{cookie}});
    assert.deepEqual(Buffer.from(await original.arrayBuffer()),Buffer.from([0,255,128,65]),"Original binary bytes must survive the shared proxy");
  } finally {
    child.kill("SIGTERM");
    await new Promise((resolve) => child.once("exit", resolve));
    await new Promise((resolve) => upstream.close(resolve));
    fs.rmSync(temporary,{recursive:true,force:true});
  }
});
