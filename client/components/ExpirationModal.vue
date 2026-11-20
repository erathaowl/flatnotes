<template>
  <Modal v-model="visible" class="max-w-md px-6 py-5">
    <h2 class="mb-4 text-xl">Expiration</h2>
    <p v-if="loading" class="mb-3">Loading expiration...</p>
    <template v-else>
      <ExpirationSelect v-model="policy" />
      <p v-if="current?.expiresAt" class="mt-3 text-xs text-theme-text-muted">
        Current deadline: {{ new Date(current.expiresAt * 1000).toLocaleString() }}
      </p>
      <p v-if="errorMessage" role="alert" class="mt-3 text-sm text-theme-danger">{{ errorMessage }}</p>
      <div class="mt-5 flex justify-end gap-2">
        <CustomButton label="Cancel" @click="visible = false" />
        <CustomButton label="Save" style="cta" :disabled="busy" @click="save" />
      </div>
    </template>
  </Modal>
</template>

<script setup>
import { ref, watch } from "vue";
import { getNoteExpiration, setNoteExpiration } from "../api.js";
import CustomButton from "./CustomButton.vue";
import ExpirationSelect from "./ExpirationSelect.vue";
import Modal from "./Modal.vue";

const props = defineProps({
  kind: { type: String, required: true },
  noteId: { type: String, required: true },
  getVerifier: { type: Function, default: null },
});
const visible = defineModel({ type: Boolean });
const emit = defineEmits(["updated"]);
const policy = ref("none");
const current = ref(null);
const loading = ref(false);
const busy = ref(false);
const errorMessage = ref("");

watch(visible, async (open) => {
  if (!open) return;
  loading.value = true;
  errorMessage.value = "";
  try {
    current.value = await getNoteExpiration(props.kind, props.noteId);
    policy.value = current.value.policy;
  } catch {
    errorMessage.value = "Unable to read expiration settings.";
  } finally {
    loading.value = false;
  }
});

async function save() {
  if (busy.value) return;
  busy.value = true;
  errorMessage.value = "";
  try {
    const verifier = policy.value === "once" && props.kind === "encrypted"
      ? await props.getVerifier?.()
      : null;
    current.value = await setNoteExpiration(props.kind, props.noteId, policy.value, verifier);
    emit("updated", current.value);
    visible.value = false;
  } catch (error) {
    errorMessage.value = error.response?.status === 410
      ? "This note has already expired or been viewed."
      : error.response?.data?.detail || "Unable to save expiration settings.";
  } finally {
    busy.value = false;
  }
}
</script>
