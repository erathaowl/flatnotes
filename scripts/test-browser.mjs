import assert from "node:assert/strict";
import { chromium } from "playwright";

const baseURL = process.env.FLATNOTES_TEST_URL || "http://127.0.0.1:18080";
const browser = await chromium.launch({ headless: true });
const owner = await browser.newContext({ baseURL });
const anonymous = await browser.newContext({ baseURL });
const ownerPage = await owner.newPage();
const publicPage = await anonymous.newPage();
const mobile = await browser.newContext({
  baseURL,
  viewport: { width: 390, height: 600 },
  deviceScaleFactor: 3,
  isMobile: true,
  hasTouch: true,
});
const mobilePage = await mobile.newPage();

async function expectStatus(response, expected) {
  assert.equal(response.status(), expected, await response.text());
  return response;
}

try {
  // An unauthenticated visitor cannot read private notes.
  await expectStatus(await anonymous.request.get("/api/notes/Smoke"), 401);

  // The owner logs in through the actual browser interface.
  await ownerPage.goto("/");
  await ownerPage.locator("#username").fill("smoke-user");
  await ownerPage.locator("#password").fill("smoke-password");
  await ownerPage.getByRole("button", { name: "Log In" }).click();
  await ownerPage.waitForURL((url) => url.pathname === "/");
  const token = await ownerPage.evaluate(() => sessionStorage.getItem("token"));
  assert.ok(token, "Login must create a session token");
  const headers = { Authorization: "Bearer " + token };

  await expectStatus(
    await owner.request.post("/api/notes", {
      headers,
      data: { title: "Smoke", content: "Browser smoke content" },
    }),
    200,
  );
  await ownerPage.goto("/n/Smoke");
  await ownerPage.getByText("Browser smoke content").waitFor();

  // A short mobile viewport must keep the Share actions accessible.
  await mobile.addInitScript((accessToken) => {
    sessionStorage.setItem("token", accessToken);
  }, token);
  await mobilePage.goto("/n/Smoke");
  await mobilePage.getByRole("button", { name: "Share" }).click();
  const dialog = mobilePage.getByRole("dialog");
  await dialog.locator("#publication-access").selectOption("read");
  await dialog.locator("#publication-slug-mode").selectOption("custom");
  const layout = await dialog.evaluate((element) => {
    const box = element.getBoundingClientRect();
    return {
      top: box.top,
      bottom: box.bottom,
      scrollHeight: element.scrollHeight,
      clientHeight: element.clientHeight,
      viewportHeight: window.innerHeight,
    };
  });
  assert.ok(layout.top >= 0, "Mobile dialog begins inside the viewport");
  assert.ok(layout.bottom <= layout.viewportHeight, "Mobile dialog ends inside the viewport");
  assert.ok(layout.scrollHeight > layout.clientHeight, "Long Share dialog scrolls internally");
  const closeButton = dialog.getByRole("button", { name: "Close" });
  const closeBox = await closeButton.boundingBox();
  assert.ok(closeBox && closeBox.y >= 0 && closeBox.y + closeBox.height <= layout.viewportHeight,
    "Share actions remain visible on short mobile screens");
  await dialog.evaluate((element) => {
    element.scrollTop = element.scrollHeight;
  });
  const scrollPosition = await dialog.evaluate((element) => element.scrollTop);
  assert.ok(scrollPosition > 0, "Mobile dialog can scroll to its actions");
  await closeButton.click();
  assert.equal(await mobilePage.getByRole("dialog").count(), 0);

  // Read-only public shares remain visible without exposing editing controls.
  await expectStatus(
    await owner.request.put("/api/notes/Smoke/publication", {
      headers,
      data: { slugMode: "custom", slug: "browser-smoke", permission: "read" },
    }),
    200,
  );
  await publicPage.goto("/p/browser-smoke");
  await publicPage.getByText("Browser smoke content").waitFor();
  assert.equal(await publicPage.getByRole("button", { name: "Edit" }).count(), 0);

  // Public Markdown editing stays opt-in, and revision checks still apply.
  await expectStatus(
    await owner.request.put("/api/notes/Smoke/publication", {
      headers,
      data: { slugMode: "custom", slug: "browser-smoke", permission: "edit" },
    }),
    200,
  );
  const current = await expectStatus(
    await anonymous.request.get("/api/public/notes/browser-smoke"), 200,
  );
  const revision = (await current.json()).revision;
  await expectStatus(
    await anonymous.request.patch("/api/public/notes/browser-smoke", {
      data: { newContent: "Updated by public browser", revision },
    }),
    200,
  );
  await publicPage.reload();
  await publicPage.getByText("Updated by public browser").waitFor();
  await publicPage.getByRole("button", { name: "Edit" }).waitFor();

  // The protected public page requires a password and cannot be edited.
  const id = "abcd".repeat(8);
  await expectStatus(
    await owner.request.put("/api/encrypted-notes/" + id, {
      headers: { ...headers, "X-Revision": "*" },
      data: Buffer.from("opaque encrypted envelope"),
    }),
    200,
  );
  await expectStatus(
    await owner.request.put("/api/encrypted-notes/" + id + "/publication", {
      headers,
      data: {
        slugMode: "custom",
        slug: "browser-protected",
        permission: "read",
      },
    }),
    200,
  );
  await publicPage.goto("/p/browser-protected");
  await publicPage.getByText("Unlock protected note").waitFor();
  await expectStatus(
    await anonymous.request.put("/api/public/encrypted-notes/browser-protected", {
      data: Buffer.from("tampering attempt"),
    }),
    405,
  );
  console.log("Browser login, private notes, public editing and protected sharing passed.");
} finally {
  await owner.close();
  await anonymous.close();
  await mobile.close();
  await browser.close();
}
