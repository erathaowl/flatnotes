<template>
  <Modal v-model="isVisible" class="max-h-[85vh] overflow-y-auto px-6 py-4">
    <h2 class="mb-4 text-xl">Share note</h2>
    <p class="mb-4 truncate text-sm text-theme-text-muted">{{ title }}</p>

    <label class="mb-1 block font-semibold" for="publication-access">Access</label>
    <select
      id="publication-access"
      v-model="access"
      class="mb-4 w-full rounded border border-theme-border bg-theme-background px-2 py-2"
    >
      <option value="private">Private (default)</option>
      <option value="read">Public: read-only</option>
      <option v-if="!encryptedId" value="edit">Public: anyone with the link can edit</option>
    </select>

    <template v-if="access !== 'private'">
      <label class="mb-1 block font-semibold" for="publication-slug-mode">Public URL</label>
      <select
        id="publication-slug-mode"
        v-model="slugMode"
        class="mb-4 w-full rounded border border-theme-border bg-theme-background px-2 py-2"
      >
        <option value="random">Random identifier (recommended)</option>
        <option v-if="!encryptedId" value="title">Use note title</option>
        <option value="custom">Custom identifier</option>
      </select>

      <div v-if="slugMode === 'custom'" class="mb-4">
        <label class="mb-1 block" for="publication-custom-slug">URL suffix</label>
        <TextInput id="publication-custom-slug" v-model="customSlug" placeholder="my-shared-note" />
      </div>

      <p v-if="draft" class="mb-4 text-sm text-theme-text-muted">
        Sharing will be activated after the first successful note save.
      </p>
      <p v-else-if="published?.expired" class="mb-4 text-sm text-theme-danger">
        This link has expired. Saving again creates a new random link, or choose
        a different custom URL suffix to renew sharing.
      </p>
      <div v-if="!draft && previewSlug" class="mb-4 break-all rounded bg-theme-background-elevated p-3 text-sm">
        <div class="mb-1 text-theme-text-muted">Link preview</div>
        <a class="underline" :href="previewUrl" target="_blank" rel="noopener noreferrer">
          {{ previewUrl }}
        </a>
      </div>
      <p v-else-if="!draft" class="mb-4 text-sm text-theme-text-muted">
        Save to generate a public link.
      </p>

      <ExpirationSelect v-model="expiration" :allowSingleView="access === 'read'" class="mb-4" />
      <label v-if="expiration !== 'none'" class="mb-3 flex items-start gap-2 text-sm">
        <input
          v-model="autoDeleteNote"
          type="checkbox"
          class="mt-1"
        />
        <span>
          Automatically delete this note when the share expires
          <span class="mt-1 block text-xs text-theme-text-muted">
            Permanently deletes the original note after expiration. Leave unchecked to retain it.
          </span>
        </span>
      </label>

      <p v-if="expiration === 'once'" class="mb-3 text-xs text-theme-text-muted">
        The first recipient to open this shared link consumes its single view.
        Private owner access does not consume the link.
      </p>
      <p v-if="access === 'edit'" class="mb-4 text-sm text-theme-danger">
        Anyone with this link can change the note content. Edits cannot be attributed to an individual.
      </p>
      <p v-if="slugMode !== 'random'" class="mb-4 text-sm text-theme-text-muted">
        Predictable links can be discovered by guessing the URL.
      </p>
    </template>

    <p v-if="errorMessage" role="alert" class="mb-4 text-sm text-theme-danger">{{ errorMessage }}</p>

    <div class="flex flex-wrap justify-end gap-2">
      <CustomButton v-if="published && !draft" label="Unpublish" style="danger" :disabled="busy" @click="unpublish" />
      <CustomButton
        v-if="published && !published.expired && access !== 'private' && previewSlug === published.slug"
        label="Copy link"
        :disabled="busy || !previewSlug"
        @click="copyLink"
      />
      <CustomButton label="Close" @click="isVisible = false" />
      <CustomButton v-if="draft || access !== 'private'" :label="draft ? 'Apply' : 'Save'" style="cta" :disabled="busy" @click="save" />
    </div>
  </Modal>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import {
  getPublication, removePublication, savePublication,
  getEncryptedPublication, removeEncryptedPublication, saveEncryptedPublication,
} from "../api.js";
import CustomButton from "./CustomButton.vue";
import ExpirationSelect from "./ExpirationSelect.vue";
import Modal from "./Modal.vue";
import TextInput from "./TextInput.vue";

const props = defineProps({
  title: String,
  encryptedId: String,
  draft: { type: Boolean, default: false },
  initialSettings: { type: Object, default: null },
  getVerifier: { type: Function, default: null },
});
const emit = defineEmits(["updated"]);
const isVisible = defineModel({ type: Boolean });
const router = useRouter();
const published = ref(null);
const access = ref("private");
const slugMode = ref("random");
const customSlug = ref("");
const expiration = ref("none");
const autoDeleteNote = ref(false);
const errorMessage = ref("");
const busy = ref(false);

watch(access, (value) => {
  if (value === "edit" && expiration.value === "once") expiration.value = "none";
  if (value === "private") autoDeleteNote.value = false;
});
watch(expiration, (value) => {
  if (value === "none") autoDeleteNote.value = false;
});

function slugify(title) {
  return (title || "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 80)
    .replace(/-$/, "");
}

const previewSlug = computed(() => {
  if (access.value === "private") return "";
  if (slugMode.value === "custom") return customSlug.value.trim().toLowerCase();
  if (published.value && published.value.slugMode === slugMode.value && !published.value.expired) {
    return published.value.slug;
  }
  return slugMode.value === "title" ? slugify(props.title) : "";
});

const previewUrl = computed(() => previewSlug.value
  ? window.location.origin + router.resolve({
    name: "publicNote", params: { slug: previewSlug.value },
  }).href
  : "",
);

async function load() {
  busy.value = true;
  errorMessage.value = "";
  if (props.draft) {
    published.value = null;
    const settings = props.initialSettings;
    access.value = settings?.permission || "private";
    slugMode.value = settings?.slugMode || "random";
    customSlug.value = settings?.slugMode === "custom" ? settings.slug || "" : "";
    expiration.value = settings?.expiration || "none";
    autoDeleteNote.value = Boolean(settings?.autoDeleteNote);
    busy.value = false;
    return;
  }
  try {
    published.value = props.encryptedId
      ? await getEncryptedPublication(props.encryptedId)
      : await getPublication(props.title);
    access.value = published.value?.permission || "private";
    slugMode.value = published.value?.slugMode || "random";
    customSlug.value = published.value?.slugMode === "custom" ? published.value.slug : "";
    expiration.value = published.value?.expiration || "none";
    autoDeleteNote.value = Boolean(published.value?.autoDeleteNote);
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || "Failed to load publication settings.";
  } finally {
    busy.value = false;
  }
}

async function save() {
  if (busy.value) return;
  busy.value = true;
  errorMessage.value = "";
  try {
    if (access.value === "private") {
      if (!props.draft) await unpublish(true);
      else emit("updated", null);
      isVisible.value = false;
      return;
    }
    if (slugMode.value !== "random") {
      const suffix = slugMode.value === "title" ? slugify(props.title) : customSlug.value.trim().toLowerCase();
      if (!/^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$/.test(suffix)) {
        throw new Error("Enter a valid public URL suffix before saving.");
      }
    }
    const settings = {
      slugMode: slugMode.value,
      slug: slugMode.value === "custom" ? customSlug.value.trim() : null,
      permission: access.value,
      expiration: expiration.value,
      autoDeleteNote: expiration.value !== "none" && autoDeleteNote.value,
    };
    if (props.draft) {
      emit("updated", settings);
    } else {
      if (props.encryptedId && expiration.value === "once") {
        settings.viewVerifier = await props.getVerifier?.();
      }
      published.value = await (props.encryptedId
        ? saveEncryptedPublication(props.encryptedId, settings)
        : savePublication(props.title, settings));
      emit("updated", published.value);
    }
    isVisible.value = false;
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || error.message || "Failed to publish this note.";
  } finally {
    busy.value = false;
  }
}

async function unpublish(fromSave = false) {
  if (busy.value && !fromSave) return;
  if (!fromSave && !window.confirm("Remove public access to this note?")) return;
  busy.value = true;
  errorMessage.value = "";
  try {
    if (props.encryptedId) await removeEncryptedPublication(props.encryptedId);
    else await removePublication(props.title);
    published.value = null;
    access.value = "private";
    expiration.value = "none";
    autoDeleteNote.value = false;
    emit("updated", null);
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || "Failed to unpublish this note.";
    if (fromSave) throw error;
  } finally {
    busy.value = false;
  }
}

async function copyLink() {
  try {
    await navigator.clipboard.writeText(previewUrl.value);
  } catch {
    errorMessage.value = "Copy failed. Please select the URL manually.";
  }
}

watch(isVisible, (visible) => {
  if (visible && (props.draft || props.title || props.encryptedId)) load();
});
</script>
