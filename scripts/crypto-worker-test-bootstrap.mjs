import { parentPort } from "node:worker_threads";

globalThis.self = {
  onmessage: null,
  postMessage: (data) => parentPort.postMessage(data),
};

await import("../client/crypto.worker.js");

parentPort.on("message", (data) => self.onmessage({ data }));
