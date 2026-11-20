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
      <option value="edit">Public: anyone with the link can edit</option>
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
      <div v-if="!draft && previewSlug" class="mb-4 break-all rounded bg-theme-background-elevated p-3 text-sm">
        <div class="mb-1 text-theme-text-muted">Link preview</div>
        <a class="underline" :href="previewUrl" target="_blank" rel="noopener noreferrer">
          {{ previewUrl }}
        </a>
      </div>
      <p v-else-if="!draft" class="mb-4 text-sm text-theme-text-muted">
        Save to generate a random public link.
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
        v-if="published && access !== 'private' && previewSlug === published.slug"
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
import Modal from "./Modal.vue";
import TextInput from "./TextInput.vue";

const props = defineProps({
  title: String,
  encryptedId: String,
  draft: { type: Boolean, default: false },
  initialSettings: { type: Object, default: null },
});
const emit = defineEmits(["updated"]);
const isVisible = defineModel({ type: Boolean });
const router = useRouter();
const published = ref(null);
const access = ref("private");
const slugMode = ref("random");
const customSlug = ref("");
const errorMessage = ref("");
const busy = ref(false);

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
  if (published.value && published.value.slugMode === slugMode.value) {
    return published.value.slug;
  }
  return slugMode.value === "title" ? slugify(props.title) : "";
});

const previewUrl = computed(() => {
  if (!previewSlug.value) return "";
  return window.location.origin + router.resolve({
    name: "publicNote", params: { slug: previewSlug.value },
  }).href;
});

async function load() {
  busy.value = true;
  errorMessage.value = "";
  if (props.draft) {
    published.value = null;
    access.value = props.initialSettings?.permission || "private";
    slugMode.value = props.initialSettings?.slugMode || "random";
    customSlug.value = props.initialSettings?.slugMode === "custom"
      ? props.initialSettings.slug || "" : "";
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
    if (props.draft) {
      if (access.value !== "private" && slugMode.value !== "random") {
        const slug = slugMode.value === "title"
          ? slugify(props.title) : customSlug.value.trim().toLowerCase();
        if (!/^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$/.test(slug)) {
          throw new Error("Enter a valid public URL suffix before saving.");
        }
      }
      emit("updated", access.value === "private" ? null : {
        slugMode: slugMode.value,
        slug: slugMode.value === "custom" ? customSlug.value.trim() : null,
        permission: access.value,
      });
      isVisible.value = false;
      return;
    }
    published.value = await (props.encryptedId
      ? saveEncryptedPublication(props.encryptedId, {
        slugMode: slugMode.value, slug: slugMode.value === "custom" ? customSlug.value : null,
        permission: access.value,
      })
      : savePublication(props.title, {
      slugMode: slugMode.value,
      slug: slugMode.value === "custom" ? customSlug.value : null,
      permission: access.value,
    }));
    emit("updated", published.value);
    isVisible.value = false;
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || error.message || "Failed to publish this note.";
  } finally {
    busy.value = false;
  }
}

async function unpublish() {
  if (busy.value || !window.confirm("Remove public access to this note?")) return;
  busy.value = true;
  errorMessage.value = "";
  try {
    if (props.encryptedId) await removeEncryptedPublication(props.encryptedId);
    else await removePublication(props.title);
    published.value = null;
    access.value = "private";
    emit("updated", null);
  } catch (error) {
    errorMessage.value = error.response?.data?.detail || "Failed to unpublish this note.";
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
