<template>
  <div class="mx-auto flex w-full max-w-4xl flex-1 flex-col">
    <div v-if="loading" class="py-12 text-center text-theme-text-muted">Loading shared note...</div>
    <div v-else-if="errorMessage" role="alert" class="py-12 text-center text-theme-danger">
      {{ errorMessage }}
    </div>
    <EncryptedNote v-else-if="encryptedSlug" :publicSlug="encryptedSlug" />
    <template v-else-if="note">
      <header class="mb-4 flex flex-wrap items-center justify-between gap-2">
        <h1 class="break-words text-3xl">{{ note.title }}</h1>
        <div v-if="note.permission === 'edit' && !note.viewToken" class="flex gap-2 print:hidden">
          <CustomButton v-if="editing" label="Cancel" @click="editing = false" />
          <CustomButton v-if="editing" label="Save" style="cta" @click="save" />
          <CustomButton v-else label="Edit" @click="editing = true" />
        </div>
      </header>
      <p v-if="note.viewToken" class="mb-3 text-xs text-theme-text-muted">
        Single view consumed. Reloading or following the link again will not work.
      </p>
      <p v-if="note.expiration?.expiresAt" class="mb-3 text-xs text-theme-text-muted">
        Expires {{ new Date(note.expiration.expiresAt * 1000).toLocaleString() }}
      </p>
      <p v-if="saveError" role="alert" class="mb-3 text-theme-danger">{{ saveError }}</p>
      <hr class="mb-4 border-theme-border" />
      <ToastViewer
        v-if="!editing"
        :key="note.revision"
        :initialValue="viewerContent"
        class="toast-viewer"
      />
      <ToastEditor
        v-else
        ref="editor"
        :initialValue="note.content"
        :initialEditType="'markdown'"
        class="min-h-[50vh]"
        @keydown="handleKeydown"
      />
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { getPublicNote, updatePublicNote } from "../api.js";
import CustomButton from "../components/CustomButton.vue";
import ToastEditor from "../components/toastui/ToastEditor.vue";
import ToastViewer from "../components/toastui/ToastViewer.vue";
import EncryptedNote from "./EncryptedNote.vue";

const props = defineProps({ slug: String });
const note = ref(null);
const encryptedSlug = ref("");
const editor = ref(null);
const editing = ref(false);
const loading = ref(true);
const errorMessage = ref("");
const saveError = ref("");
const saving = ref(false);

// Relative attachment URLs are resolved through an allowlisted public endpoint.
const viewerContent = computed(() => {
  const content = note.value?.content || "";
  return content.replace(
    /(^|[\s("'=])\/?attachments\/([^\s\)"'<>\]?#]+)/g,
    (_, prefix, filename) =>
      prefix + "api/public/notes/" + encodeURIComponent(props.slug) +
      "/attachments/" + filename +
      (note.value?.viewToken ? "?view_token=" + encodeURIComponent(note.value.viewToken) : ""),
  );
});

async function load() {
  loading.value = true;
  encryptedSlug.value = "";
  editing.value = false;
  errorMessage.value = "";
  try {
    note.value = await getPublicNote(props.slug);
  } catch (error) {
    note.value = null;
    if (error.response?.status === 404) {
      encryptedSlug.value = props.slug;
    } else if (error.response?.status === 410) {
      errorMessage.value = "This note has expired or its single view has been used.";
    } else {
      errorMessage.value = "Failed to load the shared note.";
    }
  } finally {
    loading.value = false;
  }
}

async function save() {
  if (saving.value || !editor.value) return;
  saving.value = true;
  saveError.value = "";
  try {
    note.value = await updatePublicNote(
      props.slug, editor.value.getMarkdown(), note.value.revision,
    );
    editing.value = false;
  } catch (error) {
    if (error.response?.status === 409) {
      saveError.value = "This note changed elsewhere. Copy your edits before reloading.";
    } else if (error.response?.status === 403) {
      saveError.value = "Public editing is no longer enabled.";
    } else if (error.response?.status === 404) {
      saveError.value = "This note is no longer published.";
    } else {
      saveError.value = "Could not save the note.";
    }
  } finally {
    saving.value = false;
  }
}

function handleKeydown(event) {
  if ((event.ctrlKey || event.metaKey) && event.key === "Enter") save();
}

watch(() => props.slug, load);
onMounted(load);
</script>
