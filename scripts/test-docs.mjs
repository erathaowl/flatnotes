import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { basename, dirname, join, resolve } from "node:path";

const read = (file) => readFileSync(file, "utf8");
const version = read("pyproject.toml").match(/^version = "(\d+\.\d+\.\d+)"$/m)?.[1];
assert.ok(version, "Project version is missing");

const pkg = JSON.parse(read("package.json"));
const lock = JSON.parse(read("package-lock.json"));
assert.equal(pkg.version, version);
assert.equal(lock.version, version);
assert.equal(lock.packages[""].version, version);
assert.ok(read("uv.lock").includes('name = "flatnotes"\nversion = "' + version + '"'));

const pages = readdirSync("wiki").filter((file) => file.endsWith(".md"));
const docs = ["README.md", "readme-it.md", ...pages.map((name) => join("wiki", name))];
const sidebar = read("wiki/_Sidebar.md");
assert.ok(pages.length >= 15, "Wiki pages are missing");
for (const page of pages.filter((name) => !name.startsWith("_"))) {
  assert.ok(sidebar.includes("/wiki/" + basename(page, ".md")),
    "Missing sidebar link for " + page);
}

for (const file of docs) {
  const body = read(file);
  if (!file.endsWith("_Sidebar.md")) {
    assert.match(body, /^# /m, "Missing heading in " + file);
  }
  const fences = body.split("\n").filter((line) => line.startsWith("~~~") || line.startsWith(String.fromCharCode(96).repeat(3))).length;
  assert.equal(fences % 2, 0, "Unclosed code fence in " + file);

  for (const match of body.matchAll(/\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g)) {
    const href = match[1].split("#")[0];
    if (href.endsWith(".md") && !href.startsWith("http")) {
      assert.ok(existsSync(resolve(dirname(file), href)), "Broken local link in " + file + ": " + href);
    }
    const wiki = href.match(/^https:\/\/github\.com\/erathaowl\/flatnotes\/wiki\/([\w-]+)$/);
    if (wiki) {
      assert.ok(pages.includes(wiki[1] + ".md"), "Missing wiki page " + wiki[1]);
    }
  }
  assert.doesNotMatch(body,
    /flatnotes-6\.2\.0|ghcr\.io\/erathaowl\/flatnotes:v6\.2\.0|releases\/tag\/v6\.2\.0/,
    "Outdated release link in " + file);
}

for (const file of ["README.md", "readme-it.md", "wiki/Home.md", "wiki/_Sidebar.md"]) {
  assert.ok(read(file).includes(version), "Missing current version in " + file);
}
for (const file of ["README.md", "readme-it.md", "wiki/Docker-and-Releases.md"]) {
  assert.ok(read(file).includes("flatnotes-" + version + "-py3-none-any.whl"));
  assert.ok(read(file).includes("flatnotes:v" + version));
}

const env = read("wiki/Environment-Variables.md");
for (const name of [
  "FLATNOTES_AUTH_TYPE", "FLATNOTES_SECRET_KEY",
  "FLATNOTES_ENCRYPTION_ENABLED", "FLATNOTES_SHARING_ENABLED",
  "FLATNOTES_ENCRYPTION_PASSWORD_MIN_LENGTH",
  "FLATNOTES_ENCRYPTION_PASSWORD_MIN_CLASSES",
  "FLATNOTES_EXPIRATION_ENABLED", "FLATNOTES_EXPIRATION_DEFAULT",
]) {
  assert.ok(env.includes(name), "Undocumented configuration: " + name);
}
for (const file of ["wiki/Notes-and-Editor.md", "wiki/Encrypted-Notes.md", "wiki/Troubleshooting.md"]) {
  assert.doesNotMatch(read(file),
    /save it first, leave edit mode|unsaved draft must be handled before protection/i,
    "Outdated Protect instructions in " + file);
}
assert.match(read("wiki/Expiring-Notes.md"), /no inline selector/i);
assert.match(read("wiki/Notes-and-Editor.md"), /unsaved/i);
assert.match(read("wiki/Publishing-Notes.md"), /first \*\*Save\*\*/);

console.log("Validated " + docs.length + " Markdown documents for version " + version + ".");
