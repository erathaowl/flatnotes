<template>
  <div class="mx-auto w-full max-w-4xl flex-1">
    <ShareModal
      v-if="!publicSlug && unlocked && globalStore.config.sharingEnabled"
      v-model="showSharing"
      :encryptedId="activeId"
      :title="title"
    />

    <div v-if="loading" class="py-12 text-center">Loading encrypted note...</div>
    <p v-else-if="loadError" role="alert" class="py-8 text-theme-danger">{{ loadError }}</p>

    <div v-else-if="!unlocked" class="mx-auto max-w-md pt-12">
      <div class="mb-5 flex items-center gap-2 text-2xl font-semibold">
        <span aria-hidden="true">🔒</span>
        {{ isNew ? "Create protected note" : "Unlock protected note" }}
      </div>
      <p class="mb-4 text-sm text-theme-text-muted">
        Encryption and decryption run only inside your browser. Your password is never sent to the server.
      </p>
      <form @submit.prevent="isNew ? initializeNew() : unlock()">
        <label class="mb-1 block" for="encrypted-password">Protection password</label>
        <input
          id="encrypted-password"
          v-model="password"
          type="password"
          autocomplete="off"
          required
          class="mb-3 w-full rounded border border-theme-border bg-theme-background px-3 py-2"
        />
        <template v-if="isNew">
          <label class="mb-1 block" for="encrypted-confirm">Confirm password</label>
          <input
            id="encrypted-confirm"
            v-model="confirmation"
            type="password"
            autocomplete="off"
            required
            class="mb-3 w-full rounded border border-theme-border bg-theme-background px-3 py-2"
          />
        </template>
        <p v-if="message" role="alert" class="mb-3 text-theme-danger">{{ message }}</p>
        <CustomButton :label="busy ? 'Working...' : isNew ? 'Continue' : 'Unlock'" :disabled="busy || !password" />
      </form>
    </div>

    <template v-else>
      <header class="mb-3 flex flex-col gap-3">
        <div class="min-w-0 w-full">
          <input
            v-if="editing && !publicSlug"
            ref="titleInput"
            v-model="title"
            placeholder="Title"
            :aria-invalid="titleError"
            aria-label="Note title"
            class="w-full min-w-0 bg-theme-background text-2xl outline-none placeholder:italic placeholder:text-theme-text-very-muted sm:text-3xl"
            @input="titleError = false"
          />
          <h1 v-else class="break-words text-2xl sm:text-3xl">{{ title }}</h1>
          <p v-if="titleError" class="mt-1 text-sm text-theme-danger" role="alert">Title is required.</p>
        </div>
        <div class="flex flex-wrap items-center gap-1 print:hidden sm:gap-2">
          <CustomButton label="Lock" @click="lock" />
          <CustomButton
            v-if="!publicSlug && globalStore.config.sharingEnabled"
            label="Share"
            @click="showSharing = true"
          />
          <CustomButton
            v-if="!publicSlug"
            label="Export Markdown"
            @click="exportMarkdown"
          />
          <CustomButton
            v-if="!publicSlug"
            label="Delete"
            style="danger"
            @click="remove"
          />
          <CustomButton v-if="canEdit && editing" label="Attach file" @click="fileInput?.click()" />
          <input ref="fileInput" type="file" class="hidden" @change="attachFile" />
          <CustomButton v-if="canEdit && editing" label="Cancel" @click="cancelEdit" />
          <CustomButton v-if="canEdit && editing" label="Save" :disabled="busy" @click="save" />
          <CustomButton v-if="canEdit && !editing" label="Edit" @click="editing = true" />
        </div>
      </header>
      <hr class="mb-4 border-theme-border" />
      <p v-if="message" role="alert" class="mb-3 text-theme-danger">{{ message }}</p>
      <div v-if="attachments.length" class="mb-4 rounded border border-theme-border p-3">
        <div class="mb-2 text-sm font-semibold">Encrypted attachments</div>
        <ul class="space-y-1">
          <li v-for="attachment in attachments" :key="attachment.id" class="flex flex-wrap items-center gap-2">
            <button type="button" class="underline" @click="downloadAttachment(attachment)">
              {{ attachment.name }}
            </button>
            <button v-if="editing && canEdit" type="button" class="text-theme-danger" @click="removeAttachment(attachment.id)">
              Remove
            </button>
          </li>
        </ul>
      </div>
      <ToastEditor
        v-if="editing"
        ref="editor"
        :initialValue="content"
        :initialEditType="'markdown'"
        :addImageBlobHook="addInlineImage"
        @keydown="handleKeydown"
      />
      <ToastViewer
        v-else
        :key="revision"
        :initialValue="content"
        class="toast-viewer pb-4"
      />
    </template>
  </div>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import {
  deleteEncryptedNote,
  fetchEncryptedNote,
  saveEncryptedNote,
} from "../api.js";
import CustomButton from "../components/CustomButton.vue";
import ShareModal from "../components/ShareModal.vue";
import ToastEditor from "../components/toastui/ToastEditor.vue";
import ToastViewer from "../components/toastui/ToastViewer.vue";
import { EncryptedSession, copyAttachments, newEncryptedId } from "../cryptoSession.js";
import { useGlobalStore } from "../globalStore.js";

const props = defineProps({ id: String, publicSlug: String });
const router = useRouter();
const globalStore = useGlobalStore();
const activeId = ref("");
const password = ref("");
const confirmation = ref("");
const title = ref("");
const content = ref("");
const ciphertext = ref("");
const revision = ref("");
const permission = ref("read");
const unlocked = ref(false);
const loading = ref(true);
const busy = ref(false);
const editing = ref(false);
const showSharing = ref(false);
const message = ref("");
const loadError = ref("");
const editor = ref(null);
const titleInput = ref(null);
const titleError = ref(false);
const fileInput = ref(null);
const attachments = ref([]);
let savedAttachments = [];
let cryptoSession = null;

const isNew = computed(() => props.id === "new" && !props.publicSlug);
const canEdit = computed(() =>
  (!props.publicSlug || permission.value === "edit") &&
  globalStore.config.authType !== "read_only" &&
  globalStore.config.encryptionEnabled,
);

async function load() {
  // Retain the unlocked session after replacing /e/new with the saved note ID.
  if (unlocked.value && activeId.value && props.id === activeId.value && !props.publicSlug) {
    return;
  }
  lock();
  loading.value = true;
  loadError.value = "";
  if (isNew.value) {
    if (!globalStore.config.encryptionEnabled) {
      loadError.value = "Creating protected notes is disabled by the administrator.";
    }
    loading.value = false;
    return;
  }
  try {
    const result = await fetchEncryptedNote(props.id, props.publicSlug);
    ciphertext.value = result.ciphertext;
    activeId.value = result.noteId;
    revision.value = result.revision;
    permission.value = result.permission;
  } catch (error) {
    loadError.value = error.response?.status === 404
      ? "This encrypted note is not available."
      : "Unable to load encrypted note.";
  } finally {
    loading.value = false;
  }
}

async function unlock() {
  busy.value = true;
  message.value = "";
  cryptoSession?.close();
  cryptoSession = new EncryptedSession();
  try {
    const note = await cryptoSession.unlock(activeId.value, password.value, ciphertext.value);
    title.value = note.title;
    content.value = note.content;
    attachments.value = note.attachments || [];
    savedAttachments = copyAttachments(attachments.value);
    unlocked.value = true;
    password.value = "";
  } catch {
    cryptoSession.close();
    cryptoSession = null;
    message.value = "Incorrect password or damaged encrypted note.";
  } finally {
    busy.value = false;
  }
}

async function initializeNew() {
  if (password.value.length < 12) {
    message.value = "Use a password of at least 12 characters.";
    return;
  }
  if (password.value !== confirmation.value) {
    message.value = "Passwords do not match.";
    return;
  }
  // The password stays only in browser memory. The initial document is empty.
  busy.value = true;
  message.value = "";
  cryptoSession = new EncryptedSession();
  activeId.value = newEncryptedId();
  try {
    ciphertext.value = await cryptoSession.create(activeId.value, password.value, "", "");
    title.value = "";
    content.value = "";
    attachments.value = [];
    savedAttachments = [];
    unlocked.value = true;
    editing.value = true;
    password.value = "";
    confirmation.value = "";
  } catch {
    message.value = "Encryption could not be initialized.";
    cryptoSession.close();
    cryptoSession = null;
  } finally {
    busy.value = false;
  }
}

async function save() {
  if (busy.value || !cryptoSession) return;
  if (!title.value.trim()) {
    titleError.value = true;
    await nextTick();
    titleInput.value?.focus();
    return;
  }
  busy.value = true;
  message.value = "";
  titleError.value = false;
  try {
    const markdown = editor.value.getMarkdown();
    const encryptedData = await cryptoSession.save(title.value.trim(), markdown, attachments.value);
    const result = await saveEncryptedNote(
      activeId.value, encryptedData, revision.value || "*", props.publicSlug,
    );
    content.value = markdown;
    savedAttachments = copyAttachments(attachments.value);
    ciphertext.value = encryptedData;
    revision.value = result.revision;
    editing.value = false;
    if (isNew.value) {
      await router.replace({ name: "encryptedNote", params: { id: activeId.value } });
    }
  } catch (error) {
    const status = error.response?.status;
    message.value = status === 409
      ? "The note changed elsewhere. Copy your edits before reloading."
      : status === 413
        ? "The encrypted note exceeds the server size limit."
        : status === 403
          ? "Saving encrypted notes is disabled or access was denied."
          : "Unable to save the encrypted note.";
    // Log only an error category: encrypted content and passwords remain private.
    console.error("Encrypted note save failed:", error.name, status || "browser");
  } finally {
    busy.value = false;
  }
}

function lock() {
  cryptoSession?.close();
  cryptoSession = null;
  title.value = "";
  content.value = "";
  attachments.value = [];
  savedAttachments = [];
  password.value = "";
  confirmation.value = "";
  unlocked.value = false;
  editing.value = false;
  showSharing.value = false;
  message.value = "";
  titleError.value = false;
}

function cancelEdit() {
  attachments.value = copyAttachments(savedAttachments);
  editing.value = false;
  message.value = "";
}

async function remove() {
  if (!window.confirm("Permanently delete this encrypted note?")) return;
  try {
    await deleteEncryptedNote(activeId.value);
    lock();
    await router.push({ name: "encryptedNotes" });
  } catch {
    message.value = "Could not delete the encrypted note.";
  }
}

function exportMarkdown() {
  const file = new Blob([content.value], { type: "text/markdown;charset=utf-8" });
  const href = URL.createObjectURL(file);
  const element = document.createElement("a");
  element.href = href;
  element.download = (title.value || "note") + ".md";
  element.click();
  setTimeout(() => URL.revokeObjectURL(href), 1000);
}

async function attachFile(event) {
  const file = event.target.files?.[0];
  event.target.value = "";
  if (!file) return;
  const total = attachments.value.reduce((sum, item) => sum + Math.ceil(item.dataUrl.length * 0.75), 0);
  if (file.size > 2 * 1024 * 1024 || total + file.size > 2 * 1024 * 1024) {
    message.value = "Total encrypted attachments may not exceed 2 MiB.";
    return;
  }
  const reader = new FileReader();
  reader.onload = () => {
    attachments.value.push({
      id: newEncryptedId(),
      name: file.name,
      dataUrl: reader.result,
    });
    message.value = "";
  };
  reader.onerror = () => {
    message.value = "Could not read the attachment.";
  };
  reader.readAsDataURL(file);
}

function removeAttachment(id) {
  attachments.value = attachments.value.filter((item) => item.id !== id);
}

function downloadAttachment(attachment) {
  try {
    const [header, encoded] = attachment.dataUrl.split(",", 2);
    if (!header.startsWith("data:") || !header.endsWith(";base64")) {
      throw new Error("Invalid encrypted attachment");
    }
    const bytes = Uint8Array.from(atob(encoded), (character) => character.charCodeAt(0));
    const type = header.slice(5, -7) || "application/octet-stream";
    const link = URL.createObjectURL(new Blob([bytes], { type }));
    const element = document.createElement("a");
    element.href = link;
    element.download = attachment.name;
    element.click();
    setTimeout(() => URL.revokeObjectURL(link), 1000);
  } catch {
    message.value = "Could not decrypt the attachment.";
  }
}

function handleKeydown(event) {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") save();
}

function addInlineImage(blob, callback) {
  // Image bytes become part of encrypted Markdown. No plaintext upload occurs.
  const reader = new FileReader();
  reader.onload = () => callback(reader.result, blob.name || "image");
  reader.readAsDataURL(blob);
}

watch(() => [props.id, props.publicSlug], load);
onMounted(load);
onUnmounted(lock);
</script>
