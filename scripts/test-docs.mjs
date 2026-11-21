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
]) {
  assert.ok(env.includes(name), "Undocumented configuration: " + name);
}
for (const file of ["wiki/Notes-and-Editor.md", "wiki/Encrypted-Notes.md", "wiki/Troubleshooting.md"]) {
  assert.doesNotMatch(read(file),
    /save it first, leave edit mode|unsaved draft must be handled before protection/i,
    "Outdated Protect instructions in " + file);
}
assert.match(read("wiki/Publishing-Notes.md"), /Automatically delete this note when the share expires/i);
assert.match(read("wiki/Notes-and-Editor.md"), /unsaved/i);
assert.match(read("wiki/Publishing-Notes.md"), /first .*Save|note.*Save/i);
assert.equal(existsSync("wiki/Expiring-Notes.md"), false);
for (const file of docs) {
  assert.doesNotMatch(read(file), /FLATNOTES_EXPIRATION_ENABLED|FLATNOTES_EXPIRATION_DEFAULT/);
  assert.doesNotMatch(read(file), /\/api\/expiring-notes|\/expiring\b/);
}

const releaseWorkflow = read(".github/workflows/release.yml");
assert.doesNotMatch(releaseWorkflow, /git push --force|--clobber/);

const buildWorkflow = read(".github/workflows/build.yml");
const cleanupWorkflow = read(".github/workflows/cleanup-dev-images.yml");
assert.match(buildWorkflow, /needs: package/);
assert.match(buildWorkflow, /type=raw,value=dev-/);
assert.match(buildWorkflow, /push: \$\{\{ github\.event_name != 'pull_request' \}\}/);
assert.match(cleanupWorkflow, /schedule:/);
assert.match(cleanupWorkflow, /scripts\/cleanup_ghcr\.py/);

// Keep workflow triggers and links aligned with the canonical branch.
const workflows = [
  ".github/workflows/build.yml",
  ".github/workflows/cleanup-dev-images.yml",
  ".github/workflows/release.yml",
  ".github/workflows/publish-wiki.yml",
  ".github/workflows/update-node-lock.yml",
];
const releaseNotes = readdirSync(".github/release-notes")
  .filter((file) => file.endsWith(".md"))
  .map((file) => join(".github/release-notes", file));

for (const file of [...docs, ...workflows, ...releaseNotes]) {
  assert.doesNotMatch(read(file), /\bdevelop\b/,
    "Obsolete develop branch reference in " + file);
}
for (const file of workflows.filter((name) => name !== ".github/workflows/cleanup-dev-images.yml")) {
  assert.match(read(file), /master/, "Missing master branch configuration in " + file);
}

console.log("Validated " + docs.length + " Markdown documents for version " + version + ".");
